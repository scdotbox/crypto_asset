/**
 * UI管理器模块
 * 
 * 统一管理界面交互、通知系统、模态框、加载状态等UI功能
 */

import { CONFIG, MESSAGES } from './config.js';
import { formatAddress, formatChainName, getChainIcon, formatNumber, getNotificationIcon } from './utils.js';

export class UIManager {
    constructor() {
        this.currentView = 'table';
        this.isSelectMode = false;
        this.selectedAssets = new Set();
        this.isLoading = false;
        
        this.setupNotificationSystem();
    }

    /**
     * 设置通知系统
     */
    setupNotificationSystem() {
        // 创建通知容器（如果不存在）
        let notificationContainer = document.getElementById('notification-container');
        if (!notificationContainer) {
            notificationContainer = document.createElement('div');
            notificationContainer.id = 'notification-container';
            notificationContainer.className = 'notification-container';
            document.body.appendChild(notificationContainer);
        }
    }

    /**
     * 显示通知
     * @param {string} message 通知消息
     * @param {string} type 通知类型（info, success, warning, error）
     * @param {number} duration 显示时长（毫秒）
     */
    showNotification(message, type = 'info', duration = CONFIG.UI.NOTIFICATION_DURATION) {
        const container = document.getElementById('notification-container');
        if (!container) return;

        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        
        const icon = getNotificationIcon(type);
        notification.innerHTML = `
            <div class="notification-content">
                <span class="notification-icon">${icon}</span>
                <span class="notification-message">${message}</span>
                <button class="notification-close" onclick="this.parentElement.parentElement.remove()">×</button>
            </div>
        `;

        container.appendChild(notification);

        // 自动移除通知
        if (duration > 0) {
            setTimeout(() => {
                if (notification.parentElement) {
                    notification.remove();
                }
            }, duration);
        }

        // 添加点击关闭功能
        notification.addEventListener('click', (e) => {
            if (e.target.classList.contains('notification-close')) {
                notification.remove();
            }
        });
    }

    /**
     * 显示模态框
     * @param {string} content HTML内容
     */
    showModal(content) {
        // 移除现有模态框
        this.closeModal();

        const modal = document.createElement('div');
        modal.className = 'modal';
        modal.innerHTML = `
            <div class="modal-content">
                <span class="modal-close">&times;</span>
                <div class="modal-body">
                    ${content}
                </div>
            </div>
        `;

        // 添加关闭事件
        const closeBtn = modal.querySelector('.modal-close');
        closeBtn.addEventListener('click', () => this.closeModal());

        // 点击外部关闭
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                this.closeModal();
            }
        });

        document.body.appendChild(modal);
        
        // 设置焦点以支持Esc键关闭
        modal.focus();
    }

    /**
     * 关闭模态框
     */
    closeModal() {
        const modals = document.querySelectorAll('.modal');
        modals.forEach(modal => modal.remove());
    }

    /**
     * 显示确认对话框
     * @param {Object} options 对话框配置
     * @returns {Promise<boolean>} 确认结果
     */
    async showConfirmationDialog({ 
        title, 
        message, 
        confirmText = '确认', 
        cancelText = '取消', 
        type = 'danger' 
    }) {
        return new Promise((resolve) => {
            const content = `
                <div class="confirmation-dialog ${type}">
                    <h3>${title}</h3>
                    <p class="confirmation-message">${message.replace(/\n/g, '<br>')}</p>
                    <div class="confirmation-actions">
                        <button class="btn btn-secondary cancel-confirm-btn">${cancelText}</button>
                        <button class="btn btn-${type} confirm-confirm-btn">${confirmText}</button>
                    </div>
                </div>
            `;

            this.showModal(content);

            // 使用更可靠的事件绑定方式
            setTimeout(() => {
                const confirmBtn = document.querySelector('.confirm-confirm-btn');
                const cancelBtn = document.querySelector('.cancel-confirm-btn');

                if (!confirmBtn || !cancelBtn) {
                    console.error('确认对话框按钮未找到', { confirmBtn, cancelBtn });
                    resolve(false);
                    return;
                }

                console.log('确认对话框按钮绑定成功', { confirmBtn, cancelBtn });

                const handleConfirm = (e) => {
                    console.log('确认按钮被点击');
                    e.preventDefault();
                    e.stopPropagation();
                    this.closeModal();
                    document.removeEventListener('keydown', handleEscape);
                    resolve(true);
                };

                const handleCancel = (e) => {
                    console.log('取消按钮被点击');
                    e.preventDefault();
                    e.stopPropagation();
                    this.closeModal();
                    document.removeEventListener('keydown', handleEscape);
                    resolve(false);
                };

                const handleEscape = (e) => {
                    if (e.key === 'Escape') {
                        console.log('ESC键被按下');
                        e.preventDefault();
                        this.closeModal();
                        document.removeEventListener('keydown', handleEscape);
                        resolve(false);
                    }
                };

                // 绑定事件
                confirmBtn.addEventListener('click', handleConfirm);
                cancelBtn.addEventListener('click', handleCancel);
                document.addEventListener('keydown', handleEscape);

                // 焦点设置到取消按钮（安全选择）
                cancelBtn.focus();

            }, 100); // 增加延迟确保DOM更新完成
        });
    }

    /**
     * 显示加载状态
     * @param {boolean} show 是否显示
     */
    showLoading(show) {
        const loadingElement = document.getElementById('loading');
        if (loadingElement) {
            loadingElement.style.display = show ? 'flex' : 'none';
        }
        this.isLoading = show;
    }

    /**
     * 显示空状态
     * @param {boolean} show 是否显示
     */
    showEmptyState(show) {
        const emptyElement = document.getElementById('emptyState');
        if (emptyElement) {
            emptyElement.style.display = show ? 'block' : 'none';
        }
    }

    /**
     * 切换视图模式
     * @param {string} view 视图类型（table, cards）
     */
    switchView(view) {
        this.currentView = view;
        
        // 更新按钮状态
        document.querySelectorAll('.view-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.view === view);
        });

        // 更新视图容器显示
        const tableView = document.getElementById('tableView');
        const cardsView = document.getElementById('cardsView');
        
        if (tableView && cardsView) {
            tableView.style.display = view === 'table' ? 'block' : 'none';
            cardsView.style.display = view === 'cards' ? 'block' : 'none';
        }
    }

    /**
     * 进入选择模式
     */
    toggleSelectMode() {
        this.isSelectMode = !this.isSelectMode;
        this.selectedAssets.clear();
        this.updateSelectModeUI();
    }

    /**
     * 取消选择模式
     */
    cancelSelectMode() {
        this.isSelectMode = false;
        this.selectedAssets.clear();
        this.updateSelectModeUI();
    }

    /**
     * 更新选择模式UI
     */
    updateSelectModeUI() {
        const selectControls = document.getElementById('selectControls');
        const selectModeBtn = document.getElementById('selectModeBtn');
        const batchControls = document.getElementById('batchActionsPanel');

        if (selectControls) {
            selectControls.style.display = this.isSelectMode ? 'flex' : 'none';
        }

        if (selectModeBtn) {
            selectModeBtn.textContent = this.isSelectMode ? '取消选择' : '批量选择';
            selectModeBtn.className = this.isSelectMode ? 'btn btn-secondary' : 'btn btn-outline-primary';
        }

        if (batchControls) {
            batchControls.style.display = this.isSelectMode ? 'block' : 'none';
        }

        // 更新表格行显示
        document.querySelectorAll('.asset-row').forEach(row => {
            const checkbox = row.querySelector('.asset-checkbox');
            if (checkbox) {
                checkbox.style.display = this.isSelectMode ? 'inline-block' : 'none';
            }
        });

        // 更新卡片视图的复选框显示
        document.querySelectorAll('.asset-card').forEach(card => {
            const checkbox = card.querySelector('.asset-checkbox');
            if (checkbox) {
                checkbox.style.display = this.isSelectMode ? 'inline-block' : 'none';
            }
        });

        // 更新选中状态
        this.updateBatchControlsVisibility();
    }

    /**
     * 切换资产选中状态
     * @param {string} assetId 资产ID
     */
    toggleAssetSelection(assetId) {
        if (this.selectedAssets.has(assetId)) {
            this.selectedAssets.delete(assetId);
        } else {
            this.selectedAssets.add(assetId);
        }
        
        this.updateRowSelection(assetId);
        this.updateBatchControlsVisibility();
    }

    /**
     * 全选/取消全选
     * @param {Array} allAssets 所有资产列表
     */
    selectAll(allAssets) {
        const isAllSelected = this.selectedAssets.size === allAssets.length;
        
        if (isAllSelected) {
            // 取消全选
            this.selectedAssets.clear();
        } else {
            // 全选
            allAssets.forEach(asset => {
                this.selectedAssets.add(asset.id);
            });
        }

        // 更新所有行的选中状态
        allAssets.forEach(asset => {
            this.updateRowSelection(asset.id);
        });

        this.updateBatchControlsVisibility();
    }

    /**
     * 更新行选中状态
     * @param {string} assetId 资产ID
     */
    updateRowSelection(assetId) {
        const row = document.querySelector(`[data-asset-id="${assetId}"]`);
        if (row) {
            const checkbox = row.querySelector('.asset-checkbox input');
            const isSelected = this.selectedAssets.has(assetId);
            
            if (checkbox) {
                checkbox.checked = isSelected;
            }
            
            row.classList.toggle('selected', isSelected);
        }
    }

    /**
     * 更新批量操作控件显示
     */
    updateBatchControlsVisibility() {
        const batchControls = document.getElementById('batchActionsPanel');
        const selectedCount = document.getElementById('selectedCount');
        const batchEditBtn = document.getElementById('batchEditBtn');
        const batchDeleteBtn = document.getElementById('batchDeleteBtn');
        
        if (batchControls) {
            batchControls.style.display = this.isSelectMode ? 'block' : 'none';
        }
        
        if (selectedCount) {
            selectedCount.textContent = this.selectedAssets.size;
        }

        // 更新批量操作按钮的启用状态
        const hasSelection = this.selectedAssets.size > 0;
        if (batchEditBtn) {
            batchEditBtn.disabled = !hasSelection;
        }
        if (batchDeleteBtn) {
            batchDeleteBtn.disabled = !hasSelection;
        }
    }

    /**
     * 显示资产存在性指示器
     * @param {Object} existenceResult 检查结果
     */
    showAssetExistenceIndicator(existenceResult) {
        const indicator = document.getElementById('assetExistenceIndicator');
        if (!indicator) return;

        indicator.style.display = 'block';
        
        if (existenceResult.exists) {
            indicator.className = 'asset-indicator warning';
            indicator.innerHTML = `
                <span class="indicator-icon">⚠️</span>
                <span class="indicator-text">该资产已存在于数据库中</span>
                <span class="indicator-details">
                    钱包: ${existenceResult.existing_asset.wallet_name || '未命名'} | 
                    添加时间: ${new Date(existenceResult.existing_asset.created_at).toLocaleDateString()}
                </span>
            `;
        } else {
            indicator.className = 'asset-indicator success';
            indicator.innerHTML = `
                <span class="indicator-icon">✅</span>
                <span class="indicator-text">该资产尚未添加，可以安全添加</span>
            `;
        }
    }

    /**
     * 隐藏资产存在性指示器
     */
    hideAssetExistenceIndicator() {
        const indicator = document.getElementById('assetExistenceIndicator');
        if (indicator) {
            indicator.style.display = 'none';
        }
    }

    /**
     * 显示重复资产模态框
     * @param {Object} result 重复检查结果
     */
    showDuplicateAssetModal(result) {
        const existingAsset = result.existing_asset;
        const content = `
            <div class="duplicate-asset-modal">
                <h3>⚠️ 资产已存在</h3>
                <p>检测到相同的资产已存在于系统中：</p>
                
                <div class="existing-asset-info">
                    <div class="asset-detail">
                        <label>钱包地址:</label>
                        <span class="asset-address">${formatAddress(existingAsset.address)}</span>
                        <button class="btn btn-small btn-secondary" onclick="app.copyToClipboard('${existingAsset.address}')">
                            📋 复制
                        </button>
                    </div>
                    
                    <div class="asset-detail">
                        <label>区块链:</label>
                        <span class="asset-chain">
                            ${getChainIcon(existingAsset.chain_name)} ${formatChainName(existingAsset.chain_name)}
                        </span>
                    </div>
                    
                    <div class="asset-detail">
                        <label>代币:</label>
                        <span class="asset-token">${existingAsset.token_symbol}</span>
                    </div>
                    
                    <div class="asset-detail">
                        <label>钱包名称:</label>
                        <span class="asset-wallet">${existingAsset.wallet_name || '未设置'}</span>
                    </div>
                    
                    <div class="asset-detail">
                        <label>当前余额:</label>
                        <span class="asset-balance">${formatNumber(existingAsset.quantity)} ${existingAsset.token_symbol}</span>
                    </div>
                    
                    <div class="asset-detail">
                        <label>当前价值:</label>
                        <span class="asset-value">$${formatNumber(existingAsset.value_usdc)}</span>
                    </div>
                    
                    <div class="asset-detail">
                        <label>添加时间:</label>
                        <span class="asset-created">${new Date(existingAsset.created_at).toLocaleString()}</span>
                    </div>
                    
                    ${existingAsset.tags && existingAsset.tags.length > 0 ? `
                        <div class="asset-detail">
                            <label>标签:</label>
                            <span class="asset-tags">
                                ${existingAsset.tags.map(tag => `<span class="tag">${tag}</span>`).join('')}
                            </span>
                        </div>
                    ` : ''}
                    
                    ${existingAsset.notes ? `
                        <div class="asset-detail">
                            <label>备注:</label>
                            <span class="asset-notes">${existingAsset.notes}</span>
                        </div>
                    ` : ''}
                </div>
                
                <div class="duplicate-actions">
                    <p><strong>选择操作：</strong></p>
                    <button class="btn btn-secondary" onclick="app.closeModal()">
                        取消添加
                    </button>
                    <button class="btn btn-warning" onclick="app.forceAddAsset()">
                        仍然添加（可能产生重复）
                    </button>
                    <button class="btn btn-primary" onclick="app.jumpToExistingAsset('${existingAsset.id}')">
                        查看现有资产
                    </button>
                </div>
            </div>
        `;

        this.showModal(content);
    }

    /**
     * 创建编辑字段的界面
     * @param {number} assetId 资产ID
     * @param {string} fieldName 字段名
     * @param {any} currentValue 当前值
     * @param {string} fieldType 字段类型
     */
    createEditField(assetId, fieldName, currentValue, fieldType = 'text') {
        const fieldElement = document.querySelector(`[data-asset-id="${assetId}"] .field-${fieldName}`);
        if (!fieldElement) return;

        // 保存原始内容
        const originalContent = fieldElement.innerHTML;
        
        let inputElement;
        if (fieldType === 'select' && fieldName === 'tags') {
            // 特殊处理标签选择
            inputElement = this.createTagsEditor(currentValue);
        } else if (fieldType === 'textarea') {
            inputElement = document.createElement('textarea');
            inputElement.value = currentValue || '';
            inputElement.className = 'edit-input';
        } else {
            inputElement = document.createElement('input');
            inputElement.type = fieldType;
            inputElement.value = currentValue || '';
            inputElement.className = 'edit-input';
        }

        const actionsHtml = `
            <div class="edit-actions">
                <button class="btn btn-small btn-success save-btn" data-asset-id="${assetId}" data-field="${fieldName}">
                    💾 保存
                </button>
                <button class="btn btn-small btn-secondary cancel-btn">
                    ❌ 取消
                </button>
            </div>
        `;

        fieldElement.innerHTML = '';
        fieldElement.appendChild(inputElement);
        fieldElement.insertAdjacentHTML('beforeend', actionsHtml);

        // 绑定事件
        const saveBtn = fieldElement.querySelector('.save-btn');
        const cancelBtn = fieldElement.querySelector('.cancel-btn');

        saveBtn.addEventListener('click', () => {
            const newValue = inputElement.value;
            // 触发保存事件
            const event = new CustomEvent('fieldSave', {
                detail: { assetId, fieldName, newValue, fieldElement }
            });
            document.dispatchEvent(event);
        });

        cancelBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            fieldElement.innerHTML = originalContent;
        });

        // 支持ESC键取消编辑
        inputElement.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                e.preventDefault();
                fieldElement.innerHTML = originalContent;
            } else if (e.key === 'Enter' && fieldType !== 'textarea') {
                e.preventDefault();
                saveBtn.click();
            }
        });

        // 聚焦输入框
        inputElement.focus();
        if (inputElement.select) {
            inputElement.select();
        }
    }

    /**
     * 创建标签编辑器
     * @param {Array} currentTags 当前标签
     * @returns {HTMLElement} 标签编辑器元素
     */
    createTagsEditor(currentTags) {
        const container = document.createElement('div');
        container.className = 'tags-editor';
        
        const input = document.createElement('input');
        input.type = 'text';
        input.value = Array.isArray(currentTags) ? currentTags.join(', ') : (currentTags || '');
        input.placeholder = '输入标签，用逗号分隔';
        input.className = 'edit-input';
        
        container.appendChild(input);
        return container;
    }

    /**
     * 处理键盘快捷键
     * @param {KeyboardEvent} event 键盘事件
     */
    handleKeyboardShortcuts(event) {
        // Esc键关闭模态框
        if (event.key === 'Escape') {
            this.closeModal();
        }
        
        // Ctrl/Cmd + R 刷新数据
        if ((event.ctrlKey || event.metaKey) && event.key === 'r') {
            event.preventDefault();
            // 触发刷新事件
            const refreshEvent = new CustomEvent('appRefresh');
            document.dispatchEvent(refreshEvent);
        }
    }
} 
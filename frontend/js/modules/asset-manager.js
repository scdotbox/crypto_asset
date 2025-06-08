/**
 * 资产管理器模块
 * 
 * 统一管理资产的增删改查、渲染、筛选等核心业务逻辑
 */

import { CONFIG, MESSAGES } from './config.js';
import { formatAddress, formatChainName, getChainIcon, formatNumber, debounce } from './utils.js';

export class AssetManager {
    constructor(apiService, uiManager, validationService) {
        this.apiService = apiService;
        this.uiManager = uiManager;
        this.validationService = validationService;
        
        this.assets = [];
        this.filteredAssets = [];
        this.walletNames = [];
        
        // 缓存DOM元素
        this.tableBody = null;
        this.cardsContainer = null;
        this.summaryElement = null;
        
        this.init();
    }

    /**
     * 初始化资产管理器
     */
    init() {
        this.bindEvents();
        this.cacheDOMElements();
        this.loadTokenOptions();
    }

    /**
     * 缓存常用DOM元素
     */
    cacheDOMElements() {
        this.tableBody = document.getElementById('assetsTableBody');
        this.cardsContainer = document.getElementById('assetsGrid');
        this.summaryElement = document.getElementById('assetSummary');
    }

    /**
     * 绑定事件监听器
     */
    bindEvents() {
        // 表单提交事件
        const addAssetForm = document.getElementById('addAssetForm');
        if (addAssetForm) {
            addAssetForm.addEventListener('submit', this.handleAddAssetFormSubmit.bind(this));
        }

        // 筛选事件
        this.bindFilterEvents();

        // 批量操作事件
        this.bindBatchOperationEvents();

        // 自定义事件监听
        document.addEventListener('fieldSave', this.handleFieldSave.bind(this));
        document.addEventListener('appRefresh', this.loadAssets.bind(this));

        // 使用事件委托处理删除按钮点击
        document.addEventListener('click', (event) => {
            if (event.target.matches('.btn-delete-asset') || event.target.closest('.btn-delete-asset')) {
                const button = event.target.matches('.btn-delete-asset') ? event.target : event.target.closest('.btn-delete-asset');
                const assetId = button.dataset.assetId;
                console.log('删除按钮被点击，资产ID:', assetId, '类型:', typeof assetId);
                if (assetId) {
                    event.preventDefault();
                    event.stopPropagation();
                    this.deleteAsset(assetId);
                } else {
                    console.error('未找到有效的资产ID，原始值:', button.dataset.assetId);
                }
            }
        });

        // 使用事件委托处理编辑按钮点击 - 增强调试
        document.addEventListener('click', (event) => {
            console.log('点击事件触发:', event.target);
            
            // 检查是否点击了编辑按钮
            const editButton = event.target.matches('.btn-edit-field') ? event.target : event.target.closest('.btn-edit-field');
            
            if (editButton) {
                console.log('检测到编辑按钮点击:', editButton);
                
                const assetId = editButton.dataset.assetId;
                const fieldName = editButton.dataset.fieldName;
                const currentValue = editButton.dataset.currentValue || '';
                const fieldType = editButton.dataset.fieldType || 'text';
                
                console.log('编辑按钮数据:', { 
                    assetId, 
                    fieldName, 
                    currentValue, 
                    fieldType,
                    allDatasets: editButton.dataset 
                });
                
                if (assetId && fieldName) {
                    event.preventDefault();
                    event.stopPropagation();
                    console.log('准备调用editField方法');
                    this.editField(assetId, fieldName, currentValue, fieldType);
                } else {
                    console.error('编辑按钮缺少必要的数据属性:', { 
                        assetId, 
                        fieldName,
                        buttonHTML: editButton.outerHTML 
                    });
                    this.uiManager.showNotification('编辑按钮配置错误', 'error');
                }
            }
        });

        // 刷新价格按钮
        const refreshPricesBtn = document.getElementById('refreshPricesBtn');
        if (refreshPricesBtn) {
            refreshPricesBtn.addEventListener('click', this.handleRefreshPrices.bind(this));
        }

        // 刷新代币按钮
        const refreshTokensBtn = document.getElementById('refreshTokensBtn');
        if (refreshTokensBtn) {
            refreshTokensBtn.addEventListener('click', this.loadTokenOptions.bind(this));
        }

        // 链选择变化时重新加载代币选项
        const chainSelect = document.querySelector('select[name="chainName"]');
        if (chainSelect) {
            chainSelect.addEventListener('change', this.loadTokenOptions.bind(this));
        }
    }

    /**
     * 绑定筛选事件
     */
    bindFilterEvents() {
        const chainFilter = document.getElementById('chainFilter');
        const addressFilter = document.getElementById('addressFilter');
        const walletNameFilter = document.getElementById('walletNameFilter');

        if (chainFilter) {
            chainFilter.addEventListener('change', this.applyFilters.bind(this));
        }

        if (addressFilter) {
            addressFilter.addEventListener('input', 
                debounce(this.applyFilters.bind(this), CONFIG.UI.DEBOUNCE_DELAY)
            );
        }

        if (walletNameFilter) {
            walletNameFilter.addEventListener('change', this.applyFilters.bind(this));
        }
    }

    /**
     * 绑定批量操作事件
     */
    bindBatchOperationEvents() {
        const selectAllBtn = document.getElementById('selectAllBtn');
        const batchEditBtn = document.getElementById('batchEditBtn');
        const batchDeleteBtn = document.getElementById('batchDeleteBtn');

        if (selectAllBtn) {
            selectAllBtn.addEventListener('click', () => {
                this.uiManager.selectAll(this.filteredAssets);
            });
        }

        if (batchEditBtn) {
            batchEditBtn.addEventListener('click', this.handleBatchEdit.bind(this));
        }

        if (batchDeleteBtn) {
            batchDeleteBtn.addEventListener('click', this.handleBatchDelete.bind(this));
        }
    }

    /**
     * 加载资产数据
     */
    async loadAssets() {
        this.uiManager.showLoading(true);
        this.uiManager.showEmptyState(false);

        try {
            this.assets = await this.apiService.fetchAssets();
            this.filteredAssets = [...this.assets];
            
            this.renderAssets();
            this.updateSummary();
            this.loadWalletNames();
            
            this.uiManager.showEmptyState(this.assets.length === 0);
            
        } catch (error) {
            console.error('加载资产失败:', error);
            this.uiManager.showNotification(MESSAGES.ERROR.DATA_LOAD_FAILED + ': ' + error.message, 'error');
            this.uiManager.showEmptyState(true);
        } finally {
            this.uiManager.showLoading(false);
        }
    }

    /**
     * 添加资产表单提交处理
     * @param {Event} event 表单提交事件
     */
    async handleAddAssetFormSubmit(event) {
        event.preventDefault();
        
        const formData = new FormData(event.target);
        const selectedToken = formData.get('tokenSelect');
        
        // 解析选中的代币信息
        let tokenSymbol, tokenContract;
        if (selectedToken) {
            const [symbol, contract] = selectedToken.split('|');
            tokenSymbol = symbol;
            tokenContract = contract === 'null' ? null : contract;
        }
        
        const assetData = {
            address: formData.get('address')?.trim(),
            chain_name: formData.get('chainName'),
            token_symbol: tokenSymbol,
            token_contract_address: tokenContract,
            wallet_name: formData.get('walletName')?.trim() || null,
            tag: formData.get('tags')?.trim() || null,
            notes: formData.get('notes')?.trim() || null
        };

        // 同时更新合约地址显示字段
        const contractInput = document.querySelector('input[name="tokenContract"]');
        if (contractInput) {
            contractInput.value = tokenContract || '';
        }

        // 验证输入数据
        if (!this.validationService.validateAssetInput(assetData)) {
            const errors = this.validationService.getErrorsAsString();
            this.uiManager.showNotification('输入数据无效:\n' + errors, 'error');
            return;
        }

        try {
            // 添加资产（后端会自动处理重复检查）
            const result = await this.apiService.addAsset(assetData);
            
            if (result.is_duplicate) {
                // 资产已存在，显示信息通知
                this.uiManager.showNotification('资产已存在，已返回现有资产信息', 'info');
            } else {
                // 新资产添加成功
                this.uiManager.showNotification(MESSAGES.SUCCESS.ASSET_ADDED, 'success');
            }
            
            // 重新加载资产列表
            await this.loadAssets();
            
            // 重置表单
            event.target.reset();
            
        } catch (error) {
            console.error('添加资产失败:', error);
            
            // 检查是否是UNIQUE约束错误
            if (error.message && error.message.includes('UNIQUE constraint failed')) {
                this.uiManager.showNotification('资产已存在，无法重复添加', 'warning');
            } else if (error.message && error.message.includes('不支持的区块链')) {
                this.uiManager.showNotification('不支持该区块链，请选择其他链', 'error');
            } else if (error.message && error.message.includes('地址格式无效')) {
                this.uiManager.showNotification('地址格式无效，请检查输入', 'error');
            } else {
                // 其他错误
                this.uiManager.showNotification(MESSAGES.ERROR.ASSET_ADD_FAILED + ': ' + error.message, 'error');
            }
        }
    }

    /**
     * 删除资产
     * @param {string} assetId 资产ID
     */
    async deleteAsset(assetId) {
        console.log('deleteAsset被调用，资产ID:', assetId, '类型:', typeof assetId);
        
        // 确保assetId存在且有效
        if (!assetId) {
            console.error('无效的资产ID:', assetId);
            this.uiManager.showNotification('无效的资产ID', 'error');
            return;
        }
        
        // 将assetId转换为字符串（如果不是的话）
        const stringAssetId = String(assetId);
        
        // 查找资产
        const asset = this.assets.find(a => a.id === stringAssetId);
        if (!asset) {
            console.error('未找到指定的资产:', stringAssetId);
            this.uiManager.showNotification('未找到指定的资产', 'error');
            return;
        }

        console.log('找到资产，准备显示确认对话框:', asset);
        const confirmed = await this.uiManager.showConfirmationDialog({
            title: '确认删除资产',
            message: `确定要删除资产 "${asset.token_symbol}" (${formatAddress(asset.address)}) 吗？\n\n此操作不可撤销。`,
            confirmText: '删除',
            cancelText: '取消',
            type: 'danger'
        });

        console.log('确认对话框结果:', confirmed);
        if (!confirmed) {
            console.log('用户取消删除操作');
            return;
        }

        try {
            console.log('开始删除资产，ID:', stringAssetId);
            await this.apiService.deleteAsset(stringAssetId);
            this.uiManager.showNotification(MESSAGES.SUCCESS.ASSET_DELETED, 'success');
            await this.loadAssets();
            console.log('资产删除成功');
        } catch (error) {
            console.error('删除资产失败:', error);
            this.uiManager.showNotification(MESSAGES.ERROR.ASSET_DELETE_FAILED + ': ' + error.message, 'error');
        }
    }

    /**
     * 批量删除资产
     */
    async handleBatchDelete() {
        if (this.uiManager.selectedAssets.size === 0) {
            this.uiManager.showNotification('请先选择要删除的资产', 'warning');
            return;
        }

        const confirmed = await this.uiManager.showConfirmationDialog({
            title: '批量删除资产',
            message: `确定要删除选中的 ${this.uiManager.selectedAssets.size} 个资产吗？此操作不可撤销。`,
            confirmText: '删除',
            type: 'danger'
        });

        if (!confirmed) return;

        try {
            const assetIds = Array.from(this.uiManager.selectedAssets);
            await this.apiService.batchDeleteAssets(assetIds);
            
            this.uiManager.showNotification(`成功删除 ${assetIds.length} 个资产`, 'success');
            this.uiManager.cancelSelectMode();
            await this.loadAssets();
            
        } catch (error) {
            console.error('批量删除失败:', error);
            this.uiManager.showNotification('批量删除失败: ' + error.message, 'error');
        }
    }

    /**
     * 批量编辑资产
     */
    async handleBatchEdit() {
        if (this.uiManager.selectedAssets.size === 0) {
            this.uiManager.showNotification('请先选择要编辑的资产', 'warning');
            return;
        }

        const selectedAssets = this.assets.filter(asset => 
            this.uiManager.selectedAssets.has(asset.id)
        );

        this.showBatchEditModal(selectedAssets);
    }

    /**
     * 显示批量编辑模态框
     * @param {Array} assets 选中的资产列表
     */
    showBatchEditModal(assets) {
        const content = `
            <div class="batch-edit-modal">
                <h3>批量编辑资产</h3>
                <p>选中了 ${assets.length} 个资产进行批量编辑</p>
                
                <form id="batchEditForm" class="batch-edit-form">
                    <div class="form-group">
                        <label for="batchWalletName">钱包名称:</label>
                        <input type="text" id="batchWalletName" name="walletName" maxlength="50">
                        <small>留空表示不修改</small>
                    </div>
                    
                    <div class="form-group">
                        <label for="batchTags">标签:</label>
                        <input type="text" id="batchTags" name="tags" placeholder="用逗号分隔多个标签">
                        <small>留空表示不修改</small>
                    </div>
                    
                    <div class="form-group">
                        <label for="batchNotes">备注:</label>
                        <textarea id="batchNotes" name="notes" maxlength="500" rows="3"></textarea>
                        <small>留空表示不修改</small>
                    </div>
                    
                    <div class="form-actions">
                        <button type="button" class="btn btn-secondary" onclick="app.uiManager.closeModal()">取消</button>
                        <button type="submit" class="btn btn-primary">保存修改</button>
                    </div>
                </form>
            </div>
        `;

        this.uiManager.showModal(content);

        // 绑定表单提交事件
        const form = document.getElementById('batchEditForm');
        form.addEventListener('submit', (event) => {
            this.handleBatchEditSubmit(event, assets);
        });
    }

    /**
     * 处理批量编辑表单提交
     * @param {Event} event 表单事件
     * @param {Array} assets 资产列表
     */
    async handleBatchEditSubmit(event, assets) {
        event.preventDefault();
        
        const formData = new FormData(event.target);
        const updateData = {};
        
        // 收集非空的更新数据
        const walletName = formData.get('walletName')?.trim();
        const tags = formData.get('tags')?.trim();
        const notes = formData.get('notes')?.trim();
        
        if (walletName) updateData.walletName = walletName;
        if (tags) updateData.tags = tags.split(',').map(tag => tag.trim()).filter(tag => tag);
        if (notes) updateData.notes = notes;
        
        if (Object.keys(updateData).length === 0) {
            this.uiManager.showNotification('请至少修改一个字段', 'warning');
            return;
        }

        // 验证更新数据
        if (!this.validationService.validateBatchEditData(updateData)) {
            const errors = this.validationService.getErrorsAsString();
            this.uiManager.showNotification('输入数据无效:\n' + errors, 'error');
            return;
        }

        try {
            const assetIds = assets.map(asset => asset.id);
            await this.apiService.batchUpdateAssets(assetIds, updateData);
            
            this.uiManager.closeModal();
            this.uiManager.showNotification(`成功更新 ${assetIds.length} 个资产`, 'success');
            this.uiManager.cancelSelectMode();
            await this.loadAssets();
            
        } catch (error) {
            console.error('批量编辑失败:', error);
            this.uiManager.showNotification('批量编辑失败: ' + error.message, 'error');
        }
    }

    /**
     * 处理字段保存事件
     * @param {CustomEvent} event 自定义保存事件
     */
    async handleFieldSave(event) {
        const { assetId, fieldName, newValue, fieldElement } = event.detail;
        
        try {
            // 字段名映射 - 将前端字段名映射到后端API字段名
            const fieldMapping = {
                'walletName': 'wallet_name',
                'amount': 'quantity',
                'notes': 'notes',
                'tags': 'tags'
            };
            
            const apiFieldName = fieldMapping[fieldName] || fieldName;
            const updateData = { [apiFieldName]: newValue };
            
            // 特殊处理标签字段
            if (fieldName === 'tags') {
                updateData.tags = newValue.split(',').map(tag => tag.trim()).filter(tag => tag);
            }
            
            // 特殊处理数量字段
            if (fieldName === 'amount') {
                const numValue = parseFloat(newValue);
                if (isNaN(numValue) || numValue < 0) {
                    throw new Error('数量必须是有效的正数');
                }
                updateData.quantity = numValue;
            }
            
            console.log('更新字段数据:', { assetId, fieldName, apiFieldName, updateData });
            
            await this.apiService.updateAsset(assetId, updateData);
            
            this.uiManager.showNotification('字段更新成功', 'success', 2000);
            
            // 重新加载资产数据
            await this.loadAssets();
            
        } catch (error) {
            console.error('保存字段失败:', error);
            this.uiManager.showNotification('保存失败: ' + error.message, 'error');
            
            // 恢复原始内容
            const asset = this.assets.find(a => a.id === assetId);
            if (asset && fieldElement) {
                fieldElement.innerHTML = this.getFieldDisplayValue(asset, fieldName);
            }
        }
    }

    /**
     * 获取字段显示值
     * @param {Object} asset 资产对象
     * @param {string} fieldName 字段名
     * @returns {string} 显示值
     */
    getFieldDisplayValue(asset, fieldName) {
        switch (fieldName) {
            case 'walletName':
                return asset.wallet_name || '未设置';
            case 'tags':
                return asset.tags && asset.tags.length > 0 
                    ? asset.tags.map(tag => `<span class="tag">${tag}</span>`).join('') 
                    : '无标签';
            case 'notes':
                return asset.notes || '无备注';
            default:
                return asset[fieldName] || '';
        }
    }

    /**
     * 应用筛选条件
     */
    applyFilters() {
        const chainFilter = document.getElementById('chainFilter')?.value || '';
        const addressFilter = document.getElementById('addressFilter')?.value?.trim().toLowerCase() || '';
        const walletNameFilter = document.getElementById('walletNameFilter')?.value || '';

        this.filteredAssets = this.assets.filter(asset => {
            // 链筛选
            if (chainFilter && asset.chain_name !== chainFilter) {
                return false;
            }

            // 地址筛选
            if (addressFilter && !asset.address.toLowerCase().includes(addressFilter)) {
                return false;
            }

            // 钱包名称筛选
            if (walletNameFilter && asset.wallet_name !== walletNameFilter) {
                return false;
            }

            return true;
        });

        this.renderAssets();
        this.updateSummary();
        this.uiManager.showEmptyState(this.filteredAssets.length === 0 && this.assets.length > 0);
    }

    /**
     * 清除筛选条件
     */
    clearFilters() {
        const chainFilter = document.getElementById('chainFilter');
        const addressFilter = document.getElementById('addressFilter');
        const walletNameFilter = document.getElementById('walletNameFilter');

        if (chainFilter) chainFilter.value = '';
        if (addressFilter) addressFilter.value = '';
        if (walletNameFilter) walletNameFilter.value = '';

        this.filteredAssets = [...this.assets];
        this.renderAssets();
        this.updateSummary();
        this.uiManager.showEmptyState(false);
    }

    /**
     * 渲染资产列表
     */
    renderAssets() {
        if (this.uiManager.currentView === 'table') {
            this.renderAssetsTable();
        } else {
            this.renderAssetsCards();
        }
        
        // 同时更新图表（如果图表管理器存在）
        if (window.app && window.app.chartManager) {
            window.app.chartManager.updateDistributionChart(this.filteredAssets);
        }
    }

    /**
     * 渲染表格视图
     */
    renderAssetsTable() {
        if (!this.tableBody) return;

        this.tableBody.innerHTML = '';

        this.filteredAssets.forEach(asset => {
            const row = this.createAssetTableRow(asset);
            this.tableBody.appendChild(row);
        });

        // 更新选择状态
        if (this.uiManager.isSelectMode) {
            this.uiManager.updateSelectModeUI();
        }
    }

    /**
     * 创建资产表格行
     * @param {Object} asset 资产对象
     * @returns {HTMLTableRowElement} 表格行元素
     */
    createAssetTableRow(asset) {
        const row = document.createElement('tr');
        row.className = 'asset-row';
        row.dataset.assetId = asset.id;

        const isSelected = this.uiManager.selectedAssets.has(asset.id);
        if (isSelected) {
            row.classList.add('selected');
        }

        // 确保所有数据属性都正确设置
        const walletNameValue = asset.wallet_name || '';
        const quantityValue = asset.quantity || 0;
        const notesValue = asset.notes || '';

        row.innerHTML = `
            <td class="field-address">
                <div class="address-container">
                    ${this.uiManager.isSelectMode ? `
                        <div class="asset-checkbox" style="display: inline-block; margin-right: 8px;">
                            <input type="checkbox" ${isSelected ? 'checked' : ''} 
                                   onchange="app.uiManager.toggleAssetSelection('${asset.id}')">
                        </div>
                    ` : ''}
                    <span class="chain-icon">${getChainIcon(asset.chain_name)}</span>
                    <span class="address-text">${formatAddress(asset.address)}</span>
                    <button class="btn btn-small btn-secondary" onclick="event.stopPropagation(); app.copyToClipboard('${asset.address}')">
                        📋
                    </button>
                </div>
            </td>
            <td class="field-chain">${formatChainName(asset.chain_name)}</td>
            <td class="field-token">${asset.token_symbol}</td>
            <td class="field-walletName">
                <div class="field-content">
                    <span class="field-value">${walletNameValue || '未设置'}</span>
                    <button class="btn btn-small btn-edit-field" 
                            data-asset-id="${asset.id}" 
                            data-field-name="walletName" 
                            data-current-value="${walletNameValue}" 
                            data-field-type="text"
                            title="编辑钱包名称">
                        ✏️
                    </button>
                </div>
            </td>
            <td class="field-amount">
                <div class="field-content">
                    <span class="field-value">${formatNumber(quantityValue)}</span>
                    <button class="btn btn-small btn-edit-field" 
                            data-asset-id="${asset.id}" 
                            data-field-name="amount" 
                            data-current-value="${quantityValue}" 
                            data-field-type="number" 
                            title="编辑数量">
                        ✏️
                    </button>
                </div>
            </td>
            <td class="field-price">$${formatNumber(asset.price_usdc || 0)}</td>
            <td class="field-value">$${formatNumber(asset.value_usdc || 0)}</td>
            <td class="field-notes">
                <div class="field-content">
                    <span class="field-value">${notesValue || '无备注'}</span>
                    <button class="btn btn-small btn-edit-field" 
                            data-asset-id="${asset.id}" 
                            data-field-name="notes" 
                            data-current-value="${notesValue}" 
                            data-field-type="text"
                            title="编辑备注">
                        ✏️
                    </button>
                </div>
            </td>
            <td class="actions-cell">
                <button class="btn btn-small btn-danger btn-delete-asset" data-asset-id="${asset.id}">
                    🗑️删除
                </button>
            </td>
        `;

        return row;
    }

    /**
     * 渲染卡片视图
     */
    renderAssetsCards() {
        if (!this.cardsContainer) return;

        this.cardsContainer.innerHTML = '';

        this.filteredAssets.forEach(asset => {
            const card = this.createAssetCard(asset);
            this.cardsContainer.appendChild(card);
        });
    }

    /**
     * 创建资产卡片
     * @param {Object} asset 资产对象
     * @returns {HTMLDivElement} 卡片元素
     */
    createAssetCard(asset) {
        const card = document.createElement('div');
        card.className = 'asset-card';
        card.dataset.assetId = asset.id;

        const isSelected = this.uiManager.selectedAssets.has(asset.id);
        if (isSelected) {
            card.classList.add('selected');
        }

        card.innerHTML = `
            <div class="card-header">
                <div class="asset-checkbox" style="display: ${this.uiManager.isSelectMode ? 'inline-block' : 'none'}">
                    <input type="checkbox" ${isSelected ? 'checked' : ''} 
                           onchange="app.uiManager.toggleAssetSelection('${asset.id}')">
                </div>
                <div class="asset-chain">
                    <span class="chain-icon">${getChainIcon(asset.chain_name)}</span>
                    <span class="chain-name">${formatChainName(asset.chain_name)}</span>
                </div>
                <div class="asset-token">${asset.token_symbol}</div>
            </div>
            
            <div class="card-body">
                <div class="asset-address">
                    <label>地址:</label>
                    <span>${formatAddress(asset.address)}</span>
                    <button class="btn btn-small btn-secondary" onclick="app.copyToClipboard('${asset.address}')">
                        📋
                    </button>
                </div>
                
                <div class="asset-amount">
                    <label>数量:</label>
                    <span>${formatNumber(asset.quantity)} ${asset.token_symbol}</span>
                </div>
                
                <div class="asset-value">
                    <label>价值:</label>
                    <span class="value-amount">$${formatNumber(asset.value_usdc)}</span>
                </div>
                
                ${asset.wallet_name ? `
                    <div class="asset-wallet">
                        <label>钱包:</label>
                        <span>${asset.wallet_name}</span>
                    </div>
                ` : ''}
                
                ${asset.tags && asset.tags.length > 0 ? `
                    <div class="asset-tags">
                        <label>标签:</label>
                        <span>${asset.tags.map(tag => `<span class="tag">${tag}</span>`).join('')}</span>
                    </div>
                ` : ''}
            </div>
            
            <div class="card-actions">
                <button class="btn btn-small btn-primary" onclick="app.assetManager.editAsset('${asset.id}')">
                    ✏️ 编辑
                </button>
                <button class="btn btn-small btn-danger btn-delete-asset" data-asset-id="${asset.id}">
                    🗑️ 删除
                </button>
            </div>
        `;

        return card;
    }

    /**
     * 编辑字段
     * @param {string} assetId 资产ID
     * @param {string} fieldName 字段名
     * @param {any} currentValue 当前值
     * @param {string} fieldType 字段类型
     */
    editField(assetId, fieldName, currentValue, fieldType = 'text') {
        console.log('editField被调用:', { assetId, fieldName, currentValue, fieldType });
        
        // 检查UI管理器是否存在
        if (!this.uiManager || typeof this.uiManager.createEditField !== 'function') {
            console.error('UI管理器或createEditField方法不存在');
            this.uiManager.showNotification('编辑功能暂时不可用', 'error');
            return;
        }
        
        try {
            // 调用UI管理器的编辑字段方法
            this.uiManager.createEditField(assetId, fieldName, currentValue, fieldType);
        } catch (error) {
            console.error('创建编辑字段失败:', error);
            this.uiManager.showNotification('创建编辑字段失败: ' + error.message, 'error');
        }
    }

    /**
     * 更新汇总信息
     */
    updateSummary() {
        const totalAssets = this.filteredAssets.length;
        const totalValue = this.filteredAssets.reduce((sum, asset) => sum + (asset.value_usdc || 0), 0);
        const uniqueChains = new Set(this.filteredAssets.map(asset => asset.chain_name)).size;

        // 更新页面顶部的汇总卡片
        const totalValueElement = document.getElementById('totalValue');
        const totalCountElement = document.getElementById('totalCount');
        const chainCountElement = document.getElementById('chainCount');

        if (totalValueElement) {
            totalValueElement.textContent = `$${formatNumber(totalValue)}`;
        }

        if (totalCountElement) {
            totalCountElement.textContent = totalAssets.toString();
        }

        if (chainCountElement) {
            chainCountElement.textContent = uniqueChains.toString();
        }

        // 如果存在汇总元素容器，也更新它
        if (this.summaryElement) {
            this.summaryElement.innerHTML = `
                <div class="summary-item">
                    <span class="summary-label">总资产:</span>
                    <span class="summary-value">${totalAssets}</span>
                </div>
                <div class="summary-item">
                    <span class="summary-label">总价值:</span>
                    <span class="summary-value">$${formatNumber(totalValue)}</span>
                </div>
                <div class="summary-item">
                    <span class="summary-label">链数量:</span>
                    <span class="summary-value">${uniqueChains}</span>
                </div>
            `;
        }
    }



    /**
     * 加载钱包名称列表
     */
    async loadWalletNames() {
        try {
            this.walletNames = await this.apiService.getWalletNames();
            this.updateWalletNameOptions();
        } catch (error) {
            console.error('加载钱包名称失败:', error);
        }
    }

    /**
     * 更新钱包名称选项
     */
    updateWalletNameOptions() {
        const walletNameFilter = document.getElementById('walletNameFilter');
        if (!walletNameFilter) return;

        // 保存当前选择
        const currentValue = walletNameFilter.value;
        
        // 清空并重新填充选项
        walletNameFilter.innerHTML = '<option value="">所有钱包</option>';
        
        this.walletNames.forEach(walletName => {
            const option = document.createElement('option');
            option.value = walletName;
            option.textContent = walletName;
            if (walletName === currentValue) {
                option.selected = true;
            }
            walletNameFilter.appendChild(option);
        });
    }



    /**
     * 刷新资产价格
     */
    async handleRefreshPrices() {
        const btn = document.getElementById('refreshPricesBtn');
        const btnText = btn?.querySelector('.btn-text');
        const btnLoading = btn?.querySelector('.btn-loading');

        try {
            // 显示加载状态
            if (btnText) btnText.style.display = 'none';
            if (btnLoading) btnLoading.style.display = 'inline';
            if (btn) btn.disabled = true;

            // 调用API刷新价格
            const result = await this.apiService.refreshAssetPrices();
            
            this.uiManager.showNotification(result.message, 'success');
            
            // 重新加载资产列表以显示更新的价格
            await this.loadAssets();

        } catch (error) {
            console.error('刷新价格失败:', error);
            this.uiManager.showNotification('刷新价格失败: ' + error.message, 'error');
        } finally {
            // 恢复按钮状态
            if (btnText) btnText.style.display = 'inline';
            if (btnLoading) btnLoading.style.display = 'none';
            if (btn) btn.disabled = false;
        }
    }

    /**
     * 加载代币选项
     */
    async loadTokenOptions() {
        const tokenSelect = document.getElementById('tokenSelect');
        const chainSelect = document.querySelector('select[name="chainName"]');
        
        if (!tokenSelect) return;

        try {
            // 获取选中的链
            const selectedChain = chainSelect?.value;
            
            // 获取代币库数据
            const tokens = await this.apiService.getTokenLibrary();
            
            // 清空现有选项
            tokenSelect.innerHTML = '<option value="">请选择代币...</option>';
            
            // 过滤代币（如果选择了特定链）
            const filteredTokens = selectedChain 
                ? tokens.filter(token => token.chain_name === selectedChain)
                : tokens;
            
            // 按链和符号排序
            filteredTokens.sort((a, b) => {
                if (a.chain_name !== b.chain_name) {
                    return a.chain_name.localeCompare(b.chain_name);
                }
                return a.symbol.localeCompare(b.symbol);
            });
            
            // 添加代币选项
            filteredTokens.forEach(token => {
                const option = document.createElement('option');
                option.value = `${token.symbol}|${token.contract_address || 'null'}`;
                option.textContent = `${token.symbol} - ${token.name} (${token.chain_name})`;
                tokenSelect.appendChild(option);
            });
            
            // 绑定选择变化事件，更新合约地址显示
            tokenSelect.addEventListener('change', this.handleTokenSelectChange.bind(this));
            
            this.uiManager.showNotification(`已加载 ${filteredTokens.length} 个代币选项`, 'success', 2000);
            
        } catch (error) {
            console.error('加载代币选项失败:', error);
            this.uiManager.showNotification('加载代币选项失败: ' + error.message, 'error');
        }
    }

    /**
     * 处理代币选择变化
     */
    handleTokenSelectChange() {
        const tokenSelect = document.getElementById('tokenSelect');
        const contractInput = document.querySelector('input[name="tokenContract"]');
        
        if (!tokenSelect || !contractInput) return;
        
        const selectedValue = tokenSelect.value;
        if (selectedValue) {
            const [symbol, contract] = selectedValue.split('|');
            contractInput.value = contract === 'null' ? '' : contract;
        } else {
            contractInput.value = '';
        }
    }
} 
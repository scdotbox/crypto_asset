/**
 * 主应用文件，整合所有功能模块
 */

import { ApiService } from './modules/api-service.js';
import { ValidationService } from './modules/validation-service.js';
import { UIManager } from './modules/ui-manager.js';
import { AssetManager } from './modules/asset-manager.js';
import { ChartManager } from './modules/chart-manager.js';
import { copyToClipboard } from './modules/utils.js';

/**
 * 主应用类
 */
class CryptoAssetManagerModular {
    constructor() {
        // 初始化服务层
        this.apiService = new ApiService();
        this.validationService = new ValidationService();
        this.uiManager = new UIManager();

        // 初始化功能模块
        this.assetManager = new AssetManager(this.apiService, this.uiManager, this.validationService);
        this.chartManager = new ChartManager(this.apiService, this.uiManager);



        // 代币库管理状态
        this.tokens = [];
        this.filteredTokens = [];
        this.isTokenLibraryVisible = false;
    }

    /**
     * 异步初始化方法
     */
    async initialize() {
        return await this.init();
    }

    /**
     * 初始化应用
     */
    async init() {
        try {
            console.log('🚀 初始化加密货币资产管理...');

            // 初始化核心模块
            this.initModules();

            // 加载初始数据（增加错误处理）
            await this.loadInitialDataWithRetry();

            console.log('✅ 应用初始化完成');

        } catch (error) {
            console.error('❌ 应用初始化失败:', error);
            this.uiManager.showNotification('应用初始化失败: ' + error.message, 'error');
        }
    }

    /**
     * 加载初始数据（带重试机制）
     */
    async loadInitialDataWithRetry() {
        const maxRetries = 3;
        let attempt = 1;

        while (attempt <= maxRetries) {
            try {
                console.log(`🔄 尝试加载数据（第${attempt}次）...`);

                // 测试API连接
                const healthResponse = await fetch(`${this.apiService.baseUrl.replace('/api', '')}/health`, {
                    method: 'GET',
                    timeout: 5000
                });

                if (healthResponse.ok) {
                    console.log('✅ API连接正常');
                } else {
                    throw new Error(`API连接失败: ${healthResponse.status}`);
                }

                // 并行加载基础数据
                await Promise.all([
                    this.assetManager.loadAssets(),
                    this.loadDatabaseStats()
                ]);

                console.log('✅ 初始数据加载完成');
                return; // 成功后退出重试循环

            } catch (error) {
                console.error(`❌ 第${attempt}次加载失败:`, error);

                if (attempt === maxRetries) {
                    // 最后一次尝试失败，显示错误信息
                    this.uiManager.showNotification(
                        `数据加载失败（已尝试${maxRetries}次）: ${error.message}`,
                        'error'
                    );
                    throw error;
                } else {
                    // 等待2秒后重试
                    console.log(`⏳ 等待2秒后重试...`);
                    await new Promise(resolve => setTimeout(resolve, 2000));
                }

                attempt++;
            }
        }
    }

    /**
     * 初始化应用
     */
    initModules() {
        console.log('🔧 initModules - document.readyState:', document.readyState);
        // 确保DOM完全加载后再绑定事件
        if (document.readyState === 'loading') {
            console.log('🔧 DOM 还在加载中，等待 DOMContentLoaded 事件');
            document.addEventListener('DOMContentLoaded', () => {
                console.log('🔧 DOMContentLoaded 事件触发，开始初始化模块');
                // 延迟一点时间确保所有元素都已渲染
                setTimeout(() => {
                    this.bindGlobalEvents();
                    this.setupGlobalVariables();
                    this.initializeChartManager();
                }, 100);
            });
        } else {
            console.log('🔧 DOM 已加载完成，直接初始化模块');
            // 延迟一点时间确保所有元素都已渲染
            setTimeout(() => {
                this.bindGlobalEvents();
                this.setupGlobalVariables();
                this.initializeChartManager();
            }, 100);
        }
    }

    /**
     * 初始化图表管理器
     */
    async initializeChartManager() {
        try {
            console.log('🚀 开始初始化图表管理器...');
            // 初始化图表管理器
            this.chartManager.init();
            
            // 初始化趋势筛选器选项
            await this.chartManager.initTrendFilterOptions();
            
            console.log('✅ 图表管理器初始化完成');
        } catch (error) {
            console.error('❌ 图表管理器初始化失败:', error);
        }
    }

    /**
     * 绑定全局事件
     */
    bindGlobalEvents() {
        // 键盘快捷键
        document.addEventListener('keydown', this.uiManager.handleKeyboardShortcuts.bind(this.uiManager));

        // 视图切换
        const viewBtns = document.querySelectorAll('.view-btn');
        viewBtns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                const view = e.target.dataset.view;
                this.uiManager.switchView(view);
                this.assetManager.renderAssets();
            });
        });

        // 批量选择模式
        const selectModeBtn = document.getElementById('selectModeBtn');
        const cancelSelectBtn = document.getElementById('cancelSelectBtn');

        if (selectModeBtn) {
            selectModeBtn.addEventListener('click', () => {
                this.uiManager.toggleSelectMode();
            });
        }

        if (cancelSelectBtn) {
            cancelSelectBtn.addEventListener('click', () => {
                this.uiManager.cancelSelectMode();
            });
        }

        // 注意：刷新功能已合并到refreshPricesBtn中

        // 清除筛选按钮
        const clearFiltersBtn = document.getElementById('clearFiltersBtn');
        if (clearFiltersBtn) {
            clearFiltersBtn.addEventListener('click', () => {
                this.assetManager.clearFilters();
            });
        }

        // 代币库管理事件
        this.bindTokenLibraryEvents();

        // 数据库管理事件
        this.bindDatabaseManagementEvents();
    }



    /**
     * 绑定代币库管理事件
     */
    bindTokenLibraryEvents() {
        const tokenLibraryBtn = document.getElementById('toggleTokenLibraryBtn');
        if (tokenLibraryBtn) {
            tokenLibraryBtn.addEventListener('click', this.toggleTokenLibraryPanel.bind(this));
        }



        // 添加代币表单
        const addTokenForm = document.getElementById('addTokenForm');
        if (addTokenForm) {
            addTokenForm.addEventListener('submit', this.handleAddTokenFormSubmit.bind(this));
        }

        // 验证合约按钮
        const validateTokenBtn = document.getElementById('validateTokenBtn');
        if (validateTokenBtn) {
            validateTokenBtn.addEventListener('click', this.handleValidateContract.bind(this));
        }

        // 刷新代币列表按钮
        const refreshTokenListBtn = document.getElementById('refreshTokenListBtn');
        if (refreshTokenListBtn) {
            refreshTokenListBtn.addEventListener('click', this.loadTokenLibrary.bind(this));
        }

        // 代币筛选事件
        const tokenListChainFilter = document.getElementById('tokenListChainFilter');
        const tokenListTypeFilter = document.getElementById('tokenListTypeFilter');
        const tokenSearchInput = document.getElementById('tokenSearchInput');

        if (tokenListChainFilter) {
            tokenListChainFilter.addEventListener('change', this.filterTokenList.bind(this));
        }

        if (tokenListTypeFilter) {
            tokenListTypeFilter.addEventListener('change', this.filterTokenList.bind(this));
        }

        if (tokenSearchInput) {
            tokenSearchInput.addEventListener('input', this.filterTokenList.bind(this));
        }
    }

    /**
     * 绑定数据库管理事件
     */
    bindDatabaseManagementEvents() {
        const managementBtn = document.getElementById('toggleManagementBtn');
        if (managementBtn) {
            managementBtn.addEventListener('click', this.toggleManagementPanel.bind(this));
        }

        // 清空所有数据按钮
        const clearAllDataBtn = document.getElementById('clearAllDataBtn');
        if (clearAllDataBtn) {
            clearAllDataBtn.addEventListener('click', this.handleClearAllData.bind(this));
        }

        // 重置数据库按钮
        const resetDatabaseBtn = document.getElementById('resetDatabaseBtn');
        if (resetDatabaseBtn) {
            resetDatabaseBtn.addEventListener('click', this.handleResetDatabase.bind(this));
        }

        // 刷新统计按钮
        const refreshStatsBtn = document.getElementById('refreshStatsBtn');
        if (refreshStatsBtn) {
            refreshStatsBtn.addEventListener('click', this.loadDatabaseStats.bind(this));
        }
    }

    /**
     * 设置全局变量（用于兼容HTML中的事件处理）
     */
    setupGlobalVariables() {
        window.app = this;
        window.copyToClipboard = this.copyToClipboard.bind(this);
        window.showAbout = this.showAbout.bind(this);
        window.showHelp = this.showHelp.bind(this);

        console.log('全局变量设置完成');
    }







    /**
     * 切换代币库面板
     */
    toggleTokenLibraryPanel() {
        this.isTokenLibraryVisible = !this.isTokenLibraryVisible;

        const panel = document.getElementById('tokenLibraryContent');
        const btn = document.getElementById('toggleTokenLibraryBtn');

        if (panel) {
            panel.style.display = this.isTokenLibraryVisible ? 'block' : 'none';
        }

        if (btn) {
            const textSpan = btn.querySelector('.toggle-text');
            if (textSpan) {
                textSpan.textContent = this.isTokenLibraryVisible ? '收起代币库' : '展开代币库';
            }
        }

        if (this.isTokenLibraryVisible) {
            this.loadTokenLibrary();
        }
    }

    /**
     * 加载代币库
     */
    async loadTokenLibrary() {
        try {
            this.tokens = await this.apiService.getTokenLibrary({ is_active: true });
            this.filteredTokens = [...this.tokens];
            this.renderTokenLibraryList();
            this.updateTokenStatsFromLocal(); // 筛选时使用本地数据更新统计
        } catch (error) {
            console.error('加载代币库失败:', error);
            this.uiManager.showNotification('加载代币库失败: ' + error.message, 'error');
        }
    }

    /**
     * 渲染代币库列表
     */
    renderTokenLibraryList() {
        const container = document.getElementById('tokenTableBody');
        if (!container) return;

        if (this.filteredTokens.length === 0) {
            container.innerHTML = '<tr><td colspan="7" class="empty-state">暂无代币数据</td></tr>';
            return;
        }

        const tokensHtml = this.filteredTokens.map(token => `
            <tr class="token-library-item">
                <td class="token-symbol">${token.symbol}</td>
                <td class="token-name">${token.name || '未知名称'}</td>
                <td class="token-chain">${token.chain_name}</td>
                <td class="contract-address">
                    ${token.contract_address ?
                `<code title="${token.contract_address}">${token.contract_address.substring(0, 10)}...</code>` :
                '<span class="native-token">原生代币</span>'
            }
                </td>
                <td class="token-type">
                    <span class="type-badge ${token.is_predefined ? 'predefined' : 'custom'}">
                        ${token.is_predefined ? '预定义' : '自定义'}
                    </span>
                </td>
                <td class="coingecko-id">${token.coingecko_id || '-'}</td>
                <td class="token-actions">
                    <button class="btn btn-small btn-primary" onclick="app.useTokenInAddForm('${token.symbol}', '${token.chain_name}', '${token.contract_address || ''}')">
                        使用
                    </button>
                    ${!token.is_predefined ? `
                        <button class="btn btn-small btn-danger" onclick="app.deleteTokenFromLibrary(${token.id})">
                            删除
                        </button>
                    ` : ''}
                </td>
            </tr>
        `).join('');

        container.innerHTML = tokensHtml;
    }

    /**
     * 在添加表单中使用代币
     * @param {string} symbol 代币符号
     * @param {string} chainName 链名称
     * @param {string} contractAddress 合约地址
     */
    useTokenInAddForm(symbol, chainName, contractAddress) {
        const tokenSelect = document.getElementById('tokenSelect');
        const chainSelect = document.querySelector('select[name="chainName"]');
        const contractInput = document.querySelector('input[name="tokenContract"]');

        if (chainSelect) chainSelect.value = chainName;

        // 设置代币选择框的值
        if (tokenSelect) {
            const optionValue = `${symbol}|${contractAddress || 'null'}`;
            tokenSelect.value = optionValue;
        }

        // 更新合约地址显示
        if (contractInput) {
            contractInput.value = contractAddress || '';
        }

        this.uiManager.showNotification(`已选择代币: ${symbol}`, 'success', 2000);

        // 关闭代币库面板
        this.toggleTokenLibraryPanel();
    }



    /**
     * 切换管理面板
     */
    toggleManagementPanel() {
        const panel = document.getElementById('managementContent');
        const btn = document.getElementById('toggleManagementBtn');

        if (!panel || !btn) return;

        const isVisible = panel.style.display === 'block';

        panel.style.display = isVisible ? 'none' : 'block';

        const textSpan = btn.querySelector('.toggle-text');
        if (textSpan) {
            textSpan.textContent = isVisible ? '显示管理面板' : '隐藏管理面板';
        }

        if (!isVisible) {
            this.loadDatabaseStats();
        }
    }

    /**
     * 加载数据库统计
     */
    async loadDatabaseStats() {
        try {
            const stats = await this.apiService.getDatabaseStats();
            this.renderDatabaseStats(stats);
        } catch (error) {
            console.error('加载数据库统计失败:', error);
        }
    }

    /**
     * 渲染数据库统计
     * @param {Object} stats 统计数据
     */
    renderDatabaseStats(stats) {
        const container = document.getElementById('databaseStats');
        if (!container) return;

        container.innerHTML = `
            <div class="stats-grid">
                <div class="stat-item">
                    <span class="stat-label">资产记录:</span>
                    <span class="stat-value">${stats.assets_count || 0}</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">钱包数量:</span>
                    <span class="stat-value">${stats.wallets_count || 0}</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">代币数量:</span>
                    <span class="stat-value">${stats.tokens_count || 0}</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">数据库大小:</span>
                    <span class="stat-value">${stats.database_size_mb || 0} MB</span>
                </div>
            </div>
        `;
    }

    /**
     * 复制文本到剪贴板
     * @param {string} text 要复制的文本
     */
    async copyToClipboard(text) {
        try {
            const success = await copyToClipboard(text);
            if (success) {
                this.uiManager.showNotification('已复制到剪贴板', 'success', 2000);
            } else {
                this.uiManager.showNotification('复制失败', 'error', 2000);
            }
        } catch (error) {
            console.error('复制失败:', error);
            this.uiManager.showNotification('复制失败', 'error', 2000);
        }
    }

    /**
     * 显示关于信息
     */
    showAbout() {
        const content = `
            <h2>关于加密货币资产管理</h2>
            <p>这是一个开源的加密货币资产管理工具，采用模块化架构设计。</p>
            <h3>功能特性:</h3>
            <ul>
                <li>🔗 支持多区块链（Ethereum、Arbitrum、Base、Polygon、BSC、Solana、Sui、Bitcoin）</li>
                <li>💰 实时获取代币余额和价格</li>
                <li>📊 资产分析和历史图表</li>
                <li>🎨 响应式设计，支持移动端</li>
                <li>🚀 模块化架构，易于维护和扩展</li>
            </ul>
            <h3>技术栈:</h3>
            <ul>
                <li>前端: HTML5, CSS3, ES6+ 模块化</li>
                <li>后端: Python 3, FastAPI（模块化路由）</li>
                <li>区块链: Web3.py</li>
                <li>价格数据: CoinGecko API</li>
                <li>图表: Chart.js</li>
            </ul>
            <p class="mt-3">
                <strong>版本:</strong> 2.0.0 (模块化版本)<br>
                <strong>许可证:</strong> MIT License
            </p>
        `;
        this.uiManager.showModal(content);
    }

    /**
     * 显示帮助信息
     */
    showHelp() {
        const content = `
            <h2>使用帮助</h2>
            <h3>如何添加资产？</h3>
            <ol>
                <li>在"手动添加"模式下填写钱包地址</li>
                <li>选择对应的区块链网络</li>
                <li>输入代币符号（如 ETH, USDC）</li>
                <li>如果是 ERC20 代币，填写合约地址</li>
                <li>点击"添加资产"按钮</li>
            </ol>
            
            <h3>智能发现功能:</h3>
            <p>切换到"智能添加"模式，输入钱包地址和选择链，系统会自动发现该地址的所有代币。</p>
            
            <h3>图表功能:</h3>
            <ul>
                <li><strong>资产分布图:</strong> 查看按链、代币、钱包等维度的资产分布</li>
                <li><strong>历史图表:</strong> 跟踪资产价值随时间的变化趋势</li>
            </ul>
            
            <h3>快捷键:</h3>
            <ul>
                <li><kbd>Ctrl/Cmd + R</kbd>: 刷新资产数据</li>
                <li><kbd>Esc</kbd>: 关闭模态框</li>
            </ul>
            
            <h3>模块化架构优势:</h3>
            <ul>
                <li>更好的代码组织和维护性</li>
                <li>功能模块独立，便于测试</li>
                <li>支持按需加载和扩展</li>
            </ul>
        `;
        this.uiManager.showModal(content);
    }

    /**
     * 处理清空所有数据
     */
    async handleClearAllData() {
        const confirmed = await this.uiManager.showConfirmationDialog({
            title: '⚠️ 危险操作确认',
            message: '此操作将永久删除所有数据，包括：\n• 所有资产记录\n• 所有钱包信息\n• 所有代币信息\n• 所有历史快照\n• 所有价格缓存\n\n此操作不可恢复，请确认是否继续？',
            confirmText: '确认清空',
            cancelText: '取消',
            type: 'danger'
        });

        if (!confirmed) return;

        const btn = document.getElementById('clearAllDataBtn');
        const btnText = btn?.querySelector('.btn-text');
        const btnLoading = btn?.querySelector('.btn-loading');

        try {
            // 显示加载状态
            if (btnText) btnText.style.display = 'none';
            if (btnLoading) btnLoading.style.display = 'inline';
            if (btn) btn.disabled = true;

            await this.apiService.clearDatabase();

            this.uiManager.showNotification('✅ 所有数据已清空', 'success');

            // 重新加载页面数据
            await this.assetManager.loadAssets();
            await this.loadDatabaseStats();

        } catch (error) {
            console.error('清空数据失败:', error);
            this.uiManager.showNotification('❌ 清空数据失败: ' + error.message, 'error');
        } finally {
            // 恢复按钮状态
            if (btnText) btnText.style.display = 'inline';
            if (btnLoading) btnLoading.style.display = 'none';
            if (btn) btn.disabled = false;
        }
    }

    /**
     * 处理重置数据库
     */
    async handleResetDatabase() {
        const confirmed = await this.uiManager.showConfirmationDialog({
            title: '⚠️ 危险操作确认',
            message: '此操作将重置整个数据库，包括：\n• 清空所有数据\n• 重新初始化表结构\n• 恢复默认配置\n• 重置自增ID序列\n\n此操作不可恢复，请确认是否继续？',
            confirmText: '确认重置',
            cancelText: '取消',
            type: 'danger'
        });

        if (!confirmed) return;

        const btn = document.getElementById('resetDatabaseBtn');
        const btnText = btn?.querySelector('.btn-text');
        const btnLoading = btn?.querySelector('.btn-loading');

        try {
            // 显示加载状态
            if (btnText) btnText.style.display = 'none';
            if (btnLoading) btnLoading.style.display = 'inline';
            if (btn) btn.disabled = true;

            await this.apiService.resetDatabase();

            this.uiManager.showNotification('✅ 数据库已重置', 'success');

            // 重新加载页面数据
            await this.assetManager.loadAssets();
            await this.loadDatabaseStats();

        } catch (error) {
            console.error('重置数据库失败:', error);
            this.uiManager.showNotification('❌ 重置数据库失败: ' + error.message, 'error');
        } finally {
            // 恢复按钮状态
            if (btnText) btnText.style.display = 'inline';
            if (btnLoading) btnLoading.style.display = 'none';
            if (btn) btn.disabled = false;
        }
    }

    /**
     * 处理添加代币表单提交
     */
    async handleAddTokenFormSubmit(event) {
        event.preventDefault();

        const formData = new FormData(event.target);
        const tokenData = {
            symbol: formData.get('symbol')?.trim().toUpperCase(),
            name: formData.get('name')?.trim(),
            chain_name: formData.get('chainName'),
            contract_address: formData.get('contractAddress')?.trim() || null,
            decimals: parseInt(formData.get('decimals')) || 18,
            coingecko_id: formData.get('coingeckoId')?.trim() || null
        };

        // 验证必填字段
        if (!tokenData.symbol || !tokenData.name || !tokenData.chain_name) {
            this.uiManager.showNotification('请填写所有必填字段', 'error');
            return;
        }

        try {
            const addTokenBtn = document.getElementById('addTokenBtn');
            const btnText = addTokenBtn.querySelector('.btn-text');
            const btnLoading = addTokenBtn.querySelector('.btn-loading');

            // 设置加载状态
            if (btnText) btnText.style.display = 'none';
            if (btnLoading) btnLoading.style.display = 'inline';
            addTokenBtn.disabled = true;

            const result = await this.apiService.addTokenToLibrary(tokenData);

            this.uiManager.showNotification(`代币 ${tokenData.symbol} 添加成功`, 'success');

            // 重新加载代币库
            await this.loadTokenLibrary();

            // 重置表单
            event.target.reset();

        } catch (error) {
            console.error('添加代币失败:', error);
            this.uiManager.showNotification('添加代币失败: ' + error.message, 'error');
        } finally {
            // 恢复按钮状态
            const addTokenBtn = document.getElementById('addTokenBtn');
            const btnText = addTokenBtn.querySelector('.btn-text');
            const btnLoading = addTokenBtn.querySelector('.btn-loading');

            if (btnText) btnText.style.display = 'inline';
            if (btnLoading) btnLoading.style.display = 'none';
            addTokenBtn.disabled = false;
        }
    }

    /**
     * 处理验证合约地址
     */
    async handleValidateContract() {
        const contractInput = document.getElementById('tokenContractInput');
        const chainSelect = document.getElementById('tokenChainName');

        if (!contractInput || !chainSelect) return;

        const contractAddress = contractInput.value.trim();
        const chainName = chainSelect.value;

        if (!contractAddress || !chainName) {
            this.uiManager.showNotification('请先填写合约地址和选择区块链', 'warning');
            return;
        }

        try {
            const validateBtn = document.getElementById('validateTokenBtn');
            const btnText = validateBtn.querySelector('.btn-text');
            const btnLoading = validateBtn.querySelector('.btn-loading');

            // 设置加载状态
            if (btnText) btnText.style.display = 'none';
            if (btnLoading) btnLoading.style.display = 'inline';
            validateBtn.disabled = true;

            const result = await this.apiService.validateContractAddress(contractAddress, chainName);

            if (result.valid) {
                this.uiManager.showNotification('合约地址验证成功', 'success');

                // 如果获取到代币信息，自动填充表单
                if (result.token_info) {
                    const symbolInput = document.getElementById('tokenSymbolInput');
                    const nameInput = document.getElementById('tokenNameInput');
                    const decimalsInput = document.getElementById('tokenDecimalsInput');

                    if (symbolInput && result.token_info.symbol) {
                        symbolInput.value = result.token_info.symbol;
                    }
                    if (nameInput && result.token_info.name) {
                        nameInput.value = result.token_info.name;
                    }
                    if (decimalsInput && result.token_info.decimals) {
                        decimalsInput.value = result.token_info.decimals;
                    }
                }
            } else {
                this.uiManager.showNotification('合约地址验证失败: ' + (result.message || '无效的合约地址'), 'error');
            }

        } catch (error) {
            console.error('验证合约地址失败:', error);
            this.uiManager.showNotification('验证合约地址失败: ' + error.message, 'error');
        } finally {
            // 恢复按钮状态
            const validateBtn = document.getElementById('validateTokenBtn');
            const btnText = validateBtn.querySelector('.btn-text');
            const btnLoading = validateBtn.querySelector('.btn-loading');

            if (btnText) btnText.style.display = 'inline';
            if (btnLoading) btnLoading.style.display = 'none';
            validateBtn.disabled = false;
        }
    }

    /**
     * 删除代币库中的代币
     */
    async deleteTokenFromLibrary(tokenId) {
        if (!confirm('确定要删除这个代币吗？此操作不可撤销。')) {
            return;
        }

        try {
            await this.apiService.deleteTokenFromLibrary(tokenId);
            this.uiManager.showNotification('代币删除成功', 'success');

            // 重新加载代币库
            await this.loadTokenLibrary();

        } catch (error) {
            console.error('删除代币失败:', error);
            this.uiManager.showNotification('删除代币失败: ' + error.message, 'error');
        }
    }

    /**
     * 筛选代币列表
     */
    filterTokenList() {
        const chainFilter = document.getElementById('tokenListChainFilter');
        const typeFilter = document.getElementById('tokenListTypeFilter');
        const searchInput = document.getElementById('tokenSearchInput');

        if (!chainFilter || !typeFilter || !searchInput) return;

        const chainValue = chainFilter.value;
        const typeValue = typeFilter.value;
        const searchValue = searchInput.value.toLowerCase().trim();

        this.filteredTokens = this.tokens.filter(token => {
            // 链筛选
            if (chainValue && token.chain_name !== chainValue) {
                return false;
            }

            // 类型筛选
            if (typeValue === 'predefined' && !token.is_predefined) {
                return false;
            }
            if (typeValue === 'custom' && token.is_predefined) {
                return false;
            }

            // 搜索筛选
            if (searchValue) {
                const searchFields = [
                    token.symbol.toLowerCase(),
                    token.name.toLowerCase(),
                    token.contract_address?.toLowerCase() || '',
                    token.coingecko_id?.toLowerCase() || ''
                ];

                if (!searchFields.some(field => field.includes(searchValue))) {
                    return false;
                }
            }

            return true;
        });

        this.renderTokenLibraryList();
        this.updateTokenStatsFromLocal(); // 筛选时使用本地数据更新统计
    }

    /**
     * 更新代币统计信息
     */
    async updateTokenStats() {
        try {
            // 获取真实的统计数据
            const stats = await this.apiService.getTokenStatistics();

            const totalTokensCount = document.getElementById('totalTokensCount');
            const predefinedTokensCount = document.getElementById('predefinedTokensCount');
            const customTokensCount = document.getElementById('customTokensCount');
            const supportedChainsCount = document.getElementById('supportedChainsCount');

            if (totalTokensCount) {
                totalTokensCount.textContent = stats.total_tokens || 0;
            }

            if (predefinedTokensCount) {
                predefinedTokensCount.textContent = stats.predefined_tokens || 0;
            }

            if (customTokensCount) {
                customTokensCount.textContent = stats.custom_tokens || 0;
            }

            if (supportedChainsCount) {
                const chainCount = stats.chain_statistics ? stats.chain_statistics.length : 0;
                supportedChainsCount.textContent = chainCount;
            }
        } catch (error) {
            console.error('获取代币统计失败:', error);
            // 如果API调用失败，使用本地数据作为备选
            this.updateTokenStatsFromLocal();
        }
    }

    /**
     * 使用本地数据更新代币统计信息（备选方案）
     */
    updateTokenStatsFromLocal() {
        const totalTokensCount = document.getElementById('totalTokensCount');
        const predefinedTokensCount = document.getElementById('predefinedTokensCount');
        const customTokensCount = document.getElementById('customTokensCount');
        const supportedChainsCount = document.getElementById('supportedChainsCount');

        if (totalTokensCount) {
            totalTokensCount.textContent = this.filteredTokens.length;
        }

        if (predefinedTokensCount) {
            const predefinedCount = this.filteredTokens.filter(token => token.is_predefined).length;
            predefinedTokensCount.textContent = predefinedCount;
        }

        if (customTokensCount) {
            const customCount = this.filteredTokens.filter(token => !token.is_predefined).length;
            customTokensCount.textContent = customCount;
        }

        if (supportedChainsCount) {
            const uniqueChains = new Set(this.filteredTokens.map(token => token.chain_name));
            supportedChainsCount.textContent = uniqueChains.size;
        }
    }

    /**
     * 销毁应用实例
     */
    destroy() {
        if (this.chartManager) {
            this.chartManager.destroy();
        }

        // 清理全局变量
        if (window.app === this) {
            delete window.app;
        }
        delete window.copyToClipboard;
        delete window.showAbout;
        delete window.showHelp;
    }
}

// 导出主应用类
export default CryptoAssetManagerModular; 
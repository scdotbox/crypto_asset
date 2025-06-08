/**
 * 图表管理器模块
 * 
 * 统一管理所有图表功能，包括资产分布图表和历史数据图表
 */

import { CONFIG, MESSAGES } from './config.js';
import { formatNumber, generateChartColors, parseDateLabel, formatDateLabel, formatTimeSpan } from './utils.js';

export class ChartManager {
    constructor(apiService, uiManager) {
        this.apiService = apiService;
        this.uiManager = uiManager;
        
        // 资产分布图表（饼状图）
        this.distributionChartInstance = null;
        
        // 资产趋势图表（折线图）
        this.trendChartInstance = null;
        
        // 图表显示状态
        this.chartsVisible = false;
        this.currentChartType = 'address';
        // 趋势图表筛选条件
        this.trendFilters = {
            chain: '',      // 区块链筛选
            address: '',    // 地址筛选
            token: ''       // 代币筛选
        };
        this.currentTimeRange = '30d';
        this.currentInterval = '1d';
        
        this.init();
    }

    /**
     * 初始化图表管理器
     */
    init() {
        console.log('🚀 ChartManager.init() 开始初始化');
        
        // 检查Chart.js是否可用
        this.checkChartJsAvailability();
        
        // 绑定事件
        this.bindEvents();
        
        console.log('✅ ChartManager.init() 初始化完成');
    }

    /**
     * 检查Chart.js库的可用性
     */
    checkChartJsAvailability() {
        const checkChart = () => {
            if (typeof Chart !== 'undefined') {
                console.log('✅ Chart.js 已加载，版本:', Chart.version || '未知');
                
                // 设置Chart.js默认配置
                Chart.defaults.font.family = 'system-ui, -apple-system, sans-serif';
                Chart.defaults.plugins.legend.position = 'bottom';
                Chart.defaults.plugins.legend.labels.usePointStyle = true;
                
                return true;
            } else {
                console.warn('⚠️ Chart.js 未加载，图表功能将不可用');
                return false;
            }
        };

        // 立即检查
        if (!checkChart()) {
            // 如果Chart.js未加载，等待一段时间后重试
            console.log('🔄 等待Chart.js加载...');
            
            let retryCount = 0;
            const maxRetries = 10;
            const retryInterval = 500;
            
            const retryCheck = () => {
                retryCount++;
                console.log(`🔄 第${retryCount}次检查Chart.js...`);
                
                if (checkChart()) {
                    console.log('✅ Chart.js 延迟加载成功');
                    return;
                }
                
                if (retryCount < maxRetries) {
                    setTimeout(retryCheck, retryInterval);
                } else {
                    console.error('❌ Chart.js 加载超时，图表功能将不可用');
                    this.showChartLoadError();
                }
            };
            
            setTimeout(retryCheck, retryInterval);
        }
    }

    /**
     * 显示Chart.js加载错误信息
     */
    showChartLoadError() {
        const chartSection = document.getElementById('chartSection');
        if (chartSection) {
            const errorDiv = document.createElement('div');
            errorDiv.className = 'chart-load-error';
            errorDiv.style.cssText = `
                background: #fff3cd;
                border: 1px solid #ffeaa7;
                color: #856404;
                padding: 15px;
                border-radius: 5px;
                margin: 10px 0;
                text-align: center;
            `;
            errorDiv.innerHTML = `
                <h4>⚠️ 图表功能不可用</h4>
                <p>Chart.js 库加载失败，请检查网络连接或刷新页面重试。</p>
                <button onclick="location.reload()" style="
                    background: #007bff;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    cursor: pointer;
                ">刷新页面</button>
            `;
            
            const sectionContainer = chartSection.querySelector('.section-container');
            if (sectionContainer) {
                sectionContainer.insertBefore(errorDiv, sectionContainer.firstChild);
            }
        }
    }

    /**
     * 绑定图表相关事件
     */
    bindEvents() {
        // 延迟绑定事件，确保DOM完全加载
        const bindToggleEvent = () => {
            const toggleChartsBtn = document.getElementById('toggleChartsBtn');
            console.log('🔗 bindEvents - toggleChartsBtn 元素:', toggleChartsBtn);
            
            if (toggleChartsBtn) {
                console.log('🔗 绑定 toggleCharts 事件监听器');
                
                // 移除可能存在的旧事件监听器
                toggleChartsBtn.removeEventListener('click', this.handleToggleClick);
                
                // 绑定新的事件监听器
                this.handleToggleClick = (event) => {
                    console.log('🖱️ 按钮被点击！事件对象:', event);
                    console.log('🖱️ 事件目标:', event.target);
                    console.log('🖱️ 当前目标:', event.currentTarget);
                    event.preventDefault();
                    event.stopPropagation();
                    this.toggleCharts();
                };
                
                toggleChartsBtn.addEventListener('click', this.handleToggleClick);
                console.log('🔗 事件绑定成功');
                
                // 测试按钮是否可点击
                console.log('🔗 按钮样式信息:');
                const computedStyle = window.getComputedStyle(toggleChartsBtn);
                console.log('🔗 - display:', computedStyle.display);
                console.log('🔗 - visibility:', computedStyle.visibility);
                console.log('🔗 - pointer-events:', computedStyle.pointerEvents);
                console.log('🔗 - z-index:', computedStyle.zIndex);
                console.log('🔗 - position:', computedStyle.position);
                
                return true;
            } else {
                console.error('❌ 找不到 toggleChartsBtn 元素');
                return false;
            }
        };

        // 立即尝试绑定
        if (!bindToggleEvent()) {
            // 如果立即绑定失败，使用多种重试策略
            console.log('🔄 立即绑定失败，尝试延迟重新绑定...');
            
            // 策略1：短延迟重试
            setTimeout(() => {
                if (!bindToggleEvent()) {
                    console.log('🔄 短延迟重试失败，尝试DOM加载完成后重试...');
                    
                    // 策略2：等待DOM完全加载
                    if (document.readyState === 'loading') {
                        document.addEventListener('DOMContentLoaded', () => {
                            setTimeout(bindToggleEvent, 100);
                        });
                    } else {
                        // 策略3：使用MutationObserver监听DOM变化
                        const observer = new MutationObserver((mutations) => {
                            for (const mutation of mutations) {
                                if (mutation.type === 'childList') {
                                    for (const node of mutation.addedNodes) {
                                        if (node.nodeType === Node.ELEMENT_NODE) {
                                            if (node.id === 'toggleChartsBtn' || 
                                                node.querySelector && node.querySelector('#toggleChartsBtn')) {
                                                console.log('🔄 通过MutationObserver检测到按钮元素');
                                                if (bindToggleEvent()) {
                                                    observer.disconnect();
                                                }
                                                break;
                                            }
                                        }
                                    }
                                }
                            }
                        });
                        
                        observer.observe(document.body, {
                            childList: true,
                            subtree: true
                        });
                        
                        // 10秒后停止观察
                        setTimeout(() => {
                            observer.disconnect();
                            console.log('🔄 MutationObserver 超时停止');
                        }, 10000);
                    }
                }
            }, 500);
        }
        
        // 分布图表统计维度选择器
        const chartTypeSelector = document.getElementById('chartType');
        if (chartTypeSelector) {
            chartTypeSelector.addEventListener('change', (e) => {
                this.currentChartType = e.target.value;
                if (this.chartsVisible) {
                    this.updateDistributionChart();
                }
            });
        }

        // 趋势图表筛选器
        const trendChainFilter = document.getElementById('trendChainFilter');
        const trendAddressFilter = document.getElementById('trendAddressFilter');
        const trendTokenFilter = document.getElementById('trendTokenFilter');
        
        if (trendChainFilter) {
            trendChainFilter.addEventListener('change', async (e) => {
                this.trendFilters.chain = e.target.value;
                await this.updateTrendAddressOptions();
                await this.updateTrendTokenOptions();
                if (this.chartsVisible) {
                    this.updateTrendChart();
                }
            });
        }
        
        if (trendAddressFilter) {
            trendAddressFilter.addEventListener('change', async (e) => {
                this.trendFilters.address = e.target.value;
                await this.updateTrendTokenOptions();
                if (this.chartsVisible) {
                    this.updateTrendChart();
                }
            });
        }
        
        if (trendTokenFilter) {
            trendTokenFilter.addEventListener('change', (e) => {
                this.trendFilters.token = e.target.value;
                if (this.chartsVisible) {
                    this.updateTrendChart();
                }
            });
        }

        // 趋势图表控制
        const refreshTrendChartBtn = document.getElementById('refreshTrendChart');
        const timeRangeSelector = document.getElementById('timeRange');
        const intervalSelector = document.getElementById('dataInterval');
        const exportTrendChartBtn = document.getElementById('exportTrendChart');
        
        if (refreshTrendChartBtn) {
            refreshTrendChartBtn.addEventListener('click', this.updateTrendChart.bind(this));
        }
        
        if (timeRangeSelector) {
            timeRangeSelector.addEventListener('change', (e) => {
                this.currentTimeRange = e.target.value;
                if (this.chartsVisible) {
                    this.updateTrendChart();
                }
            });
        }
        
        if (intervalSelector) {
            intervalSelector.addEventListener('change', (e) => {
                this.currentInterval = e.target.value;
                if (this.chartsVisible) {
                    this.updateTrendChart();
                }
            });
        }
        
        if (exportTrendChartBtn) {
            exportTrendChartBtn.addEventListener('click', this.exportTrendChart.bind(this));
        }
    }

    /**
     * 切换图表显示
     */
    toggleCharts() {
        console.log('🔄 toggleCharts 被调用');
        this.chartsVisible = !this.chartsVisible;
        console.log('📊 图表可见状态:', this.chartsVisible);
        
        const chartsContainer = document.getElementById('chartsContainer');
        const toggleChartsBtn = document.getElementById('toggleChartsBtn');
        
        console.log('📦 chartsContainer 元素:', chartsContainer);
        console.log('🔘 toggleChartsBtn 元素:', toggleChartsBtn);
        
        if (chartsContainer) {
            chartsContainer.style.display = this.chartsVisible ? 'block' : 'none';
            console.log('📦 chartsContainer display 设置为:', chartsContainer.style.display);
        } else {
            console.error('❌ 找不到 chartsContainer 元素');
        }
        
        // 更新按钮状态
        if (toggleChartsBtn) {
            const toggleText = toggleChartsBtn.querySelector('.toggle-text');
            console.log('📝 toggleText 元素:', toggleText);
            if (toggleText) {
                toggleText.textContent = this.chartsVisible ? '隐藏图表' : '显示图表';
                console.log('📝 按钮文本更新为:', toggleText.textContent);
            }
        }
        
        if (this.chartsVisible) {
            console.log('🚀 开始渲染图表...');
            // 初始化筛选器选项
            this.initTrendFilterOptions();
            
            // 获取当前资产数据并渲染图表
            if (window.app && window.app.assetManager) {
                console.log('📊 使用 assetManager 数据渲染图表');
                console.log('📊 filteredAssets:', window.app.assetManager.filteredAssets);
                this.renderDistributionChart(window.app.assetManager.filteredAssets || []);
                this.renderTrendChart();
            } else {
                console.log('⚠️ 没有找到 assetManager，使用空数据渲染图表');
                this.renderDistributionChart([]);
                this.renderTrendChart();
            }
        } else {
            console.log('🗑️ 销毁图表实例');
            // 销毁图表实例
            this.destroyCharts();
        }
    }

    /**
     * 渲染资产分布图表（饼状图）
     * @param {Array} assets 资产数据
     */
    renderDistributionChart(assets = []) {
        console.log('🥧 renderDistributionChart 被调用，资产数量:', assets.length);
        
        if (!this.chartsVisible || typeof Chart === 'undefined') {
            console.log('🥧 跳过渲染分布图表：chartsVisible=', this.chartsVisible, ', Chart可用=', typeof Chart !== 'undefined');
            return;
        }
        
        try {
            const chartData = this.prepareChartData(assets);
            
            if (chartData.labels.length === 0) {
                console.log('🥧 没有数据，显示空状态');
                this.showDistributionChartEmptyState();
                return;
            }
            
            // 隐藏空状态，显示图表内容
            const emptyState = document.getElementById('distributionChartEmptyState');
            const chartContent = document.getElementById('distributionChartContent');
            
            if (emptyState) {
                emptyState.style.display = 'none';
            }
            
            if (chartContent) {
                chartContent.style.display = 'block';
            }
            
            this.createDistributionChart(chartData);
            this.updateDistributionChartLegend(chartData);
            this.updateDistributionChartStats(chartData);
            console.log('🥧 分布图表渲染完成');
            
        } catch (error) {
            console.error('渲染分布图表失败:', error);
            this.uiManager.showNotification('分布图表渲染失败: ' + error.message, 'error');
        }
    }

    /**
     * 更新资产分布图表
     * @param {Array} assets 资产数据
     */
    updateDistributionChart(assets = []) {
        if (!this.chartsVisible) return;
        if (window.app && window.app.assetManager) {
            this.renderDistributionChart(window.app.assetManager.filteredAssets || []);
        } else {
            this.renderDistributionChart(assets);
        }
    }

    /**
     * 渲染资产趋势图表（折线图）
     */
    async renderTrendChart() {
        console.log('📈 renderTrendChart 被调用');
        console.log('📈 chartsVisible:', this.chartsVisible);
        console.log('📈 Chart 可用性:', typeof Chart !== 'undefined');
        
        if (!this.chartsVisible || typeof Chart === 'undefined') {
            console.log('📈 跳过渲染趋势图表：chartsVisible=', this.chartsVisible, ', Chart可用=', typeof Chart !== 'undefined');
            return;
        }
        
        try {
            console.log('📈 开始获取历史数据...');
            const historyData = await this.fetchAssetHistory();
            console.log('📈 获取到的历史数据:', historyData);
            
            if (!historyData || historyData.length === 0) {
                console.log('📈 没有历史数据，显示空状态');
                this.showTrendChartEmptyState();
                return;
            }
            
            // 隐藏空状态，显示图表内容
            const emptyState = document.getElementById('trendChartEmptyState');
            const chartContent = document.getElementById('trendChartContent');
            
            console.log('📈 emptyState 元素:', emptyState);
            console.log('📈 chartContent 元素:', chartContent);
            
            if (emptyState) {
                emptyState.style.display = 'none';
                console.log('📈 隐藏空状态');
            }
            
            if (chartContent) {
                chartContent.style.display = 'block';
                console.log('📈 显示图表内容');
            }
            
            console.log('📈 开始准备趋势图表数据...');
            const chartData = this.prepareTrendChartData(historyData);
            console.log('📈 准备的趋势图表数据:', chartData);
            
            console.log('📈 开始创建趋势图表...');
            this.createTrendChart(chartData);
            console.log('📈 趋势图表渲染完成');
            
        } catch (error) {
            console.error('渲染趋势图表失败:', error);
            this.uiManager.showNotification('趋势图表渲染失败: ' + error.message, 'error');
            this.showTrendChartEmptyState();
        }
    }

    /**
     * 更新资产趋势图表
     */
    async updateTrendChart() {
        if (!this.chartsVisible) return;
        await this.renderTrendChart();
    }

    /**
     * 准备图表数据
     * @param {Array} assets 资产数据
     * @returns {Object} 图表数据
     */
    prepareChartData(assets) {
        if (!assets || assets.length === 0) {
            return { labels: [], datasets: [] };
        }

        let groupedData = {};
        
        switch (this.currentChartType) {
            case 'chain':
                groupedData = this.groupByChain(assets);
                break;
            case 'token':
                groupedData = this.groupByToken(assets);
                break;
            case 'wallet':
                groupedData = this.groupByWallet(assets);
                break;
            default: // 'address'
                groupedData = this.groupByAddress(assets);
                break;
        }

        const labels = Object.keys(groupedData);
        const values = Object.values(groupedData);
        const colors = generateChartColors(labels.length);

        return {
            labels,
            datasets: [{
                data: values,
                backgroundColor: colors,
                borderColor: colors.map(color => color.replace('0.8', '1')),
                borderWidth: 2
            }]
        };
    }

    /**
     * 按链分组
     * @param {Array} assets 资产数据
     * @returns {Object} 分组数据
     */
    groupByChain(assets) {
        return assets.reduce((acc, asset) => {
            const key = asset.chain_name || '未知链';
            acc[key] = (acc[key] || 0) + (asset.value_usdc || 0);
            return acc;
        }, {});
    }

    /**
     * 按代币分组
     * @param {Array} assets 资产数据
     * @returns {Object} 分组数据
     */
    groupByToken(assets) {
        return assets.reduce((acc, asset) => {
            const key = asset.token_symbol || '未知代币';
            acc[key] = (acc[key] || 0) + (asset.value_usdc || 0);
            return acc;
        }, {});
    }

    /**
     * 按钱包分组
     * @param {Array} assets 资产数据
     * @returns {Object} 分组数据
     */
    groupByWallet(assets) {
        return assets.reduce((acc, asset) => {
            const key = asset.wallet_name || '未命名钱包';
            acc[key] = (acc[key] || 0) + (asset.value_usdc || 0);
            return acc;
        }, {});
    }

    /**
     * 按地址分组
     * @param {Array} assets 资产数据
     * @returns {Object} 分组数据
     */
    groupByAddress(assets) {
        return assets.reduce((acc, asset) => {
            const key = asset.address ? 
                `${asset.address.slice(0, 6)}...${asset.address.slice(-4)}` : 
                '未知地址';
            acc[key] = (acc[key] || 0) + (asset.value_usdc || 0);
            return acc;
        }, {});
    }

    /**
     * 创建分布图表实例
     * @param {Object} chartData 图表数据
     */
    createDistributionChart(chartData) {
        const ctx = document.getElementById('distributionChart');
        if (!ctx) return;

        // 销毁现有图表
        if (this.distributionChartInstance) {
            this.distributionChartInstance.destroy();
        }

        this.distributionChartInstance = new Chart(ctx, {
            type: 'doughnut',
            data: chartData,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false // 使用自定义图例
                    },
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                const label = context.label || '';
                                const value = context.parsed || 0;
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = ((value / total) * 100).toFixed(1);
                                return `${label}: $${formatNumber(value)} (${percentage}%)`;
                            }
                        }
                    }
                },
                animation: {
                    duration: CONFIG.CHART.ANIMATION_DURATION
                }
            }
        });
    }

    /**
     * 创建趋势图表实例
     * @param {Object} chartData 图表数据
     */
    createTrendChart(chartData) {
        const ctx = document.getElementById('trendChart');
        if (!ctx) return;

        // 销毁现有图表
        if (this.trendChartInstance) {
            this.trendChartInstance.destroy();
        }

        this.trendChartInstance = new Chart(ctx, {
            type: 'line',
            data: chartData,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        display: true,
                        title: {
                            display: true,
                            text: '时间'
                        }
                    },
                    y: {
                        display: true,
                        title: {
                            display: true,
                            text: '价值 (USD)'
                        },
                        ticks: {
                            callback: (value) => '$' + formatNumber(value)
                        }
                    }
                },
                plugins: {
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                return `${context.dataset.label}: $${formatNumber(context.parsed.y)}`;
                            }
                        }
                    },
                    legend: {
                        display: true,
                        position: 'top'
                    }
                },
                animation: {
                    duration: CONFIG.CHART.ANIMATION_DURATION
                }
            }
        });
    }

    /**
     * 更新分布图表图例
     * @param {Object} chartData 图表数据
     */
    updateDistributionChartLegend(chartData) {
        const legendContainer = document.getElementById('distributionChartLegend');
        if (!legendContainer) return;

        const total = chartData.datasets[0].data.reduce((a, b) => a + b, 0);
        
        const legendHtml = chartData.labels.map((label, index) => {
            const value = chartData.datasets[0].data[index];
            const percentage = ((value / total) * 100).toFixed(1);
            const color = chartData.datasets[0].backgroundColor[index];
            
            return `
                <div class="legend-item">
                    <span class="legend-color" style="background-color: ${color}"></span>
                    <span class="legend-label">${label}</span>
                    <span class="legend-value">$${formatNumber(value)} (${percentage}%)</span>
                </div>
            `;
        }).join('');

        legendContainer.innerHTML = legendHtml;
    }

    /**
     * 更新分布图表统计信息
     * @param {Object} chartData 图表数据
     */
    updateDistributionChartStats(chartData) {
        const statsContainer = document.getElementById('distributionChartStats');
        if (!statsContainer) return;

        const total = chartData.datasets[0].data.reduce((a, b) => a + b, 0);
        const count = chartData.labels.length;
        const average = count > 0 ? total / count : 0;
        const max = Math.max(...chartData.datasets[0].data);

        statsContainer.innerHTML = `
            <div class="stats-inline">
                <span class="stat-item-compact">
                    <span class="stat-label">总价值:</span>
                    <span class="stat-value">$${formatNumber(total)}</span>
                </span>
                <span class="stat-separator">|</span>
                <span class="stat-item-compact">
                    <span class="stat-label">项目数:</span>
                    <span class="stat-value">${count}</span>
                </span>
                <span class="stat-separator">|</span>
                <span class="stat-item-compact">
                    <span class="stat-label">平均值:</span>
                    <span class="stat-value">$${formatNumber(average)}</span>
                </span>
                <span class="stat-separator">|</span>
                <span class="stat-item-compact">
                    <span class="stat-label">最大值:</span>
                    <span class="stat-value">$${formatNumber(max)}</span>
                </span>
            </div>
        `;
    }

    /**
     * 显示分布图表空状态
     */
    showDistributionChartEmptyState() {
        const chartContent = document.getElementById('distributionChartContent');
        const chartEmptyState = document.getElementById('distributionChartEmptyState');
        
        if (chartContent) {
            chartContent.style.display = 'none';
        }
        
        if (chartEmptyState) {
            chartEmptyState.style.display = 'block';
        }
    }

    /**
     * 显示趋势图表空状态
     */
    showTrendChartEmptyState() {
        const chartContent = document.getElementById('trendChartContent');
        const chartEmptyState = document.getElementById('trendChartEmptyState');
        const infoPanel = document.getElementById('trendChartInfoPanel');
        
        if (chartContent) {
            chartContent.style.display = 'none';
        }
        
        if (chartEmptyState) {
            chartEmptyState.style.display = 'block';
        }
        
        if (infoPanel) {
            infoPanel.style.display = 'none';
        }
    }



    /**
     * 导出趋势图表
     */
    exportTrendChart() {
        if (!this.trendChartInstance) {
            this.uiManager.showNotification('没有可导出的图表', 'warning');
            return;
        }

        try {
            const url = this.trendChartInstance.toBase64Image();
            const link = document.createElement('a');
            link.download = `asset-trend-chart-${new Date().toISOString().split('T')[0]}.png`;
            link.href = url;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            
            this.uiManager.showNotification('图表导出成功', 'success');
        } catch (error) {
            console.error('导出图表失败:', error);
            this.uiManager.showNotification('图表导出失败: ' + error.message, 'error');
        }
    }

    /**
     * 销毁所有图表实例
     */
    destroy() {
        if (this.chartInstance) {
            this.chartInstance.destroy();
            this.chartInstance = null;
        }
        
        if (this.historyChartInstance) {
            this.historyChartInstance.destroy();
            this.historyChartInstance = null;
        }
    }

    /**
     * 获取资产历史数据
     * @returns {Promise<Array>} 历史数据数组
     */
    async fetchAssetHistory() {
        try {
            const requestData = {
                time_range: this.currentTimeRange,
                interval: this.currentInterval
            };
            
            // 添加筛选条件到请求数据
            if (this.trendFilters.chain) {
                requestData.chain_name = this.trendFilters.chain;
            }
            
            if (this.trendFilters.address) {
                requestData.address = this.trendFilters.address;
            }
            
            // 启用token_symbol筛选
            if (this.trendFilters.token) {
                requestData.token_symbol = this.trendFilters.token;
            }
            
            console.log('🔍 fetchAssetHistory 请求数据:', requestData);
            console.log('🔍 当前筛选条件:', this.trendFilters);
            
            // 调用API服务
            const response = await this.apiService.getAssetHistory(requestData);
            console.log('🔍 fetchAssetHistory API 响应:', response);
            
            // 处理不同的响应格式
            let historyData = [];
            
            if (response) {
                // 情况1：直接是数组格式
                if (Array.isArray(response)) {
                    console.log('🔍 响应是数组格式，长度:', response.length);
                    historyData = response;
                }
                // 情况2：包含data字段的对象格式
                else if (response.data && Array.isArray(response.data)) {
                    console.log('🔍 响应是对象格式，data数组长度:', response.data.length);
                    historyData = response.data;
                }
                // 情况3：包含success字段的标准响应格式
                else if (response.success !== undefined) {
                    if (response.success && response.data && Array.isArray(response.data)) {
                        console.log('🔍 标准成功响应，data数组长度:', response.data.length);
                        historyData = response.data;
                    } else {
                        console.warn('🔍 API响应表示失败:', response.message || '未知错误');
                        historyData = [];
                    }
                }
                // 情况4：其他格式，尝试直接使用
                else {
                    console.warn('🔍 未知的响应格式，尝试直接使用:', response);
                    historyData = [];
                }
            } else {
                console.warn('🔍 API返回空响应');
                historyData = [];
            }
            
            // 验证历史数据格式
            if (historyData.length > 0) {
                console.log('🔍 历史数据样本:', historyData[0]);
                console.log(`🔍 获取到 ${historyData.length} 个资产的历史数据`);
                
                // 转换为趋势图表需要的格式
                const convertedData = this.convertHistoryDataForTrend(historyData);
                console.log('🔍 转换后的趋势数据:', convertedData);
                
                return convertedData;
            } else {
                console.log('🔍 没有历史数据');
                return [];
            }
            
        } catch (error) {
            console.error('🔍 获取资产历史数据失败:', error);
            
            // 显示用户友好的错误信息
            if (this.uiManager) {
                this.uiManager.showNotification(
                    '获取历史数据失败: ' + (error.message || '网络错误'),
                    'error'
                );
            }
            
            throw error;
        }
    }

    /**
     * 将资产历史数据转换为趋势图表格式
     * @param {Array} historyData 原始历史数据
     * @returns {Array} 转换后的趋势数据
     */
    convertHistoryDataForTrend(historyData) {
        if (!historyData || !Array.isArray(historyData)) {
            return [];
        }

        // 使用Map来按时间戳合并数据点
        const timePointMap = new Map();
        
        // 遍历每个资产的历史数据
        historyData.forEach(assetHistory => {
            if (!assetHistory || !assetHistory.history_points) {
                return;
            }
            
            // 遍历每个历史点
            assetHistory.history_points.forEach(point => {
                if (!point || !point.timestamp) {
                    return;
                }
                
                const timestamp = point.timestamp;
                
                // 创建资产数据
                const assetData = {
                    asset_id: assetHistory.asset_id,
                    address: assetHistory.address,
                    chain_name: assetHistory.chain_name,
                    token_symbol: assetHistory.token_symbol,
                    token_contract_address: assetHistory.token_contract_address,
                    quantity: point.quantity || 0,
                    price_usdc: point.price_usdc || 0,
                    value_usdc: point.value_usdc || 0,
                    tag: assetHistory.tag,
                    wallet_name: assetHistory.wallet_name || '默认钱包'
                };
                
                // 如果该时间点已存在，添加资产到现有数据点
                if (timePointMap.has(timestamp)) {
                    const existingPoint = timePointMap.get(timestamp);
                    existingPoint.assets.push(assetData);
                } else {
                    // 创建新的时间点数据
                    const trendPoint = {
                        timestamp: timestamp,
                        date: point.date,
                        assets: [assetData]
                    };
                    timePointMap.set(timestamp, trendPoint);
                }
            });
        });
        
        // 转换Map为数组并按时间戳排序
        const trendData = Array.from(timePointMap.values()).sort((a, b) => a.timestamp - b.timestamp);
        
        console.log('🔄 转换历史数据完成，时间点数量:', trendData.length, '总资产数据点:', trendData.reduce((sum, point) => sum + point.assets.length, 0));
        return trendData;
    }

    /**
     * 准备趋势图表数据
     * @param {Array} historyData 历史数据
     * @returns {Object} 图表数据
     */
    prepareTrendChartData(historyData) {
        if (!historyData || historyData.length === 0) {
            return { labels: [], datasets: [] };
        }

        // 确保historyData是数组
        let dataArray = Array.isArray(historyData) ? historyData : [];
        
        // 如果historyData是对象且包含data属性，使用data属性
        if (!Array.isArray(historyData) && historyData.data && Array.isArray(historyData.data)) {
            dataArray = historyData.data;
        }
        
        if (dataArray.length === 0) {
            return { labels: [], datasets: [] };
        }

        // 按时间排序
        const sortedData = dataArray.sort((a, b) => a.timestamp - b.timestamp);
        
        // 将秒级时间戳转换为毫秒级，然后格式化为日期标签
        const labels = sortedData.map(item => {
            const timestampMs = item.timestamp * 1000;
            return formatDateLabel(new Date(timestampMs));
        });
        
        // 根据筛选条件决定显示方式
        if (this.hasSpecificFilters()) {
            // 有具体筛选条件时，显示筛选后的资产趋势
            return this.createFilteredTrendDatasets(labels, sortedData);
        } else {
            // 无筛选条件时，显示总量和各分量
            return this.createComprehensiveTrendDatasets(labels, sortedData);
        }
    }

    /**
     * 检查是否有具体的筛选条件
     * @returns {boolean} 是否有筛选条件
     */
    hasSpecificFilters() {
        return this.trendFilters.chain || this.trendFilters.address || this.trendFilters.token;
    }

    /**
     * 创建筛选后的趋势数据集
     * @param {Array} labels 时间标签
     * @param {Array} sortedData 排序后的数据
     * @returns {Object} 图表数据
     */
    createFilteredTrendDatasets(labels, sortedData) {
        // 应用筛选条件
        const filteredData = this.applyTrendFilters(sortedData);
        
        // 根据筛选条件决定分组方式
        if (this.trendFilters.token) {
            // 选择了特定代币，显示该代币的趋势
            return this.createSingleTokenDataset(labels, filteredData, this.trendFilters.token);
        } else if (this.trendFilters.address) {
            // 选择了特定地址，按代币分组显示该地址的资产
            return this.createAddressTokenDatasets(labels, filteredData);
        } else if (this.trendFilters.chain) {
            // 选择了特定区块链，按地址分组显示该链的资产
            return this.createChainAddressDatasets(labels, filteredData);
        }
        
        // 默认返回空数据
        return { labels, datasets: [] };
    }

    /**
     * 创建综合趋势数据集（总量+各分量）
     * @param {Array} labels 时间标签
     * @param {Array} sortedData 排序后的数据
     * @returns {Object} 图表数据
     */
    createComprehensiveTrendDatasets(labels, sortedData) {
        const datasets = [];
        const colors = generateChartColors(10); // 生成足够的颜色
        
        // 1. 计算总量数据
        const totalData = sortedData.map(timePoint => {
            const assets = timePoint.assets || [];
            return assets.reduce((sum, asset) => sum + (asset.value_usdc || 0), 0);
        });
        
        // 添加总量数据集
        datasets.push({
            label: '总资产价值',
            data: totalData,
            borderColor: colors[0],
            backgroundColor: colors[0] + '20',
            borderWidth: 3,
            fill: false,
            tension: 0.1,
            pointRadius: 4,
            pointHoverRadius: 6
        });
        
        // 2. 按区块链分组显示各分量
        const chainData = this.groupDataByDimension(sortedData, 'chain');
        let colorIndex = 1;
        
        Object.keys(chainData).forEach(chainName => {
            const chainValues = chainData[chainName];
            
            datasets.push({
                label: `${chainName} 链`,
                data: chainValues,
                borderColor: colors[colorIndex % colors.length],
                backgroundColor: colors[colorIndex % colors.length] + '20',
                borderWidth: 2,
                fill: false,
                tension: 0.1,
                pointRadius: 2,
                pointHoverRadius: 4
            });
            
            colorIndex++;
        });
        
        return { labels, datasets };
    }

    /**
     * 按维度分组数据
     * @param {Array} sortedData 排序后的数据
     * @param {string} dimension 维度类型 ('chain', 'address', 'token')
     * @returns {Object} 分组后的数据
     */
    groupDataByDimension(sortedData, dimension) {
        const groupedData = {};
        
        sortedData.forEach(timePoint => {
            const assets = timePoint.assets || [];
            
            // 按维度分组计算每个时间点的值
            const dimensionValues = {};
            
            assets.forEach(asset => {
                let key;
                switch (dimension) {
                    case 'chain':
                        key = asset.chain_name;
                        break;
                    case 'address':
                        key = this.formatAddress(asset.address);
                        break;
                    case 'token':
                        key = asset.token_symbol;
                        break;
                    default:
                        key = 'unknown';
                }
                
                if (!dimensionValues[key]) {
                    dimensionValues[key] = 0;
                }
                dimensionValues[key] += (asset.value_usdc || 0);
            });
            
            // 将每个维度的值添加到对应的数组中
            Object.keys(dimensionValues).forEach(key => {
                if (!groupedData[key]) {
                    groupedData[key] = [];
                }
                groupedData[key].push(dimensionValues[key]);
            });
        });
        
        // 确保所有维度的数组长度一致
        const maxLength = sortedData.length;
        Object.keys(groupedData).forEach(key => {
            while (groupedData[key].length < maxLength) {
                groupedData[key].push(0);
            }
        });
        
        return groupedData;
    }

    /**
     * 创建单个代币的数据集
     * @param {Array} labels 时间标签
     * @param {Array} filteredData 筛选后的数据
     * @param {string} tokenSymbol 代币符号
     * @returns {Object} 图表数据
     */
    createSingleTokenDataset(labels, filteredData, tokenSymbol) {
        const colors = generateChartColors(1);
        
        const tokenData = filteredData.map(timePoint => {
            const assets = timePoint.assets || [];
            return assets
                .filter(asset => asset.token_symbol === tokenSymbol)
                .reduce((sum, asset) => sum + (asset.value_usdc || 0), 0);
        });
        
        return {
            labels,
            datasets: [{
                label: `${tokenSymbol} 价值`,
                data: tokenData,
                borderColor: colors[0],
                backgroundColor: colors[0] + '20',
                borderWidth: 3,
                fill: false,
                tension: 0.1,
                pointRadius: 4,
                pointHoverRadius: 6
            }]
        };
    }

    /**
     * 创建地址下各代币的数据集
     * @param {Array} labels 时间标签
     * @param {Array} filteredData 筛选后的数据
     * @returns {Object} 图表数据
     */
    createAddressTokenDatasets(labels, filteredData) {
        const tokenData = this.groupDataByDimension(filteredData, 'token');
        const colors = generateChartColors(Object.keys(tokenData).length);
        const datasets = [];
        
        let colorIndex = 0;
        Object.keys(tokenData).forEach(tokenSymbol => {
            datasets.push({
                label: tokenSymbol,
                data: tokenData[tokenSymbol],
                borderColor: colors[colorIndex % colors.length],
                backgroundColor: colors[colorIndex % colors.length] + '20',
                borderWidth: 2,
                fill: false,
                tension: 0.1,
                pointRadius: 3,
                pointHoverRadius: 5
            });
            colorIndex++;
        });
        
        return { labels, datasets };
    }

    /**
     * 创建区块链下各地址的数据集
     * @param {Array} labels 时间标签
     * @param {Array} filteredData 筛选后的数据
     * @returns {Object} 图表数据
     */
    createChainAddressDatasets(labels, filteredData) {
        const addressData = this.groupDataByDimension(filteredData, 'address');
        const colors = generateChartColors(Object.keys(addressData).length);
        const datasets = [];
        
        let colorIndex = 0;
        Object.keys(addressData).forEach(address => {
            datasets.push({
                label: address,
                data: addressData[address],
                borderColor: colors[colorIndex % colors.length],
                backgroundColor: colors[colorIndex % colors.length] + '20',
                borderWidth: 2,
                fill: false,
                tension: 0.1,
                pointRadius: 3,
                pointHoverRadius: 5
            });
            colorIndex++;
        });
        
        return { labels, datasets };
    }

    /**
     * 创建历史图表实例
     * @param {Object} chartData 图表数据
     */
    createHistoryChart(chartData) {
        const ctx = document.getElementById('assetHistoryChart');
        if (!ctx) return;

        // 销毁现有图表
        if (this.historyChartInstance) {
            this.historyChartInstance.destroy();
        }

        this.historyChartInstance = new Chart(ctx, {
            type: 'line',
            data: chartData,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        display: true,
                        title: {
                            display: true,
                            text: '时间'
                        }
                    },
                    y: {
                        display: true,
                        title: {
                            display: true,
                            text: '价值 (USD)'
                        },
                        ticks: {
                            callback: (value) => '$' + formatNumber(value)
                        }
                    }
                },
                plugins: {
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                return `${context.dataset.label}: $${formatNumber(context.parsed.y)}`;
                            }
                        }
                    },
                    legend: {
                        display: true
                    }
                },
                animation: {
                    duration: CONFIG.CHART.ANIMATION_DURATION
                }
            }
        });
    }

    /**
     * 显示历史图表加载状态
     * @param {boolean} show 是否显示
     */
    showHistoryChartLoading(show) {
        const loadingElement = document.getElementById('historyChartLoading');
        if (loadingElement) {
            loadingElement.style.display = show ? 'flex' : 'none';
        }
    }

    /**
     * 显示历史图表空状态
     */
    showHistoryChartEmptyState() {
        const historyChartEmptyState = document.getElementById('historyChartEmptyState');
        const chartInfoPanel = document.getElementById('chartInfoPanel');
        
        if (historyChartEmptyState) {
            historyChartEmptyState.style.display = 'block';
        }
        
        if (chartInfoPanel) {
            chartInfoPanel.style.display = 'none';
        }
    }

    /**
     * 更新图表信息面板
     * @param {Array} historyData 历史数据
     */
    updateChartInfoPanel(historyData) {
        const infoPanel = document.getElementById('chartInfoPanel');
        if (!infoPanel || !historyData || historyData.length === 0) return;

        const latestData = historyData[historyData.length - 1];
        const previousData = historyData.length > 1 ? historyData[historyData.length - 2] : null;
        
        const currentValue = latestData.total_value_usdc || 0;
        const previousValue = previousData ? (previousData.total_value_usdc || 0) : 0;
        const change = currentValue - previousValue;
        const changePercent = previousValue > 0 ? ((change / previousValue) * 100) : 0;
        
        const startDate = new Date(historyData[0].timestamp);
        const endDate = new Date(latestData.timestamp);
        const timeSpan = formatTimeSpan(startDate, endDate);
        
        infoPanel.innerHTML = `
            <div class="info-item">
                <span class="info-label">当前价值:</span>
                <span class="info-value">$${formatNumber(currentValue)}</span>
            </div>
            <div class="info-item">
                <span class="info-label">变化:</span>
                <span class="info-value ${change >= 0 ? 'positive' : 'negative'}">
                    ${change >= 0 ? '+' : ''}$${formatNumber(Math.abs(change))} 
                    (${changePercent >= 0 ? '+' : ''}${changePercent.toFixed(2)}%)
                </span>
            </div>
            <div class="info-item">
                <span class="info-label">时间范围:</span>
                <span class="info-value">${timeSpan}</span>
            </div>
            <div class="info-item">
                <span class="info-label">数据点:</span>
                <span class="info-value">${historyData.length}</span>
            </div>
        `;
    }

    /**
     * 导出历史图表
     */
    exportHistoryChart() {
        if (!this.historyChartInstance) {
            this.uiManager.showNotification('没有可导出的图表', 'warning');
            return;
        }

        try {
            const url = this.historyChartInstance.toBase64Image();
            const link = document.createElement('a');
            link.download = `asset-history-chart-${new Date().toISOString().split('T')[0]}.png`;
            link.href = url;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            
            this.uiManager.showNotification('图表导出成功', 'success');
        } catch (error) {
            console.error('导出图表失败:', error);
            this.uiManager.showNotification('图表导出失败: ' + error.message, 'error');
        }
    }

    /**
     * 应用趋势图表筛选条件
     * @param {Array} historyData 历史数据
     * @returns {Array} 筛选后的数据
     */
    applyTrendFilters(historyData) {
        if (!historyData || !Array.isArray(historyData)) {
            return [];
        }
        
        return historyData.map(timePoint => {
            // 确保timePoint和assets存在
            if (!timePoint || typeof timePoint !== 'object') {
                return {
                    ...timePoint,
                    assets: [],
                    total_value_usdc: 0
                };
            }
            
            // 获取资产数组，如果不存在则使用空数组
            const assets = timePoint.assets || [];
            
            // 对每个时间点的资产数据应用筛选
            const filteredAssets = assets.filter(asset => {
                if (!asset || typeof asset !== 'object') {
                    return false;
                }
                
                // 区块链筛选
                if (this.trendFilters.chain && asset.chain_name !== this.trendFilters.chain) {
                    return false;
                }
                
                // 地址筛选
                if (this.trendFilters.address && asset.address !== this.trendFilters.address) {
                    return false;
                }
                
                // 代币筛选
                if (this.trendFilters.token && asset.token_symbol !== this.trendFilters.token) {
                    return false;
                }
                
                return true;
            });
            
            // 重新计算总价值
            const totalValue = filteredAssets.reduce((sum, asset) => sum + (asset.value_usdc || 0), 0);
            
            return {
                ...timePoint,
                assets: filteredAssets,
                total_value_usdc: totalValue
            };
        });
    }

    /**
     * 更新趋势图表地址选项
     */
    async updateTrendAddressOptions() {
        const addressFilter = document.getElementById('trendAddressFilter');
        if (!addressFilter) return;
        
        // 保存当前选择
        const currentValue = addressFilter.value;
        
        // 清空选项
        addressFilter.innerHTML = '<option value="">全部地址</option>';
        
        try {
            // 获取当前资产数据
            let assets = window.app?.assetManager?.filteredAssets || [];
            
            // 如果没有资产数据，尝试从API获取
            if (assets.length === 0) {
                const response = await this.apiService.getAssets();
                assets = response || [];
            }
            
            // 根据区块链筛选获取地址
            const filteredAssets = this.trendFilters.chain 
                ? assets.filter(asset => asset.chain_name === this.trendFilters.chain)
                : assets;
                
            console.log(`筛选前资产数量: ${assets.length}, 筛选后资产数量: ${filteredAssets.length}, 筛选条件: ${this.trendFilters.chain}`);
            
            // 获取唯一地址，过滤掉空值
            const addresses = [...new Set(filteredAssets
                .map(asset => asset.address)
                .filter(address => address && address.trim() !== '')
            )];
            
            // 添加地址选项
            addresses.forEach(address => {
                const option = document.createElement('option');
                option.value = address;
                option.textContent = this.formatAddress(address);
                addressFilter.appendChild(option);
            });
            
            // 恢复选择（如果仍然有效）
            if (addresses.includes(currentValue)) {
                addressFilter.value = currentValue;
            } else {
                this.trendFilters.address = '';
            }
            
            console.log(`地址选项已更新，共${addresses.length}个地址`);
        } catch (error) {
            console.error('更新地址选项失败:', error);
        }
    }
    
    /**
     * 更新趋势图表代币选项
     */
    async updateTrendTokenOptions() {
        const tokenFilter = document.getElementById('trendTokenFilter');
        if (!tokenFilter) return;
        
        // 保存当前选择
        const currentValue = tokenFilter.value;
        
        // 清空选项
        tokenFilter.innerHTML = '<option value="">全部代币</option>';
        
        try {
            // 获取当前资产数据
            let assets = window.app?.assetManager?.filteredAssets || [];
            
            // 如果没有资产数据，尝试从API获取
            if (assets.length === 0) {
                const response = await this.apiService.getAssets();
                assets = response || [];
            }
            
            // 根据区块链和地址筛选获取代币
            let filteredAssets = assets;
            
            if (this.trendFilters.chain) {
                filteredAssets = filteredAssets.filter(asset => asset.chain_name === this.trendFilters.chain);
            }
            
            if (this.trendFilters.address) {
                filteredAssets = filteredAssets.filter(asset => asset.address === this.trendFilters.address);
            }
            
            // 获取唯一代币，过滤掉空值
            const tokens = [...new Set(filteredAssets
                .map(asset => asset.token_symbol)
                .filter(token => token && token.trim() !== '')
            )];
            
            // 添加代币选项
            tokens.forEach(token => {
                const option = document.createElement('option');
                option.value = token;
                option.textContent = token;
                tokenFilter.appendChild(option);
            });
            
            // 恢复选择（如果仍然有效）
            if (tokens.includes(currentValue)) {
                tokenFilter.value = currentValue;
            } else {
                this.trendFilters.token = '';
            }
            
            console.log(`代币选项已更新，共${tokens.length}个代币`);
        } catch (error) {
            console.error('更新代币选项失败:', error);
        }
    }
    
    /**
     * 格式化地址显示
     * @param {string} address 地址
     * @returns {string} 格式化后的地址
     */
    formatAddress(address) {
        if (!address) return '';
        if (address.length <= 12) return address;
        return `${address.slice(0, 6)}...${address.slice(-6)}`;
    }
    
    /**
     * 初始化趋势图表筛选器选项
     */
    async initTrendFilterOptions() {
        try {
            // 初始化区块链筛选器（确保有默认选项）
            this.initTrendChainOptions();
            
            // 初始化地址和代币筛选器
            await this.updateTrendAddressOptions();
            await this.updateTrendTokenOptions();
            
            console.log('趋势筛选器选项初始化完成');
        } catch (error) {
            console.error('初始化趋势筛选器选项失败:', error);
        }
    }

    /**
     * 初始化趋势图表区块链选项
     */
    initTrendChainOptions() {
        const chainFilter = document.getElementById('trendChainFilter');
        if (!chainFilter) return;
        
        // 确保有默认的"全部区块链"选项
        if (chainFilter.children.length === 0) {
            chainFilter.innerHTML = `
                <option value="">全部区块链</option>
                <option value="ethereum">Ethereum</option>
                <option value="arbitrum">Arbitrum One</option>
                <option value="base">Base</option>
                <option value="polygon">Polygon</option>
                <option value="bsc">BNB Smart Chain</option>
                <option value="solana">Solana</option>
                <option value="sui">Sui</option>
                <option value="bitcoin">Bitcoin</option>
            `;
        }
    }
} 
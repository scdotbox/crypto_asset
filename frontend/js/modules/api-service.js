/**
 * API服务模块
 * 
 * 统一管理所有API调用，包括资产、代币、价格等数据的获取和提交
 */

import { CONFIG, MESSAGES } from './config.js';

export class ApiService {
    constructor() {
        this.baseUrl = CONFIG.API_BASE_URL;
        this.tokenListCache = null;
        this.tokenListCacheTime = 0;
    }

    /**
     * 通用API请求方法
     * @param {string} endpoint API端点
     * @param {Object} options 请求选项
     * @returns {Promise<any>} API响应数据
     */
    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
            },
        };

        const finalOptions = { ...defaultOptions, ...options };

        try {
            const response = await fetch(url, finalOptions);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            console.error(`API请求失败 [${endpoint}]:`, error);
            throw error;
        }
    }

    /**
     * 获取资产列表
     * @param {Object} filters 筛选条件
     * @returns {Promise<Array>} 资产列表
     */
    async fetchAssets(filters = {}) {
        const queryParams = new URLSearchParams(filters).toString();
        const endpoint = queryParams ? `/assets?${queryParams}` : '/assets';
        return await this.request(endpoint);
    }

    /**
     * 添加新资产
     * @param {Object} assetData 资产数据
     * @returns {Promise<Object>} 添加结果
     */
    async addAsset(assetData) {
        return await this.request('/assets', {
            method: 'POST',
            body: JSON.stringify(assetData)
        });
    }

    /**
     * 更新资产
     * @param {string} assetId 资产ID
     * @param {Object} updateData 更新数据
     * @returns {Promise<Object>} 更新结果
     */
    async updateAsset(assetId, updateData) {
        return await this.request(`/assets/${assetId}`, {
            method: 'PUT',
            body: JSON.stringify(updateData)
        });
    }

    /**
     * 删除资产
     * @param {string} assetId 资产ID
     * @returns {Promise<Object>} 删除结果
     */
    async deleteAsset(assetId) {
        return await this.request(`/assets/${assetId}`, {
            method: 'DELETE'
        });
    }

    /**
     * 批量删除资产
     * @param {Array<string>} assetIds 资产ID列表
     * @returns {Promise<Object>} 删除结果
     */
    async batchDeleteAssets(assetIds) {
        return await this.request('/assets/batch-delete', {
            method: 'POST',
            body: JSON.stringify({ asset_ids: assetIds })
        });
    }

    /**
     * 批量更新资产
     * @param {Array<string>} assetIds 资产ID列表
     * @param {Object} updateData 更新数据
     * @returns {Promise<Object>} 更新结果
     */
    async batchUpdateAssets(assetIds, updateData) {
        return await this.request('/assets/batch-update', {
            method: 'POST',
            body: JSON.stringify({
                asset_ids: assetIds,
                update_data: updateData
            })
        });
    }

    /**
     * 检查资产是否存在
     * @param {Object} assetData 资产数据
     * @returns {Promise<Object>} 检查结果
     */
    async checkAssetExists(assetData) {
        return await this.request('/assets/check', {
            method: 'POST',
            body: JSON.stringify(assetData)
        });
    }



    /**
     * 验证合约地址
     * @param {string} contractAddress 合约地址
     * @param {string} chainName 链名称
     * @returns {Promise<Object>} 验证结果
     */
    async validateContractAddress(contractAddress, chainName) {
        const params = new URLSearchParams({
            contract_address: contractAddress,
            chain_name: chainName
        });
        return await this.request(`/tokens/validation/contract?${params}`);
    }

    /**
     * 通过合约地址获取代币信息
     * @param {string} contractAddress 合约地址
     * @param {string} chainName 链名称
     * @returns {Promise<Object>} 代币信息
     */
    async getTokenByContract(contractAddress, chainName) {
        return await this.request(`/tokens/contract/${chainName}/${contractAddress}`);
    }

    /**
     * 获取CoinGecko代币列表
     * @param {boolean} forceRefresh 是否强制刷新
     * @param {number} limit 数量限制
     * @returns {Promise<Array>} 代币列表
     */
    async getCoinGeckoTokensList(forceRefresh = false, limit = null) {
        // 检查缓存
        const now = Date.now();
        if (!forceRefresh && this.tokenListCache && 
            (now - this.tokenListCacheTime < CONFIG.CACHE.TOKEN_LIST_TTL)) {
            return this.tokenListCache;
        }

        const params = new URLSearchParams({ force_refresh: forceRefresh });
        if (limit) {
            params.append('limit', limit);
        }

        const response = await this.request(`/tokens/coingecko/list?${params}`);
        
        // 缓存结果
        if (response && response.data) {
            this.tokenListCache = response.data;
            this.tokenListCacheTime = now;
            return response.data;
        }

        return [];
    }

    /**
     * 获取代币库列表
     * @param {Object} filters 筛选条件
     * @returns {Promise<Array>} 代币列表
     */
    async getTokenLibrary(filters = {}) {
        const queryParams = new URLSearchParams(filters).toString();
        const endpoint = queryParams ? `/tokens?${queryParams}` : '/tokens';
        return await this.request(endpoint);
    }

    /**
     * 获取代币统计信息
     * @returns {Promise<Object>} 代币统计
     */
    async getTokenStatistics() {
        return await this.request('/tokens/statistics');
    }

    /**
     * 添加代币到库
     * @param {Object} tokenData 代币数据
     * @returns {Promise<Object>} 添加结果
     */
    async addTokenToLibrary(tokenData) {
        return await this.request('/tokens', {
            method: 'POST',
            body: JSON.stringify(tokenData)
        });
    }

    /**
     * 更新代币库中的代币
     * @param {number} tokenId 代币ID
     * @param {Object} updateData 更新数据
     * @returns {Promise<Object>} 更新结果
     */
    async updateTokenInLibrary(tokenId, updateData) {
        return await this.request(`/tokens/${tokenId}`, {
            method: 'PUT',
            body: JSON.stringify(updateData)
        });
    }

    /**
     * 从代币库删除代币
     * @param {number} tokenId 代币ID
     * @returns {Promise<Object>} 删除结果
     */
    async deleteTokenFromLibrary(tokenId) {
        return await this.request(`/tokens/${tokenId}`, {
            method: 'DELETE'
        });
    }

    /**
     * 获取资产历史数据
     * @param {Object} requestData 请求数据
     * @returns {Promise<Object>} 历史数据
     */
    async getAssetHistory(requestData) {
        return await this.request('/assets/history', {
            method: 'POST',
            body: JSON.stringify(requestData)
        });
    }

    /**
     * 保存资产快照
     * @returns {Promise<Object>} 保存结果
     */
    async saveAssetSnapshot() {
        return await this.request('/assets/save-snapshot', {
            method: 'POST'
        });
    }

    /**
     * 获取钱包名称列表
     * @returns {Promise<Array>} 钱包名称列表
     */
    async getWalletNames() {
        const response = await this.request('/wallets');
        return response.wallet_names || [];
    }

    /**
     * 获取区块链列表
     * @returns {Promise<Array>} 区块链列表
     */
    async getBlockchains() {
        return await this.request('/blockchains');
    }

    /**
     * 获取价格服务统计
     * @returns {Promise<Object>} 统计数据
     */
    async getPriceServiceStats() {
        return await this.request('/price-service/stats');
    }

    /**
     * 清空价格缓存
     * @returns {Promise<Object>} 操作结果
     */
    async clearPriceCache() {
        return await this.request('/price-service/clear-cache', {
            method: 'POST'
        });
    }

    /**
     * 获取数据库统计信息
     * @returns {Promise<Object>} 数据库统计
     */
    async getDatabaseStats() {
        return await this.request('/database/stats');
    }

    /**
     * 清空数据库
     * @returns {Promise<Object>} 操作结果
     */
    async clearDatabase() {
        return await this.request('/database/clear-all', {
            method: 'POST'
        });
    }

    /**
     * 重置数据库
     * @returns {Promise<Object>} 操作结果
     */
    async resetDatabase() {
        return await this.request('/database/reset', {
            method: 'POST'
        });
    }

    /**
     * 获取日志统计
     * @returns {Promise<Object>} 日志统计
     */
    async getLogStats() {
        return await this.request('/logs/stats');
    }

    /**
     * 清理日志文件
     * @param {number} days 保留天数
     * @returns {Promise<Object>} 操作结果
     */
    async cleanupLogs(days = 7) {
        return await this.request(`/logs/cleanup?days=${days}`, {
            method: 'POST'
        });
    }

    /**
     * 刷新资产价格
     * @returns {Promise<Object>} 刷新结果
     */
    async refreshAssetPrices() {
        return await this.request('/assets/refresh-prices', {
            method: 'POST'
        });
    }

    /**
     * 获取数据库统计
     * @returns {Promise<Object>} 数据库统计信息
     */
} 
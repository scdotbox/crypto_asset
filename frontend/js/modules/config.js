/**
 * 前端应用配置模块
 */

export const CONFIG = {
    // API配置
    API_BASE_URL: 'http://localhost:8010/api',
    
    // 图表配置
    CHART: {
        DEFAULT_COLORS: [
            '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF',
            '#FF9F40', '#FF6384', '#C9CBCF', '#4BC0C0', '#FF6384'
        ],
        ANIMATION_DURATION: 1000,
        RESPONSIVE: true
    },
    
    // 缓存配置
    CACHE: {
        TOKEN_LIST_TTL: 300000, // 5分钟
        HISTORY_DATA_TTL: 60000  // 1分钟
    },
    
    // UI配置
    UI: {
        NOTIFICATION_DURATION: 5000,
        DEBOUNCE_DELAY: 300,
        PAGINATION_SIZE: 20
    },
    
    // 验证配置
    VALIDATION: {
        ADDRESS_PATTERNS: {
            ethereum: /^0x[a-fA-F0-9]{40}$/,
            solana: /^[1-9A-HJ-NP-Za-km-z]{32,44}$/,
            bitcoin_legacy: /^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$/,
            bitcoin_bech32: /^bc1[a-z0-9]{39,59}$/,
            // Sui支持两种格式：标准地址(64字符)和coin type格式(包含::)
            sui: /^0x[a-fA-F0-9]{64}$|^0x[a-fA-F0-9]{64}::[a-zA-Z0-9_]+::[a-zA-Z0-9_]+$/
        }
    }
};

export const MESSAGES = {
    SUCCESS: {
        ASSET_ADDED: '资产添加成功',
        ASSET_UPDATED: '资产更新成功',
        ASSET_DELETED: '资产删除成功',
        DATA_REFRESHED: '数据刷新成功'
    },
    ERROR: {
        ASSET_ADD_FAILED: '添加资产失败',
        ASSET_UPDATE_FAILED: '更新资产失败',
        ASSET_DELETE_FAILED: '删除资产失败',
        DATA_LOAD_FAILED: '数据加载失败',
        INVALID_ADDRESS: '无效的地址格式',
        NETWORK_ERROR: '网络连接错误'
    },
    WARNING: {
        DUPLICATE_ASSET: '资产已存在',
        NO_DATA: '暂无数据'
    }
};

export const SUPPORTED_CHAINS = [
    { name: 'ethereum', displayName: 'Ethereum', nativeToken: 'ETH' },
    { name: 'arbitrum', displayName: 'Arbitrum One', nativeToken: 'ETH' },
    { name: 'base', displayName: 'Base', nativeToken: 'ETH' },
    { name: 'polygon', displayName: 'Polygon', nativeToken: 'MATIC' },
    { name: 'bsc', displayName: 'BNB Smart Chain', nativeToken: 'BNB' },
    { name: 'solana', displayName: 'Solana', nativeToken: 'SOL' },
    { name: 'sui', displayName: 'Sui', nativeToken: 'SUI' },
    { name: 'bitcoin', displayName: 'Bitcoin', nativeToken: 'BTC' }
]; 
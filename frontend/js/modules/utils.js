/**
 * 前端通用工具函数模块
 */

import { CONFIG, MESSAGES } from './config.js';

/**
 * 防抖函数
 * @param {Function} func 要防抖的函数
 * @param {number} wait 等待时间
 * @returns {Function} 防抖后的函数
 */
export function debounce(func, wait = CONFIG.UI.DEBOUNCE_DELAY) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * 格式化地址显示
 * @param {string} address 完整地址
 * @param {number} prefixLength 前缀长度
 * @param {number} suffixLength 后缀长度
 * @returns {string} 格式化后的地址
 */
export function formatAddress(address, prefixLength = 6, suffixLength = 4) {
    if (!address || address.length <= prefixLength + suffixLength) {
        return address;
    }
    return `${address.slice(0, prefixLength)}...${address.slice(-suffixLength)}`;
}

/**
 * 格式化链名称显示
 * @param {string} chainName 链名称
 * @returns {string} 格式化后的链名称
 */
export function formatChainName(chainName) {
    const chainMap = {
        'ethereum': 'Ethereum',
        'arbitrum': 'Arbitrum',
        'base': 'Base',
        'polygon': 'Polygon',
        'bsc': 'BSC',
        'solana': 'Solana',
        'sui': 'Sui',
        'bitcoin': 'Bitcoin'
    };
    return chainMap[chainName] || chainName.charAt(0).toUpperCase() + chainName.slice(1);
}

/**
 * 获取链图标
 * @param {string} chainName 链名称
 * @returns {string} 图标类名或符号
 */
export function getChainIcon(chainName) {
    const iconMap = {
        'ethereum': '⟠',
        'arbitrum': 'ᐱ',
        'base': '🔵',
        'polygon': '⬟',
        'bsc': '⭐',
        'solana': '◎',
        'sui': '💧',
        'bitcoin': '₿'
    };
    return iconMap[chainName] || '🔗';
}

/**
 * 格式化数字显示
 * @param {number} number 数字
 * @param {number} decimals 小数位数
 * @param {boolean} useCommas 是否使用千位分隔符
 * @returns {string} 格式化后的数字
 */
export function formatNumber(number, decimals = 2, useCommas = true) {
    if (number === undefined || number === null || isNaN(number)) {
        return '0.00';
    }

    // 处理极小的数字
    if (Math.abs(number) < Math.pow(10, -decimals) && number !== 0) {
        return `< ${Math.pow(10, -decimals).toFixed(decimals)}`;
    }

    const formatted = Number(number).toFixed(decimals);
    
    if (!useCommas) {
        return formatted;
    }

    // 添加千位分隔符
    const parts = formatted.split('.');
    parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    return parts.join('.');
}

/**
 * 验证地址格式
 * @param {string} address 地址
 * @param {string} chainName 链名称
 * @returns {boolean} 是否有效
 */
export function validateAddressFormat(address, chainName) {
    if (!address || !chainName) return false;

    const patterns = CONFIG.VALIDATION.ADDRESS_PATTERNS;
    
    switch (chainName.toLowerCase()) {
        case 'ethereum':
        case 'arbitrum':
        case 'base':
        case 'polygon':
        case 'bsc':
            return patterns.ethereum.test(address);
        case 'solana':
            return patterns.solana.test(address);
        case 'bitcoin':
            return patterns.bitcoin_legacy.test(address) || patterns.bitcoin_bech32.test(address);
        case 'sui':
            return patterns.sui.test(address);
        default:
            return true; // 对于未知链，暂时允许通过
    }
}

/**
 * 复制文本到剪贴板
 * @param {string} text 要复制的文本
 * @returns {Promise<boolean>} 是否复制成功
 */
export async function copyToClipboard(text) {
    try {
        if (navigator.clipboard && window.isSecureContext) {
            await navigator.clipboard.writeText(text);
            return true;
        } else {
            // 回退方法
            return fallbackCopyToClipboard(text);
        }
    } catch (error) {
        console.error('复制失败:', error);
        return fallbackCopyToClipboard(text);
    }
}

/**
 * 回退的复制方法
 * @param {string} text 要复制的文本
 * @returns {boolean} 是否复制成功
 */
function fallbackCopyToClipboard(text) {
    try {
        const textArea = document.createElement('textarea');
        textArea.value = text;
        textArea.style.position = 'fixed';
        textArea.style.left = '-999999px';
        textArea.style.top = '-999999px';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        
        const successful = document.execCommand('copy');
        document.body.removeChild(textArea);
        return successful;
    } catch (error) {
        console.error('回退复制方法失败:', error);
        return false;
    }
}

/**
 * 生成图表颜色
 * @param {number} count 颜色数量
 * @returns {Array<string>} 颜色数组
 */
export function generateChartColors(count) {
    const baseColors = CONFIG.CHART.DEFAULT_COLORS;
    const colors = [];
    
    for (let i = 0; i < count; i++) {
        if (i < baseColors.length) {
            colors.push(baseColors[i]);
        } else {
            // 生成新颜色
            const hue = (i * 137.508) % 360; // 使用黄金角度
            colors.push(`hsl(${hue}, 70%, 60%)`);
        }
    }
    
    return colors;
}

/**
 * 解析日期标签
 * @param {string} label 日期标签
 * @returns {Date} 日期对象
 */
export function parseDateLabel(label) {
    return new Date(label);
}

/**
 * 格式化日期标签
 * @param {Date} date 日期对象
 * @returns {string} 格式化后的日期
 */
export function formatDateLabel(date) {
    if (!date || !(date instanceof Date)) return '';
    
    const now = new Date();
    const diffTime = Math.abs(now - date);
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    
    if (diffDays <= 1) {
        return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
    } else if (diffDays <= 7) {
        return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
    } else {
        return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric', year: 'numeric' });
    }
}

/**
 * 计算时间跨度
 * @param {Date} startDate 开始日期
 * @param {Date} endDate 结束日期
 * @returns {string} 时间跨度描述
 */
export function formatTimeSpan(startDate, endDate) {
    if (!startDate || !endDate) return '';
    
    const diffTime = Math.abs(endDate - startDate);
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    
    if (diffDays <= 1) {
        return '1天内';
    } else if (diffDays <= 7) {
        return `${diffDays}天`;
    } else if (diffDays <= 30) {
        const weeks = Math.ceil(diffDays / 7);
        return `${weeks}周`;
    } else if (diffDays <= 365) {
        const months = Math.ceil(diffDays / 30);
        return `${months}个月`;
    } else {
        const years = Math.ceil(diffDays / 365);
        return `${years}年`;
    }
}

/**
 * 深拷贝对象
 * @param {any} obj 要拷贝的对象
 * @returns {any} 拷贝后的对象
 */
export function deepClone(obj) {
    if (obj === null || typeof obj !== 'object') return obj;
    if (obj instanceof Date) return new Date(obj.getTime());
    if (obj instanceof Array) return obj.map(item => deepClone(item));
    if (typeof obj === 'object') {
        const clonedObj = {};
        for (const key in obj) {
            if (obj.hasOwnProperty(key)) {
                clonedObj[key] = deepClone(obj[key]);
            }
        }
        return clonedObj;
    }
}

/**
 * 获取通知图标
 * @param {string} type 通知类型
 * @returns {string} 图标
 */
export function getNotificationIcon(type) {
    const iconMap = {
        'success': '✅',
        'error': '❌',
        'warning': '⚠️',
        'info': 'ℹ️'
    };
    return iconMap[type] || iconMap.info;
} 
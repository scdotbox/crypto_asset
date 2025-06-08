/**
 * 数据验证服务模块
 * 
 * 统一管理各种数据验证规则和方法
 */

import { CONFIG, MESSAGES } from './config.js';
import { validateAddressFormat } from './utils.js';

export class ValidationService {
    constructor() {
        this.errors = [];
    }

    /**
     * 清空错误列表
     */
    clearErrors() {
        this.errors = [];
    }

    /**
     * 添加错误信息
     * @param {string} field 字段名
     * @param {string} message 错误信息
     */
    addError(field, message) {
        this.errors.push({ field, message });
    }

    /**
     * 获取所有错误
     * @returns {Array} 错误列表
     */
    getErrors() {
        return this.errors;
    }

    /**
     * 检查是否有错误
     * @returns {boolean} 是否有错误
     */
    hasErrors() {
        return this.errors.length > 0;
    }

    /**
     * 验证资产输入数据
     * @param {Object} assetData 资产数据
     * @returns {boolean} 验证是否通过
     */
    validateAssetInput(assetData) {
        this.clearErrors();

        // 验证钱包地址
        if (!assetData.address || assetData.address.trim() === '') {
            this.addError('address', '钱包地址不能为空');
        } else if (!validateAddressFormat(assetData.address, assetData.chain_name)) {
            this.addError('address', `无效的${assetData.chain_name}地址格式`);
        }

        // 验证链名称
        if (!assetData.chain_name || assetData.chain_name === '') {
            this.addError('chain_name', '请选择区块链');
        }

        // 验证代币符号
        if (!assetData.token_symbol || assetData.token_symbol.trim() === '') {
            this.addError('token_symbol', '代币符号不能为空');
        } else if (!/^[A-Z0-9\-_]{1,20}$/i.test(assetData.token_symbol)) {
            this.addError('token_symbol', '代币符号格式无效（仅支持字母、数字、连字符和下划线，最长20位）');
        }

        // 验证合约地址（如果提供）
        if (assetData.token_contract_address && assetData.token_contract_address.trim() !== '') {
            if (!this.validateContractAddress(assetData.token_contract_address, assetData.chain_name)) {
                this.addError('token_contract_address', '合约地址格式无效');
            }
        }

        // 验证钱包名称（可选）
        if (assetData.wallet_name && assetData.wallet_name.length > 50) {
            this.addError('wallet_name', '钱包名称不能超过50个字符');
        }

        // 验证标签（可选）
        if (assetData.tag && assetData.tag.length > 50) {
            this.addError('tag', '标签不能超过50个字符');
        }

        // 验证备注（可选）
        if (assetData.notes && assetData.notes.length > 200) {
            this.addError('notes', '备注不能超过200个字符');
        }

        return !this.hasErrors();
    }

    /**
     * 验证代币输入数据
     * @param {Object} tokenData 代币数据
     * @returns {boolean} 验证是否通过
     */
    validateTokenInput(tokenData) {
        this.clearErrors();

        // 验证代币符号
        if (!tokenData.symbol || tokenData.symbol.trim() === '') {
            this.addError('symbol', '代币符号不能为空');
        } else if (!/^[A-Z0-9\-_]{1,20}$/i.test(tokenData.symbol)) {
            this.addError('symbol', '代币符号格式无效');
        }

        // 验证代币名称
        if (!tokenData.name || tokenData.name.trim() === '') {
            this.addError('name', '代币名称不能为空');
        } else if (tokenData.name.length > 100) {
            this.addError('name', '代币名称不能超过100个字符');
        }

        // 验证链名称
        if (!tokenData.chainName || tokenData.chainName === '') {
            this.addError('chainName', '请选择区块链');
        }

        // 验证合约地址
        if (!tokenData.contractAddress || tokenData.contractAddress.trim() === '') {
            this.addError('contractAddress', '合约地址不能为空');
        } else if (!this.validateContractAddress(tokenData.contractAddress, tokenData.chainName)) {
            this.addError('contractAddress', '合约地址格式无效');
        }

        // 验证小数位数
        if (tokenData.decimals !== undefined && tokenData.decimals !== null) {
            if (!Number.isInteger(tokenData.decimals) || tokenData.decimals < 0 || tokenData.decimals > 18) {
                this.addError('decimals', '小数位数必须是0-18之间的整数');
            }
        }

        // 验证描述（可选）
        if (tokenData.description && tokenData.description.length > 500) {
            this.addError('description', '描述不能超过500个字符');
        }

        return !this.hasErrors();
    }

    /**
     * 验证合约地址格式
     * @param {string} contractAddress 合约地址
     * @param {string} chainName 链名称
     * @returns {boolean} 是否有效
     */
    validateContractAddress(contractAddress, chainName) {
        if (!contractAddress || !chainName) return false;

        const patterns = CONFIG.VALIDATION.ADDRESS_PATTERNS;
        
        switch (chainName.toLowerCase()) {
            case 'ethereum':
            case 'arbitrum':
            case 'base':
            case 'polygon':
            case 'bsc':
                return patterns.ethereum.test(contractAddress);
            case 'solana':
                return patterns.solana.test(contractAddress);
            case 'sui':
                return patterns.sui.test(contractAddress);
            default:
                // 对于未知链，允许通用地址格式
                return contractAddress.length >= 10;
        }
    }

    /**
     * 验证批量编辑数据
     * @param {Object} updateData 更新数据
     * @returns {boolean} 验证是否通过
     */
    validateBatchEditData(updateData) {
        this.clearErrors();

        // 验证钱包名称（如果提供）
        if (updateData.walletName !== undefined) {
            if (updateData.walletName && updateData.walletName.length > 50) {
                this.addError('walletName', '钱包名称不能超过50个字符');
            }
        }

        // 验证标签（如果提供）
        if (updateData.tags !== undefined) {
            if (Array.isArray(updateData.tags) && updateData.tags.length > 5) {
                this.addError('tags', '标签数量不能超过5个');
            }
        }

        // 验证备注（如果提供）
        if (updateData.notes !== undefined) {
            if (updateData.notes && updateData.notes.length > 500) {
                this.addError('notes', '备注不能超过500个字符');
            }
        }

        return !this.hasErrors();
    }

    /**
     * 验证筛选条件
     * @param {Object} filters 筛选条件
     * @returns {boolean} 验证是否通过
     */
    validateFilters(filters) {
        this.clearErrors();

        // 验证地址筛选
        if (filters.address && filters.address.trim() !== '') {
            if (filters.address.length < 3) {
                this.addError('address', '地址筛选条件至少需要3个字符');
            }
        }

        // 验证数量范围
        if (filters.minAmount !== undefined && filters.maxAmount !== undefined) {
            if (filters.minAmount > filters.maxAmount) {
                this.addError('amount', '最小数量不能大于最大数量');
            }
        }

        return !this.hasErrors();
    }

    /**
     * 验证历史查询参数
     * @param {Object} params 查询参数
     * @returns {boolean} 验证是否通过
     */
    validateHistoryParams(params) {
        this.clearErrors();

        // 验证时间范围
        if (params.startTime && params.endTime) {
            const startDate = new Date(params.startTime);
            const endDate = new Date(params.endTime);
            
            if (isNaN(startDate.getTime()) || isNaN(endDate.getTime())) {
                this.addError('dateRange', '无效的日期格式');
            } else if (startDate >= endDate) {
                this.addError('dateRange', '开始时间必须早于结束时间');
            }
        }

        // 验证时间间隔
        const validIntervals = ['1h', '4h', '1d', '1w', '1M'];
        if (params.interval && !validIntervals.includes(params.interval)) {
            this.addError('interval', '无效的时间间隔');
        }

        // 验证限制数量
        if (params.limit !== undefined) {
            if (!Number.isInteger(params.limit) || params.limit < 1 || params.limit > 1000) {
                this.addError('limit', '数量限制必须是1-1000之间的整数');
            }
        }

        return !this.hasErrors();
    }

    /**
     * 格式化错误信息为字符串
     * @returns {string} 格式化的错误信息
     */
    getErrorsAsString() {
        return this.errors.map(error => `${error.field}: ${error.message}`).join('\n');
    }

    /**
     * 获取特定字段的错误
     * @param {string} field 字段名
     * @returns {Array} 该字段的错误列表
     */
    getFieldErrors(field) {
        return this.errors.filter(error => error.field === field);
    }

    /**
     * 验证数量是否为有效数字
     * @param {any} value 数值
     * @param {string} fieldName 字段名称
     * @param {boolean} allowZero 是否允许为0
     * @returns {boolean} 是否有效
     */
    validateNumber(value, fieldName, allowZero = true) {
        if (value === undefined || value === null || value === '') {
            return true; // 空值由其他验证规则处理
        }

        const num = Number(value);
        if (isNaN(num)) {
            this.addError(fieldName, '必须是有效数字');
            return false;
        }

        if (!allowZero && num === 0) {
            this.addError(fieldName, '不能为0');
            return false;
        }

        if (num < 0) {
            this.addError(fieldName, '不能为负数');
            return false;
        }

        return true;
    }

    /**
     * 验证字符串长度
     * @param {string} value 字符串值
     * @param {string} fieldName 字段名称
     * @param {number} minLength 最小长度
     * @param {number} maxLength 最大长度
     * @returns {boolean} 是否有效
     */
    validateStringLength(value, fieldName, minLength = 0, maxLength = Infinity) {
        if (!value) {
            if (minLength > 0) {
                this.addError(fieldName, `不能为空`);
                return false;
            }
            return true;
        }

        if (value.length < minLength) {
            this.addError(fieldName, `至少需要${minLength}个字符`);
            return false;
        }

        if (value.length > maxLength) {
            this.addError(fieldName, `不能超过${maxLength}个字符`);
            return false;
        }

        return true;
    }
} 
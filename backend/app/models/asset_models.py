"""
资产相关的数据模型
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator
import uuid


class AssetInput(BaseModel):
    """用户录入资产时的请求模型"""

    address: str = Field(..., description="钱包地址", min_length=1)
    chain_name: str = Field(..., description="区块链名称")
    token_symbol: str = Field(..., description="代币符号")
    token_contract_address: Optional[str] = Field(
        None, description="代币合约地址，原生代币可为空"
    )
    wallet_name: Optional[str] = Field(None, description="钱包名称，用于标识不同钱包")
    notes: Optional[str] = Field(None, description="备注信息")
    tag: Optional[str] = Field(None, description="资产标签")

    @field_validator("address")
    @classmethod
    def validate_address_format(cls, v):
        """基础地址格式验证"""
        if not v or len(v.strip()) == 0:
            raise ValueError("地址不能为空")
        return v.strip()

    @model_validator(mode='after')
    def validate_address_for_chain(self):
        """根据链类型验证地址格式"""
        address = self.address
        chain_name = self.chain_name.lower()
        
        # 根据链类型验证地址格式
        if chain_name in ["ethereum", "arbitrum", "base", "polygon", "bsc"]:
            # 以太坊类地址格式验证 (0x 开头，40 字符)
            if not (address.startswith("0x") and len(address) == 42):
                raise ValueError(f"无效的{chain_name}地址格式")
            self.address = address.lower()
            
        elif chain_name == "solana":
            # Solana 地址格式验证 (Base58, 32-44 字符)
            if not (len(address) >= 32 and len(address) <= 44 and address.isalnum()):
                raise ValueError("无效的solana地址格式")
            # 简单的 Base58 字符检查
            base58_chars = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
            if not all(c in base58_chars for c in address):
                raise ValueError("无效的solana地址格式")
                
        elif chain_name == "sui":
            # Sui 地址格式验证 (0x 开头，64 字符)
            if not (address.startswith("0x") and len(address) == 66):
                raise ValueError("无效的sui地址格式")
            self.address = address.lower()
            
        elif chain_name == "bitcoin":
            # Bitcoin 地址格式验证
            # Legacy (P2PKH): 1 开头，25-34 字符
            # SegWit (P2SH): 3 开头，25-34 字符  
            # Bech32 (P2WPKH/P2WSH): bc1 开头
            is_legacy = (address.startswith("1") or address.startswith("3")) and 25 <= len(address) <= 34
            is_bech32 = address.startswith("bc1") and len(address) >= 39
            if not (is_legacy or is_bech32):
                raise ValueError("无效的bitcoin地址格式")
        else:
            raise ValueError(f"不支持的区块链: {chain_name}")
            
        return self

    @field_validator("chain_name")
    @classmethod
    def validate_chain_name(cls, v):
        """验证链名称"""
        supported_chains = [
            "ethereum",
            "arbitrum",
            "base",
            "polygon",
            "bsc",
            "solana",
            "sui",
            "bitcoin",
        ]
        if v.lower() not in supported_chains:
            raise ValueError(f"不支持的区块链: {v}")
        return v.lower()

    @field_validator("token_symbol")
    @classmethod
    def validate_token_symbol(cls, v):
        """验证代币符号"""
        if not v or len(v.strip()) == 0:
            raise ValueError("代币符号不能为空")
        return v.upper()

    @field_validator("wallet_name")
    @classmethod
    def validate_wallet_name(cls, v):
        """验证钱包名称"""
        if v is not None:
            v = v.strip()
            if len(v) == 0:
                return None
            if len(v) > 50:
                raise ValueError("钱包名称长度不能超过50个字符")
        return v

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, v):
        """验证备注"""
        if v is not None:
            v = v.strip()
            if len(v) == 0:
                return None
            if len(v) > 200:
                raise ValueError("备注长度不能超过200个字符")
        return v


class AssetUpdateInput(BaseModel):
    """更新资产时的请求模型"""
    
    wallet_name: Optional[str] = Field(None, description="钱包名称")
    notes: Optional[str] = Field(None, description="备注信息")
    tag: Optional[str] = Field(None, description="资产标签")

    @field_validator("wallet_name")
    @classmethod
    def validate_wallet_name(cls, v):
        """验证钱包名称"""
        if v is not None:
            v = v.strip()
            if len(v) == 0:
                return None
            if len(v) > 50:
                raise ValueError("钱包名称长度不能超过50个字符")
        return v

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, v):
        """验证备注"""
        if v is not None:
            v = v.strip()
            if len(v) == 0:
                return None
            if len(v) > 200:
                raise ValueError("备注长度不能超过200个字符")
        return v


class AssetData(BaseModel):
    """存储在文件中的资产数据模型"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    address: str
    chain_name: str
    token_symbol: str
    token_contract_address: Optional[str] = None
    wallet_name: Optional[str] = None
    notes: Optional[str] = None
    tag: Optional[str] = None
    created_at: str = Field(default_factory=lambda: str(uuid.uuid4()))


class AssetDisplay(BaseModel):
    """返回给前端的资产展示模型"""

    id: str
    address: str
    chain_name: str
    token_symbol: str
    token_contract_address: Optional[str] = None
    wallet_name: Optional[str] = None
    notes: Optional[str] = None
    tag: Optional[str] = None
    quantity: float = Field(..., description="代币数量")
    price_usdc: float = Field(..., description="USDC 价格")
    value_usdc: float = Field(..., description="总价值（USDC）")


class AssetResponse(BaseModel):
    """添加资产的响应模型"""

    message: str
    asset: AssetData


class EnhancedAssetResponse(BaseModel):
    """增强的资产响应模型，包含状态信息"""

    message: str
    asset: AssetData
    status: str = Field(..., description="状态：'created' 表示新创建，'existing' 表示已存在")
    is_duplicate: bool = Field(False, description="是否为重复资产")


class ErrorResponse(BaseModel):
    """错误响应模型"""

    detail: str
    error_code: Optional[str] = None


class AssetSummary(BaseModel):
    """资产汇总模型"""

    total_value_usdc: float
    total_assets: int
    chains_summary: List[dict]
    addresses_summary: List[dict]


class TagResponse(BaseModel):
    """标签响应模型"""

    tags: List[str] = Field(..., description="所有可用的标签列表")


# 钱包创建时间相关模型
class WalletCreationInfo(BaseModel):
    """钱包创建时间信息模型"""
    
    address: str = Field(..., description="钱包地址")
    chain_name: str = Field(..., description="区块链名称")
    creation_timestamp: Optional[int] = Field(None, description="创建时间戳（Unix时间戳）")
    creation_date: Optional[str] = Field(None, description="创建日期（ISO格式）")
    first_transaction_hash: Optional[str] = Field(None, description="第一笔交易哈希")
    block_number: Optional[int] = Field(None, description="第一笔交易所在区块号")
    is_estimated: bool = Field(False, description="是否为估算时间")
    error_message: Optional[str] = Field(None, description="查询错误信息")


class WalletCreationResponse(BaseModel):
    """钱包创建时间查询响应模型"""
    
    success: bool = Field(..., description="查询是否成功")
    data: Optional[WalletCreationInfo] = Field(None, description="钱包创建信息")
    message: str = Field(..., description="响应消息")


# 自动发现代币相关模型
class DiscoveredToken(BaseModel):
    """发现的代币信息模型"""
    
    symbol: str = Field(..., description="代币符号")
    name: Optional[str] = Field(None, description="代币名称")
    contract_address: Optional[str] = Field(None, description="合约地址，原生代币为None")
    balance: float = Field(..., description="代币余额")
    decimals: int = Field(18, description="小数位数")
    is_native: bool = Field(False, description="是否为原生代币")
    price_usdc: Optional[float] = Field(None, description="USDC价格")
    value_usdc: Optional[float] = Field(None, description="总价值（USDC）")


class WalletDiscoveryRequest(BaseModel):
    """钱包代币发现请求模型"""
    
    address: str = Field(..., description="钱包地址")
    chain_name: str = Field(..., description="区块链名称")
    include_zero_balance: bool = Field(False, description="是否包含零余额代币")
    min_value_usdc: float = Field(0.01, description="最小价值阈值（USDC）")


class WalletDiscoveryResponse(BaseModel):
    """钱包代币发现响应模型"""
    
    success: bool = Field(..., description="发现是否成功")
    address: str = Field(..., description="钱包地址")
    chain_name: str = Field(..., description="区块链名称")
    discovered_tokens: List[DiscoveredToken] = Field(..., description="发现的代币列表")
    total_count: int = Field(..., description="发现的代币总数")
    total_value_usdc: float = Field(..., description="总价值（USDC）")
    message: str = Field(..., description="响应消息")


class BatchAddTokensRequest(BaseModel):
    """批量添加代币请求模型"""
    
    address: str = Field(..., description="钱包地址")
    chain_name: str = Field(..., description="区块链名称")
    tokens: List[str] = Field(..., description="要添加的代币符号列表")
    wallet_name: Optional[str] = Field(None, description="钱包名称")
    tag: Optional[str] = Field(None, description="资产标签")


class BatchAddTokensResponse(BaseModel):
    """批量添加代币响应模型"""
    
    success: bool = Field(..., description="添加是否成功")
    added_assets: List[AssetData] = Field(..., description="成功添加的资产列表")
    failed_tokens: List[dict] = Field(..., description="添加失败的代币列表")
    total_added: int = Field(..., description="成功添加的数量")
    total_failed: int = Field(..., description="添加失败的数量")
    message: str = Field(..., description="响应消息")


# 资产历史数据相关模型
class AssetHistoryPoint(BaseModel):
    """资产历史数据点模型"""
    
    timestamp: int = Field(..., description="时间戳（Unix时间戳）")
    date: str = Field(..., description="日期（ISO格式）")
    quantity: float = Field(..., description="代币数量")
    price_usdc: float = Field(..., description="USDC价格")
    value_usdc: float = Field(..., description="总价值（USDC）")


class AssetHistoryData(BaseModel):
    """单个资产的历史数据模型"""
    
    asset_id: str = Field(..., description="资产ID")
    address: str = Field(..., description="钱包地址")
    chain_name: str = Field(..., description="区块链名称")
    token_symbol: str = Field(..., description="代币符号")
    token_contract_address: Optional[str] = Field(None, description="代币合约地址")
    tag: Optional[str] = Field(None, description="资产标签")
    history_points: List[AssetHistoryPoint] = Field(..., description="历史数据点列表")
    wallet_creation_date: Optional[str] = Field(None, description="钱包创建日期")


class AssetHistoryRequest(BaseModel):
    """资产历史数据请求模型"""
    
    asset_id: Optional[str] = Field(None, description="特定资产ID，为空则查询所有资产")
    address: Optional[str] = Field(None, description="特定钱包地址，为空则查询所有地址")
    chain_name: Optional[str] = Field(None, description="特定区块链，为空则查询所有链")
    token_symbol: Optional[str] = Field(None, description="特定代币符号，为空则查询所有代币")
    start_date: Optional[str] = Field(None, description="开始日期（ISO格式），为空则从钱包创建时间开始")
    end_date: Optional[str] = Field(None, description="结束日期（ISO格式），为空则到当前时间")
    time_range: Optional[str] = Field(None, description="时间范围：1d, 7d, 30d, 90d, 1y等，会覆盖start_date和end_date")
    interval: str = Field("1d", description="数据间隔：1h, 1d, 1w, 1m")


class AssetHistoryResponse(BaseModel):
    """资产历史数据响应模型"""
    
    success: bool = Field(..., description="查询是否成功")
    data: List[AssetHistoryData] = Field(..., description="资产历史数据列表")
    total_count: int = Field(..., description="资产总数")
    date_range: dict = Field(..., description="实际查询的日期范围")
    message: str = Field(..., description="响应消息")


# 代币库相关模型
class TokenInfo(BaseModel):
    """代币信息模型"""

    symbol: str = Field(..., description="代币符号")
    name: str = Field(..., description="代币名称")
    chain_name: str = Field(..., description="所属链名称")
    contract_address: Optional[str] = Field(None, description="合约地址")
    decimals: int = Field(18, description="小数位数")
    coingecko_id: Optional[str] = Field(None, description="CoinGecko ID")
    is_predefined: bool = Field(False, description="是否为预定义代币")
    created_at: str = Field(..., description="创建时间")


class TokenLibraryResponse(BaseModel):
    """代币库响应模型"""

    tokens: List[TokenInfo] = Field(..., description="代币列表")
    total_count: int = Field(..., description="代币总数")


class TokenSuggestionResponse(BaseModel):
    """代币建议响应模型"""

    suggestions: List[TokenInfo] = Field(..., description="建议的代币列表")


class QuickAddTokenRequest(BaseModel):
    """快速添加代币请求模型"""

    address: str = Field(..., description="钱包地址")
    chain_name: str = Field(..., description="区块链名称")
    token_symbol: str = Field(..., description="代币符号")
    tag: Optional[str] = Field(None, description="资产标签")


class HistoryDataPoint(BaseModel):
    """历史数据点基础模型"""
    
    timestamp: int = Field(..., description="时间戳（Unix时间戳）")
    date: str = Field(..., description="日期（ISO格式）")
    value: float = Field(..., description="数值")


class PriceHistoryPoint(HistoryDataPoint):
    """价格历史数据点模型"""
    
    timestamp: int = Field(..., description="时间戳（Unix时间戳）")
    date: str = Field(..., description="日期（ISO格式）")
    token_symbol: str = Field(..., description="代币符号")
    chain_name: Optional[str] = Field(None, description="区块链名称")
    price_usdc: float = Field(..., description="USDC价格")
    coingecko_id: Optional[str] = Field(None, description="CoinGecko ID")
    
    @property
    def value(self) -> float:
        """返回价格值"""
        return self.price_usdc


class BalanceHistoryPoint(HistoryDataPoint):
    """余额历史数据点模型"""
    
    timestamp: int = Field(..., description="时间戳（Unix时间戳）")
    date: str = Field(..., description="日期（ISO格式）")
    address: str = Field(..., description="钱包地址")
    chain_name: str = Field(..., description="区块链名称")
    token_symbol: str = Field(..., description="代币符号")
    token_contract_address: Optional[str] = Field(None, description="代币合约地址")
    balance: float = Field(..., description="代币余额")
    
    @property
    def value(self) -> float:
        """返回余额值"""
        return self.balance


class HistoryCacheStats(BaseModel):
    """历史缓存统计信息模型"""
    
    price_cache_size: int = Field(..., description="价格缓存条目数")
    balance_cache_size: int = Field(..., description="余额缓存条目数")
    oldest_price_record: Optional[str] = Field(None, description="最早的价格记录时间")
    newest_price_record: Optional[str] = Field(None, description="最新的价格记录时间")
    oldest_balance_record: Optional[str] = Field(None, description="最早的余额记录时间")
    newest_balance_record: Optional[str] = Field(None, description="最新的余额记录时间")
    total_tokens_tracked: int = Field(..., description="跟踪的代币总数")
    total_addresses_tracked: int = Field(..., description="跟踪的地址总数")


class HistoryQueryRequest(BaseModel):
    """历史数据查询请求模型"""
    
    start_date: Optional[str] = Field(None, description="开始日期（ISO格式）")
    end_date: Optional[str] = Field(None, description="结束日期（ISO格式）")
    token_symbol: Optional[str] = Field(None, description="代币符号")
    chain_name: Optional[str] = Field(None, description="区块链名称")
    address: Optional[str] = Field(None, description="钱包地址")
    interval_hours: int = Field(1, description="数据间隔（小时）")
    limit: int = Field(1000, description="返回记录数限制")


class PriceHistoryResponse(BaseModel):
    """价格历史数据响应模型"""
    
    success: bool = Field(..., description="查询是否成功")
    data: List[PriceHistoryPoint] = Field(..., description="价格历史数据列表")
    total_count: int = Field(..., description="总记录数")
    date_range: dict = Field(..., description="实际查询的日期范围")
    message: str = Field(..., description="响应消息")


class BalanceHistoryResponse(BaseModel):
    """余额历史数据响应模型"""
    
    success: bool = Field(..., description="查询是否成功")
    data: List[BalanceHistoryPoint] = Field(..., description="余额历史数据列表")
    total_count: int = Field(..., description="总记录数")
    date_range: dict = Field(..., description="实际查询的日期范围")
    message: str = Field(..., description="响应消息")


class HistoryUpdateRequest(BaseModel):
    """历史数据更新请求模型"""
    
    force_update: bool = Field(False, description="是否强制更新")
    start_date: Optional[str] = Field(None, description="更新开始日期")
    end_date: Optional[str] = Field(None, description="更新结束日期")
    token_symbols: Optional[List[str]] = Field(None, description="指定更新的代币列表")
    addresses: Optional[List[str]] = Field(None, description="指定更新的地址列表")


class HistoryUpdateResponse(BaseModel):
    """历史数据更新响应模型"""
    
    success: bool = Field(..., description="更新是否成功")
    updated_price_records: int = Field(..., description="更新的价格记录数")
    updated_balance_records: int = Field(..., description="更新的余额记录数")
    failed_updates: List[dict] = Field(..., description="更新失败的记录")
    message: str = Field(..., description="响应消息")
    duration_seconds: float = Field(..., description="更新耗时（秒）")


class TokenInput(BaseModel):
    """代币输入模型"""
    symbol: str = Field(..., description="代币符号")
    name: Optional[str] = Field(None, description="代币名称")
    chain_name: str = Field(..., description="区块链名称")
    contract_address: Optional[str] = Field(None, description="合约地址")
    decimals: Optional[int] = Field(18, description="小数位数")
    coingecko_id: Optional[str] = Field(None, description="CoinGecko ID")

    @model_validator(mode='after')
    def validate_contract_address_for_chain(self):
        """根据链类型验证合约地址格式"""
        if not self.contract_address:
            return self
            
        contract_address = self.contract_address.strip()
        chain_name = self.chain_name.lower()
        
        # 根据链类型验证合约地址格式
        if chain_name in ["ethereum", "arbitrum", "base", "polygon", "bsc"]:
            # EVM链合约地址格式验证 (0x 开头，40 字符)
            if not (contract_address.startswith("0x") and len(contract_address) == 42):
                raise ValueError(f"无效的{chain_name}合约地址格式")
            self.contract_address = contract_address.lower()
            
        elif chain_name == "solana":
            # Solana 合约地址格式验证 (Base58, 32-44 字符)
            if not (len(contract_address) >= 32 and len(contract_address) <= 44):
                raise ValueError("无效的solana合约地址格式")
            # 简单的 Base58 字符检查
            base58_chars = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
            if not all(c in base58_chars for c in contract_address):
                raise ValueError("无效的solana合约地址格式")
                
        elif chain_name == "sui":
            # Sui 支持两种格式：
            # 1. 标准地址格式: 0x + 64个十六进制字符
            # 2. Coin type格式: 0x + 64个十六进制字符 + :: + module + :: + type
            import re
            
            # 标准地址格式
            standard_pattern = r'^0x[a-fA-F0-9]{64}$'
            # Coin type格式
            coin_type_pattern = r'^0x[a-fA-F0-9]{64}::[a-zA-Z0-9_]+::[a-zA-Z0-9_]+$'
            
            if not (re.match(standard_pattern, contract_address) or re.match(coin_type_pattern, contract_address)):
                raise ValueError("无效的sui合约地址格式。支持标准地址(0x+64字符)或coin type格式(0x+64字符::module::type)")
            self.contract_address = contract_address.lower()
            
        elif chain_name == "bitcoin":
            # Bitcoin 不支持智能合约
            raise ValueError("Bitcoin不支持智能合约代币")
        else:
            # 对于其他链，进行基本验证
            if len(contract_address) < 10:
                raise ValueError(f"无效的{chain_name}合约地址格式")
            
        return self

    @field_validator("chain_name")
    @classmethod
    def validate_chain_name(cls, v):
        """验证链名称"""
        supported_chains = [
            "ethereum",
            "arbitrum", 
            "base",
            "polygon",
            "bsc",
            "solana",
            "sui",
        ]
        if v.lower() not in supported_chains:
            raise ValueError(f"不支持的区块链: {v}")
        return v.lower()

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, v):
        """验证代币符号"""
        if not v or len(v.strip()) == 0:
            raise ValueError("代币符号不能为空")
        return v.upper().strip()

    @field_validator("decimals")
    @classmethod
    def validate_decimals(cls, v):
        """验证小数位数"""
        if v is not None and (v < 0 or v > 18):
            raise ValueError("小数位数必须在0-18之间")
        return v


class TokenData(BaseModel):
    """代币数据模型"""
    id: int = Field(..., description="代币ID")
    symbol: str = Field(..., description="代币符号")
    name: str = Field(..., description="代币名称")
    chain_name: str = Field(..., description="区块链名称")
    contract_address: Optional[str] = Field(None, description="合约地址")
    decimals: int = Field(18, description="小数位数")
    coingecko_id: Optional[str] = Field(None, description="CoinGecko ID")
    is_predefined: bool = Field(False, description="是否为预定义代币")
    is_active: bool = Field(True, description="是否激活")
    created_at: Optional[str] = Field(None, description="创建时间")


class TokenUpdateInput(BaseModel):
    """代币更新输入模型"""
    name: Optional[str] = Field(None, description="代币名称")
    decimals: Optional[int] = Field(None, description="小数位数")
    coingecko_id: Optional[str] = Field(None, description="CoinGecko ID")


class WalletData(BaseModel):
    """钱包数据模型"""
    id: int = Field(..., description="钱包ID")
    address: str = Field(..., description="钱包地址")
    chain_name: str = Field(..., description="区块链名称")
    wallet_name: Optional[str] = Field(None, description="钱包名称")
    notes: Optional[str] = Field(None, description="备注")
    creation_timestamp: Optional[int] = Field(None, description="创建时间戳")
    creation_date: Optional[str] = Field(None, description="创建日期")
    first_transaction_hash: Optional[str] = Field(None, description="首次交易哈希")
    block_number: Optional[int] = Field(None, description="区块号")
    is_estimated: bool = Field(False, description="是否为估算时间")
    created_at: Optional[str] = Field(None, description="记录创建时间")


class BlockchainData(BaseModel):
    """区块链数据模型"""
    id: int = Field(..., description="区块链ID")
    name: str = Field(..., description="区块链名称")
    display_name: str = Field(..., description="显示名称")
    rpc_url: str = Field(..., description="RPC URL")
    explorer_url: Optional[str] = Field(None, description="浏览器URL")
    chain_type: str = Field("evm", description="链类型")
    is_active: bool = Field(True, description="是否激活")
    created_at: Optional[str] = Field(None, description="创建时间")


class DatabaseStatsResponse(BaseModel):
    """数据库统计响应模型"""
    total_assets: int = Field(..., description="总资产数")
    total_wallets: int = Field(..., description="总钱包数")
    total_tokens: int = Field(..., description="总代币数")
    total_blockchains: int = Field(..., description="总区块链数")
    predefined_tokens: int = Field(..., description="预定义代币数")
    custom_tokens: int = Field(..., description="自定义代币数")
    active_assets: int = Field(..., description="活跃资产数")
    chain_statistics: List[Dict[str, Any]] = Field(..., description="按链统计")
    wallet_statistics: List[Dict[str, Any]] = Field(..., description="按钱包统计")


class DatabaseClearResponse(BaseModel):
    """数据库清空响应模型"""
    
    success: bool = Field(..., description="操作是否成功")
    message: str = Field(..., description="操作结果消息")
    cleared_counts: Dict[str, int] = Field(..., description="各表清空的记录数")
    total_cleared: int = Field(..., description="总共清空的记录数")


class DatabaseResetResponse(BaseModel):
    """数据库重置响应模型"""
    
    success: bool = Field(..., description="操作是否成功")
    message: str = Field(..., description="操作结果消息")
    cleared_records: Optional[int] = Field(default=None, description="清空的记录总数")
    steps_completed: List[str] = Field(..., description="完成的步骤列表")

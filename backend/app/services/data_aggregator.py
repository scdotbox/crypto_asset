"""
数据聚合层核心服务

实现多链数据提供商API的统一接口，支持ETH、SOL、SUI、BNB等多条链的数据聚合
采用混合策略：主要多链聚合API + 特定链专用API
"""

import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import httpx
from abc import ABC, abstractmethod

from app.core.logger import get_logger
from app.core.config import settings
from app.models.asset_models import DiscoveredToken

logger = get_logger(__name__)


class DataProviderType(Enum):
    """数据提供商类型枚举"""
    MULTI_CHAIN = "multi_chain"  # 多链聚合API
    CHAIN_SPECIFIC = "chain_specific"  # 特定链API
    FALLBACK = "fallback"  # 备用API


class DataProviderPriority(Enum):
    """数据提供商优先级"""
    PRIMARY = 1    # 主要提供商
    SECONDARY = 2  # 次要提供商
    FALLBACK = 3   # 备用提供商


class BaseDataProvider(ABC):
    """数据提供商基类"""
    
    def __init__(self, name: str, provider_type: DataProviderType, priority: DataProviderPriority):
        self.name = name
        self.provider_type = provider_type
        self.priority = priority
        self.http_client = httpx.AsyncClient(timeout=30.0)
        self.rate_limit_delay = 1.0  # 默认请求间隔
        self.last_request_time = 0
        self.error_count = 0
        self.max_errors = 5
        
    @abstractmethod
    async def get_wallet_assets(
        self, 
        address: str, 
        chain_name: str, 
        include_zero_balance: bool = False
    ) -> List[DiscoveredToken]:
        """获取钱包资产"""
        pass
    
    @abstractmethod
    async def get_token_balance(
        self, 
        address: str, 
        token_contract: Optional[str], 
        chain_name: str
    ) -> float:
        """获取代币余额"""
        pass
    
    @abstractmethod
    async def get_token_price(self, token_symbol: str, chain_name: str) -> Optional[float]:
        """获取代币价格"""
        pass
    
    @abstractmethod
    def supports_chain(self, chain_name: str) -> bool:
        """检查是否支持指定链"""
        pass
    
    async def _rate_limit(self):
        """实施速率限制"""
        current_time = asyncio.get_event_loop().time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - time_since_last)
        self.last_request_time = asyncio.get_event_loop().time()
    
    def is_healthy(self) -> bool:
        """检查提供商是否健康"""
        return self.error_count < self.max_errors
    
    def record_error(self):
        """记录错误"""
        self.error_count += 1
        logger.warning(f"数据提供商 {self.name} 错误计数: {self.error_count}")
    
    def reset_errors(self):
        """重置错误计数"""
        self.error_count = 0


class CovalentProvider(BaseDataProvider):
    """Covalent API 提供商 - 支持200+链的多链聚合API"""
    
    def __init__(self):
        super().__init__("Covalent", DataProviderType.MULTI_CHAIN, DataProviderPriority.PRIMARY)
        self.api_key = getattr(settings, 'covalent_api_key', "")
        self.base_url = "https://api.covalenthq.com/v1"
        self.supported_chains = {
            "ethereum": "eth-mainnet",
            "polygon": "matic-mainnet", 
            "bsc": "bsc-mainnet",
            "arbitrum": "arbitrum-mainnet",
            "base": "base-mainnet"
        }
        self.rate_limit_delay = 0.5  # Covalent允许较高的请求频率
    
    def supports_chain(self, chain_name: str) -> bool:
        return chain_name.lower() in self.supported_chains
    
    async def get_wallet_assets(
        self, 
        address: str, 
        chain_name: str, 
        include_zero_balance: bool = False
    ) -> List[DiscoveredToken]:
        """获取钱包资产"""
        if not self.supports_chain(chain_name):
            return []
        
        try:
            await self._rate_limit()
            
            chain_id = self.supported_chains[chain_name.lower()]
            url = f"{self.base_url}/{chain_id}/address/{address}/balances_v2/"
            
            params = {
                "key": self.api_key,
                "nft": "false",
                "no-nft-fetch": "true"
            }
            
            response = await self.http_client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            tokens = []
            
            if data.get("data") and data["data"].get("items"):
                for item in data["data"]["items"]:
                    balance = float(item.get("balance", 0)) / (10 ** item.get("contract_decimals", 18))
                    
                    if not include_zero_balance and balance == 0:
                        continue
                    
                    # 判断是否为原生代币（contract_address为None或空字符串）
                    contract_address = item.get("contract_address")
                    is_native = not contract_address or contract_address.strip() == ""
                    
                    token = DiscoveredToken(
                        symbol=item.get("contract_ticker_symbol", "UNKNOWN"),
                        name=item.get("contract_name", ""),
                        contract_address=contract_address,
                        balance=balance,
                        decimals=item.get("contract_decimals", 18),
                        is_native=is_native,
                        price_usdc=item.get("quote_rate"),
                        value_usdc=item.get("quote", 0)
                    )
                    tokens.append(token)
            
            self.reset_errors()
            return tokens
            
        except Exception as e:
            self.record_error()
            logger.error(f"Covalent获取钱包资产失败 {address} on {chain_name}: {e}")
            return []
    
    async def get_token_balance(
        self, 
        address: str, 
        token_contract: Optional[str], 
        chain_name: str
    ) -> float:
        """获取代币余额"""
        assets = await self.get_wallet_assets(address, chain_name, include_zero_balance=True)
        
        for asset in assets:
            if token_contract is None and asset.is_native:
                return asset.balance
            elif token_contract and asset.contract_address and asset.contract_address.lower() == token_contract.lower():
                return asset.balance
        
        return 0.0
    
    async def get_token_price(self, token_symbol: str, chain_name: str) -> Optional[float]:
        """获取代币价格 - Covalent主要提供余额数据，价格数据有限"""
        # Covalent的价格数据通过余额查询获得，这里返回None让其他提供商处理
        return None


class DataAggregatorService:
    """数据聚合服务 - 统一管理多个数据提供商"""
    
    def __init__(self):
        self.providers: List[BaseDataProvider] = []
        self.provider_cache: Dict[str, Any] = {}
        self.cache_ttl = 300  # 5分钟缓存
        self._initialize_providers()
        
    def _initialize_providers(self):
        """初始化所有数据提供商"""
        # 导入所有提供商类
        from app.services.data_providers import (
            ZerionProvider, ZapperProvider, AlchemyProvider, 
            MobulaProvider, DeBankProvider, BitqueryProvider, MoralisProvider,
            BlockVisionSuiProvider
        )
        
        # 按优先级添加提供商
        provider_classes = [
            CovalentProvider,       # 主要多链聚合API
            BlockVisionSuiProvider, # Sui链专用高精度API (优先级最高)
            ZerionProvider,         # DeFi专业数据
            ZapperProvider,         # DeFi协议聚合
            AlchemyProvider,        # 高性能基础设施
            DeBankProvider,         # DeFi数据聚合
            MobulaProvider,         # Sui链专用 (备用)
            BitqueryProvider,       # GraphQL数据分析
            MoralisProvider,        # Web3开发平台
        ]
        
        for provider_class in provider_classes:
            try:
                provider = provider_class()
                self.providers.append(provider)
                logger.info(f"已初始化数据提供商: {provider.name}")
            except Exception as e:
                logger.error(f"初始化数据提供商失败 {provider_class.__name__}: {e}")
        
        # 按优先级排序
        self.providers.sort(key=lambda p: p.priority.value)
        logger.info(f"数据聚合器已初始化，共 {len(self.providers)} 个提供商")
    
    async def get_wallet_assets(
        self, 
        address: str, 
        chain_name: str, 
        include_zero_balance: bool = False
    ) -> List[DiscoveredToken]:
        """获取钱包资产 - 使用多提供商策略"""
        cache_key = f"assets:{address}:{chain_name}:{include_zero_balance}"
        
        # 检查缓存
        if cache_key in self.provider_cache:
            cache_data = self.provider_cache[cache_key]
            if datetime.now().timestamp() - cache_data["timestamp"] < self.cache_ttl:
                logger.debug(f"使用缓存的钱包资产数据: {address}")
                return cache_data["data"]
        
        # 获取支持该链的提供商
        compatible_providers = [
            p for p in self.providers 
            if p.supports_chain(chain_name) and p.is_healthy()
        ]
        
        if not compatible_providers:
            logger.warning(f"没有可用的数据提供商支持链 {chain_name}")
            return []
        
        # 按优先级尝试提供商
        for provider in compatible_providers:
            try:
                logger.debug(f"尝试使用 {provider.name} 获取 {address} 在 {chain_name} 的资产")
                assets = await provider.get_wallet_assets(address, chain_name, include_zero_balance)
                
                if assets:
                    # 缓存结果
                    self.provider_cache[cache_key] = {
                        "data": assets,
                        "timestamp": datetime.now().timestamp(),
                        "provider": provider.name
                    }
                    
                    logger.info(f"成功使用 {provider.name} 获取到 {len(assets)} 个资产")
                    return assets
                    
            except Exception as e:
                logger.error(f"提供商 {provider.name} 获取资产失败: {e}")
                provider.record_error()
                continue
        
        logger.warning(f"所有提供商都无法获取 {address} 在 {chain_name} 的资产")
        return []
    
    async def get_token_balance(
        self, 
        address: str, 
        token_contract: Optional[str], 
        chain_name: str
    ) -> float:
        """获取代币余额 - 使用多提供商策略"""
        cache_key = f"balance:{address}:{token_contract}:{chain_name}"
        
        # 检查缓存
        if cache_key in self.provider_cache:
            cache_data = self.provider_cache[cache_key]
            if datetime.now().timestamp() - cache_data["timestamp"] < self.cache_ttl:
                return cache_data["data"]
        
        # 获取支持该链的提供商
        compatible_providers = [
            p for p in self.providers 
            if p.supports_chain(chain_name) and p.is_healthy()
        ]
        
        # 按优先级尝试提供商
        for provider in compatible_providers:
            try:
                balance = await provider.get_token_balance(address, token_contract, chain_name)
                
                if balance > 0:
                    # 缓存结果
                    self.provider_cache[cache_key] = {
                        "data": balance,
                        "timestamp": datetime.now().timestamp(),
                        "provider": provider.name
                    }
                    
                    return balance
                    
            except Exception as e:
                logger.error(f"提供商 {provider.name} 获取余额失败: {e}")
                provider.record_error()
                continue
        
        return 0.0
    
    async def get_token_price(self, token_symbol: str, chain_name: str) -> Optional[float]:
        """获取代币价格 - 使用多提供商策略"""
        cache_key = f"price:{token_symbol}:{chain_name}"
        
        # 检查缓存
        if cache_key in self.provider_cache:
            cache_data = self.provider_cache[cache_key]
            if datetime.now().timestamp() - cache_data["timestamp"] < self.cache_ttl:
                return cache_data["data"]
        
        # 获取支持该链的提供商
        compatible_providers = [
            p for p in self.providers 
            if p.supports_chain(chain_name) and p.is_healthy()
        ]
        
        # 按优先级尝试提供商
        for provider in compatible_providers:
            try:
                price = await provider.get_token_price(token_symbol, chain_name)
                
                if price is not None:
                    # 缓存结果
                    self.provider_cache[cache_key] = {
                        "data": price,
                        "timestamp": datetime.now().timestamp(),
                        "provider": provider.name
                    }
                    
                    return price
                    
            except Exception as e:
                logger.error(f"提供商 {provider.name} 获取价格失败: {e}")
                provider.record_error()
                continue
        
        return None
    
    def get_provider_status(self) -> Dict[str, Any]:
        """获取所有提供商的状态"""
        status = {
            "total_providers": len(self.providers),
            "healthy_providers": len([p for p in self.providers if p.is_healthy()]),
            "providers": []
        }
        
        for provider in self.providers:
            provider_info = {
                "name": provider.name,
                "type": provider.provider_type.value,
                "priority": provider.priority.value,
                "is_healthy": provider.is_healthy(),
                "error_count": provider.error_count,
                "max_errors": provider.max_errors,
                "supported_chains": []
            }
            
            # 检查支持的链
            test_chains = ["ethereum", "polygon", "bsc", "arbitrum", "base", "solana", "sui"]
            for chain in test_chains:
                if provider.supports_chain(chain):
                    provider_info["supported_chains"].append(chain)
            
            status["providers"].append(provider_info)
        
        return status
    
    def clear_cache(self):
        """清空缓存"""
        self.provider_cache.clear()
        logger.info("数据聚合器缓存已清空")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        current_time = datetime.now().timestamp()
        valid_cache = 0
        expired_cache = 0
        
        for cache_data in self.provider_cache.values():
            if current_time - cache_data["timestamp"] < self.cache_ttl:
                valid_cache += 1
            else:
                expired_cache += 1
        
        return {
            "total_cache_entries": len(self.provider_cache),
            "valid_cache_entries": valid_cache,
            "expired_cache_entries": expired_cache,
            "cache_ttl_seconds": self.cache_ttl
        }


# 创建全局数据聚合器实例
data_aggregator = DataAggregatorService() 
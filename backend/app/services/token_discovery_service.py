"""
增强的代币发现服务

实现多层次的代币发现机制：
1. 主要API发现
2. 备用API发现
3. 手动添加机制
4. 智能过滤和去重
5. 增强的缓存管理
"""

import asyncio
from typing import Dict, List, Optional, Set, Tuple, Any
from datetime import datetime, timedelta
import json

from app.core.logger import get_logger
from app.core.config import settings, PREDEFINED_TOKENS
from app.models.asset_models import DiscoveredToken
from app.services.data_aggregator import data_aggregator
from app.services.blockchain_service import BlockchainService

logger = get_logger(__name__)


class TokenDiscoveryService:
    """增强的代币发现服务"""
    
    def __init__(self):
        self.blockchain_service = BlockchainService()
        self.discovery_cache: Dict[str, List[DiscoveredToken]] = {}
        self.cache_ttl = getattr(settings, 'aggregator_cache_ttl', 300)  # 5分钟缓存
        self.last_cache_time: Dict[str, datetime] = {}
        
        # 代币过滤配置
        self.min_value_threshold = settings.token_discovery_min_value_usd
        self.include_zero_balance = settings.token_discovery_include_zero_balance
        
        # 增强的垃圾代币过滤列表
        self.spam_tokens = {
            "ethereum": {
                "SPAM", "SCAM", "FAKE", "TEST", "AIRDROP", "FREE", "CLAIM", 
                "BONUS", "GIFT", "REWARD", "WIN", "LUCKY", "PRIZE"
            },
            "bsc": {
                "SPAM", "SCAM", "FAKE", "TEST", "AIRDROP", "FREE", "CLAIM",
                "BONUS", "GIFT", "REWARD", "WIN", "LUCKY", "PRIZE", "SAFEMOON"
            },
            "polygon": {
                "SPAM", "SCAM", "FAKE", "TEST", "AIRDROP", "FREE", "CLAIM",
                "BONUS", "GIFT", "REWARD", "WIN", "LUCKY", "PRIZE"
            },
            "arbitrum": {
                "SPAM", "SCAM", "FAKE", "TEST", "AIRDROP", "FREE", "CLAIM",
                "BONUS", "GIFT", "REWARD", "WIN", "LUCKY", "PRIZE"
            },
            "base": {
                "SPAM", "SCAM", "FAKE", "TEST", "AIRDROP", "FREE", "CLAIM",
                "BONUS", "GIFT", "REWARD", "WIN", "LUCKY", "PRIZE"
            }
        }
        
        # 可疑代币名称模式
        self.suspicious_patterns = [
            "visit", "claim", "bonus", "airdrop", "free", "gift", "reward",
            "win", "lucky", "prize", "spam", "scam", "fake", "test"
        ]
    
    async def discover_wallet_tokens(
        self,
        address: str,
        chain_name: str,
        include_zero_balance: Optional[bool] = None,
        min_value_usdc: Optional[float] = None,
        use_cache: bool = True,
        force_refresh: bool = False
    ) -> List[DiscoveredToken]:
        """
        发现钱包中的代币
        
        Args:
            address: 钱包地址
            chain_name: 区块链名称
            include_zero_balance: 是否包含零余额代币
            min_value_usdc: 最小价值阈值
            use_cache: 是否使用缓存
            force_refresh: 是否强制刷新
            
        Returns:
            发现的代币列表
        """
        # 使用默认配置
        if include_zero_balance is None:
            include_zero_balance = self.include_zero_balance
        if min_value_usdc is None:
            min_value_usdc = self.min_value_threshold
        
        cache_key = f"{address}:{chain_name}:{include_zero_balance}:{min_value_usdc}"
        
        # 检查缓存
        if use_cache and not force_refresh and self._is_cache_valid(cache_key):
            logger.info(f"使用缓存的代币发现结果: {address} on {chain_name}")
            return self.discovery_cache[cache_key]
        
        logger.info(f"开始发现钱包代币: {address} on {chain_name}")
        
        # 多层次发现策略
        discovered_tokens = []
        
        # 1. 使用数据聚合器发现（主要策略）
        if settings.data_aggregator_enabled:
            try:
                aggregator_tokens = await data_aggregator.get_wallet_assets(
                    address, chain_name, include_zero_balance
                )
                if aggregator_tokens:
                    discovered_tokens.extend(aggregator_tokens)
                    logger.info(f"数据聚合器发现 {len(aggregator_tokens)} 个代币")
            except Exception as e:
                logger.error(f"数据聚合器发现失败: {e}")
        
        # 2. 使用区块链服务发现（备用策略）
        if not discovered_tokens and settings.fallback_to_blockchain_service:
            try:
                blockchain_tokens = await self.blockchain_service.discover_wallet_tokens(
                    address, chain_name, include_zero_balance, min_value_usdc
                )
                if blockchain_tokens:
                    discovered_tokens.extend(blockchain_tokens)
                    logger.info(f"区块链服务发现 {len(blockchain_tokens)} 个代币")
            except Exception as e:
                logger.error(f"区块链服务发现失败: {e}")
        
        # 3. 添加预定义代币（如果钱包中有余额）
        predefined_tokens = await self._check_predefined_tokens(address, chain_name)
        if predefined_tokens:
            discovered_tokens.extend(predefined_tokens)
            logger.info(f"预定义代币检查发现 {len(predefined_tokens)} 个代币")
        
        # 4. 去重和过滤
        filtered_tokens = self._filter_and_deduplicate_tokens(
            discovered_tokens, min_value_usdc, include_zero_balance
        )
        
        # 5. 增强价格信息
        enhanced_tokens = await self._enhance_token_prices(filtered_tokens, chain_name)
        
        # 6. 缓存结果
        if use_cache:
            self.discovery_cache[cache_key] = enhanced_tokens
            self.last_cache_time[cache_key] = datetime.now()
        
        logger.info(f"代币发现完成: {address} on {chain_name}, 发现 {len(enhanced_tokens)} 个代币")
        return enhanced_tokens
    
    async def _enhance_token_prices(
        self, 
        tokens: List[DiscoveredToken], 
        chain_name: str
    ) -> List[DiscoveredToken]:
        """增强代币价格信息"""
        enhanced_tokens = []
        
        for token in tokens:
            # 如果代币没有价格信息，尝试获取
            if token.price_usdc is None:
                try:
                    price = await data_aggregator.get_token_price(token.symbol, chain_name)
                    if price is not None:
                        token.price_usdc = price
                        token.value_usdc = token.balance * price
                except Exception as e:
                    logger.debug(f"获取代币 {token.symbol} 价格失败: {e}")
            
            enhanced_tokens.append(token)
        
        return enhanced_tokens
    
    async def _check_predefined_tokens(
        self, 
        address: str, 
        chain_name: str
    ) -> List[DiscoveredToken]:
        """检查预定义代币的余额"""
        predefined_tokens = []
        
        if chain_name not in PREDEFINED_TOKENS:
            return predefined_tokens
        
        chain_tokens = PREDEFINED_TOKENS[chain_name]
        
        # 并发检查所有预定义代币的余额
        tasks = []
        for symbol, token_info in chain_tokens.items():
            task = self._check_single_token_balance(
                address, chain_name, symbol, token_info
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, DiscoveredToken):
                predefined_tokens.append(result)
            elif isinstance(result, Exception):
                logger.warning(f"检查预定义代币余额失败: {result}")
        
        return predefined_tokens
    
    async def _check_single_token_balance(
        self,
        address: str,
        chain_name: str,
        symbol: str,
        token_info: dict
    ) -> Optional[DiscoveredToken]:
        """检查单个代币的余额"""
        try:
            # 首先尝试使用数据聚合器
            balance = 0.0
            if settings.data_aggregator_enabled:
                balance = await data_aggregator.get_token_balance(
                    address, token_info.get("contract_address"), chain_name
                )
            
            # 如果数据聚合器没有结果，使用区块链服务
            if balance == 0.0 and settings.fallback_to_blockchain_service:
                balance = await self.blockchain_service.get_token_balance(
                    address, token_info.get("contract_address"), chain_name
                )
            
            if balance > 0:
                return DiscoveredToken(
                    symbol=symbol,
                    name=token_info.get("name", ""),
                    contract_address=token_info.get("contract_address"),
                    balance=balance,
                    decimals=token_info.get("decimals", 18),
                    is_native=token_info.get("contract_address") is None,
                    price_usdc=None,  # 价格将在后续步骤中获取
                    value_usdc=None
                )
            
            return None
            
        except Exception as e:
            logger.error(f"检查代币 {symbol} 余额失败: {e}")
            return None
    
    def _filter_and_deduplicate_tokens(
        self,
        tokens: List[DiscoveredToken],
        min_value_usdc: float,
        include_zero_balance: bool
    ) -> List[DiscoveredToken]:
        """过滤和去重代币"""
        if not tokens:
            return []
        
        # 1. 去重 - 基于合约地址和符号
        unique_tokens = {}
        for token in tokens:
            # 创建唯一键
            if token.contract_address:
                key = f"contract:{token.contract_address.lower()}"
            else:
                key = f"native:{token.symbol.upper()}"
            
            # 如果已存在，选择余额更高的
            if key in unique_tokens:
                if token.balance > unique_tokens[key].balance:
                    unique_tokens[key] = token
            else:
                unique_tokens[key] = token
        
        # 2. 过滤垃圾代币
        filtered_tokens = []
        for token in unique_tokens.values():
            if self._is_spam_token(token):
                logger.debug(f"过滤垃圾代币: {token.symbol}")
                continue
            
            # 3. 过滤零余额代币
            if not include_zero_balance and token.balance == 0:
                continue
            
            # 4. 过滤低价值代币
            if token.value_usdc is not None and token.value_usdc < min_value_usdc:
                logger.debug(f"过滤低价值代币: {token.symbol} (${token.value_usdc:.4f})")
                continue
            
            filtered_tokens.append(token)
        
        # 5. 按价值排序（价值高的在前）
        filtered_tokens.sort(
            key=lambda t: t.value_usdc if t.value_usdc is not None else 0, 
            reverse=True
        )
        
        return filtered_tokens
    
    def _is_spam_token(self, token: DiscoveredToken) -> bool:
        """检查是否为垃圾代币"""
        symbol = token.symbol.upper()
        name = token.name.lower() if token.name else ""
        
        # 检查符号是否在垃圾列表中
        for chain_spam_tokens in self.spam_tokens.values():
            if symbol in chain_spam_tokens:
                return True
        
        # 检查名称是否包含可疑模式
        for pattern in self.suspicious_patterns:
            if pattern in name:
                return True
        
        # 检查是否为明显的测试代币
        if len(symbol) > 20 or symbol.startswith("TEST") or symbol.endswith("TEST"):
            return True
        
        # 检查是否为空名称或符号
        if not symbol or symbol == "UNKNOWN":
            return True
        
        return False
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """检查缓存是否有效"""
        if cache_key not in self.discovery_cache:
            return False
        
        if cache_key not in self.last_cache_time:
            return False
        
        cache_age = datetime.now() - self.last_cache_time[cache_key]
        return cache_age.total_seconds() < self.cache_ttl
    
    async def add_manual_token(
        self,
        address: str,
        chain_name: str,
        token_contract: Optional[str],
        token_symbol: str
    ) -> Optional[DiscoveredToken]:
        """
        手动添加代币
        
        Args:
            address: 钱包地址
            chain_name: 区块链名称
            token_contract: 代币合约地址（原生代币为None）
            token_symbol: 代币符号
            
        Returns:
            发现的代币信息，如果余额为0则返回None
        """
        if not settings.manual_token_addition_enabled:
            logger.warning("手动添加代币功能已禁用")
            return None
        
        try:
            logger.info(f"手动添加代币: {token_symbol} for {address} on {chain_name}")
            
            # 获取代币余额
            balance = 0.0
            if settings.data_aggregator_enabled:
                balance = await data_aggregator.get_token_balance(
                    address, token_contract, chain_name
                )
            
            # 如果数据聚合器没有结果，使用区块链服务
            if balance == 0.0 and settings.fallback_to_blockchain_service:
                balance = await self.blockchain_service.get_token_balance(
                    address, token_contract, chain_name
                )
            
            if balance > 0:
                # 尝试获取代币价格
                price = None
                if settings.data_aggregator_enabled:
                    price = await data_aggregator.get_token_price(token_symbol, chain_name)
                
                token = DiscoveredToken(
                    symbol=token_symbol.upper(),
                    name="",  # 手动添加的代币可能没有名称
                    contract_address=token_contract,
                    balance=balance,
                    decimals=18,  # 默认精度
                    is_native=token_contract is None,
                    price_usdc=price,
                    value_usdc=balance * price if price else None
                )
                
                # 清除相关缓存
                self._clear_address_cache(address, chain_name)
                
                logger.info(f"成功手动添加代币: {token_symbol}, 余额: {balance}")
                return token
            else:
                logger.warning(f"代币 {token_symbol} 余额为0，未添加")
                return None
                
        except Exception as e:
            logger.error(f"手动添加代币失败: {e}")
            return None
    
    def _clear_address_cache(self, address: str, chain_name: str):
        """清除特定地址的缓存"""
        keys_to_remove = []
        for cache_key in self.discovery_cache.keys():
            if cache_key.startswith(f"{address}:{chain_name}:"):
                keys_to_remove.append(cache_key)
        
        for key in keys_to_remove:
            del self.discovery_cache[key]
            if key in self.last_cache_time:
                del self.last_cache_time[key]
        
        logger.debug(f"已清除 {address} 在 {chain_name} 的缓存")
    
    async def batch_discover_tokens(
        self,
        addresses: List[str],
        chain_name: str,
        include_zero_balance: bool = False,
        min_value_usdc: float = 0.01,
        max_concurrent: int = 5
    ) -> Dict[str, List[DiscoveredToken]]:
        """
        批量发现多个地址的代币
        
        Args:
            addresses: 钱包地址列表
            chain_name: 区块链名称
            include_zero_balance: 是否包含零余额代币
            min_value_usdc: 最小价值阈值
            max_concurrent: 最大并发数
            
        Returns:
            地址到代币列表的映射
        """
        logger.info(f"开始批量发现代币: {len(addresses)} 个地址 on {chain_name}")
        
        # 创建信号量限制并发数
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def discover_single_address(address: str) -> Tuple[str, List[DiscoveredToken]]:
            async with semaphore:
                try:
                    tokens = await self.discover_wallet_tokens(
                        address, chain_name, include_zero_balance, min_value_usdc
                    )
                    return address, tokens
                except Exception as e:
                    logger.error(f"批量发现失败 {address}: {e}")
                    return address, []
        
        # 并发执行所有地址的代币发现
        tasks = [discover_single_address(addr) for addr in addresses]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 整理结果
        discovery_results = {}
        for result in results:
            if isinstance(result, tuple):
                address, tokens = result
                discovery_results[address] = tokens
            else:
                logger.error(f"批量发现异常: {result}")
        
        total_tokens = sum(len(tokens) for tokens in discovery_results.values())
        logger.info(f"批量发现完成: {len(discovery_results)} 个地址，共 {total_tokens} 个代币")
        
        return discovery_results
    
    def clear_cache(self):
        """清空所有缓存"""
        self.discovery_cache.clear()
        self.last_cache_time.clear()
        logger.info("代币发现服务缓存已清空")
    
    def clear_expired_cache(self):
        """清理过期缓存"""
        current_time = datetime.now()
        expired_keys = []
        
        for cache_key, cache_time in self.last_cache_time.items():
            if (current_time - cache_time).total_seconds() > self.cache_ttl:
                expired_keys.append(cache_key)
        
        for key in expired_keys:
            if key in self.discovery_cache:
                del self.discovery_cache[key]
            del self.last_cache_time[key]
        
        logger.info(f"已清理 {len(expired_keys)} 个过期缓存条目")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        current_time = datetime.now()
        valid_cache = 0
        expired_cache = 0
        
        for cache_time in self.last_cache_time.values():
            if (current_time - cache_time).total_seconds() < self.cache_ttl:
                valid_cache += 1
            else:
                expired_cache += 1
        
        return {
            "total_cache_entries": len(self.discovery_cache),
            "valid_cache_entries": valid_cache,
            "expired_cache_entries": expired_cache,
            "cache_ttl_seconds": self.cache_ttl,
            "cache_hit_rate": valid_cache / len(self.discovery_cache) if self.discovery_cache else 0
        }


# 创建全局代币发现服务实例
token_discovery_service = TokenDiscoveryService() 
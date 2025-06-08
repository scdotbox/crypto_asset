"""
价格服务模块

提供加密货币价格查询功能，支持：
- CoinGecko API 价格查询
- 价格缓存机制
- 历史价格数据
"""

import asyncio
import httpx
import time
import json
import os
from typing import Dict, List, Optional, Tuple

# 使用统一日志系统
from app.core.logger import get_logger
from app.core.config import settings
from app.services.token_library_service import TokenLibraryService

logger = get_logger(__name__)


class PriceCache:
    """价格缓存类，支持时间戳缓存"""
    
    def __init__(self, ttl: int = 300):
        """
        初始化价格缓存
        
        Args:
            ttl: 缓存生存时间（秒），默认5分钟
        """
        self.cache: Dict[str, Tuple[float, float]] = {}
        self.ttl = ttl
    
    def get(self, key: str) -> Optional[float]:
        """获取缓存的价格"""
        if key in self.cache:
            price, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return price
            else:
                # 缓存过期，删除
                del self.cache[key]
        return None
    
    def set(self, key: str, price: float) -> None:
        """设置缓存价格"""
        self.cache[key] = (price, time.time())
    
    def clear_expired(self) -> None:
        """清理过期的缓存项"""
        current_time = time.time()
        expired_keys = [
            key for key, (_, timestamp) in self.cache.items()
            if current_time - timestamp >= self.ttl
        ]
        for key in expired_keys:
            del self.cache[key]
    
    def get_cache_stats(self) -> Dict[str, int]:
        """获取缓存统计信息"""
        current_time = time.time()
        valid_count = sum(
            1 for _, timestamp in self.cache.values()
            if current_time - timestamp < self.ttl
        )
        return {
            "total_items": len(self.cache),
            "valid_items": valid_count,
            "expired_items": len(self.cache) - valid_count
        }


class PriceService:
    """价格服务类，用于获取代币价格"""
    
    def __init__(self):
        self.base_url = settings.coingecko_api_url
        self.api_key = settings.coingecko_api_key
        self.price_cache = PriceCache(ttl=settings.price_cache_ttl)
        self.token_library_service = TokenLibraryService()
        
        # 历史缓存服务（延迟初始化避免循环导入）
        self._history_cache = None
        
        # 备用 API 端点
        self.backup_endpoints = [
            "https://api.coingecko.com/api/v3",
            "https://pro-api.coingecko.com/api/v3",
            "https://api.coinpaprika.com/v1",  # 备用 API
        ]
        
        # 批量查询配置（从配置文件读取）
        self.batch_size = settings.price_batch_size
        self.rate_limit_delay = settings.price_rate_limit_delay
        self.last_request_time = 0
        
        # 重试配置（从配置文件读取）
        self.max_retries = settings.price_max_retries
        self.base_delay = settings.price_retry_base_delay
        
        # 请求统计
        self.request_stats = {
            "total_requests": 0,
            "batch_requests": 0,
            "cache_hits": 0,
            "rate_limit_hits": 0,
            "network_errors": 0,
            "successful_requests": 0
        }
        
        # 添加错误统计
        self.error_stats = {
            "network_errors": 0,
            "timeout_errors": 0,
            "json_errors": 0,
            "unknown_errors": 0,
            "last_error_time": None,
            "consecutive_failures": 0
        }
        
        # 降级模式
        self.degraded_mode = False
        self.degraded_mode_until = 0
        
        # 代币列表缓存
        self.coins_list_cache = None
        self.coins_list_cache_time = 0
        self.coins_list_cache_ttl = 86400  # 24小时缓存
        
        # 合约地址查询缓存
        self.contract_cache = {}
        self.contract_cache_ttl = 3600  # 1小时缓存
    
    @property
    def history_cache(self):
        """延迟初始化历史缓存服务"""
        if self._history_cache is None:
            try:
                from app.services.history_cache_service import HistoryCacheService
                self._history_cache = HistoryCacheService()
            except ImportError:
                logger.warning("历史缓存服务不可用")
                self._history_cache = None
        return self._history_cache
    
    async def get_token_price_usdc_with_cache(
        self, 
        token_symbol: str, 
        chain_name: Optional[str] = None,
        use_history_cache: bool = True
    ) -> float:
        """
        获取代币价格（优先使用历史缓存）
        
        Args:
            token_symbol: 代币符号
            chain_name: 区块链名称
            use_history_cache: 是否使用历史缓存
            
        Returns:
            float: 代币价格（USDC）
        """
        try:
            # 首先尝试从历史缓存获取最新价格
            if use_history_cache and self.history_cache:
                cached_price = await self.history_cache.get_latest_price(token_symbol, chain_name)
                if cached_price is not None:
                    # 检查缓存时间是否在可接受范围内（例如1小时内）
                    logger.debug(f"从历史缓存获取价格: {token_symbol}@{chain_name} = ${cached_price}")
                    return cached_price
            
            # 如果历史缓存没有或过期，则从API获取
            price = await self.get_token_price_usdc(token_symbol, chain_name)
            
            # 保存到历史缓存
            if price > 0 and self.history_cache:
                await self.history_cache.save_price_history(
                    token_symbol=token_symbol,
                    price_usdc=price,
                    chain_name=chain_name
                )
                logger.debug(f"保存价格到历史缓存: {token_symbol}@{chain_name} = ${price}")
            
            return price
            
        except Exception as e:
            logger.error(f"获取代币价格失败: {e}")
            return 0.0
    
    async def get_all_coins_list(self, force_refresh: bool = False) -> List[Dict]:
        """
        获取所有代币列表
        
        Args:
            force_refresh: 是否强制刷新缓存
            
        Returns:
            代币列表，包含 id、symbol、name
        """
        try:
            # 检查缓存
            current_time = time.time()
            if (not force_refresh and 
                self.coins_list_cache and 
                current_time - self.coins_list_cache_time < self.coins_list_cache_ttl):
                logger.debug("使用缓存的代币列表")
                return self.coins_list_cache
            
            # 等待速率限制
            await self._wait_for_rate_limit()
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                url = f"{self.base_url}/coins/list"
                headers = {}
                if self.api_key:
                    headers["x-cg-demo-api-key"] = self.api_key
                
                logger.info("正在获取 CoinGecko 所有代币列表...")
                
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                
                data = response.json()
                self.request_stats["total_requests"] += 1
                
                # 缓存结果
                self.coins_list_cache = data
                self.coins_list_cache_time = current_time
                
                logger.info(f"成功获取 {len(data)} 个代币信息")
                
                # 保存到本地文件
                await self._save_coins_list_to_file(data)
                
                return data
                
        except Exception as e:
            logger.error(f"获取代币列表失败: {e}")
            # 尝试从本地文件加载
            local_data = await self._load_coins_list_from_file()
            if local_data:
                logger.info("使用本地缓存的代币列表")
                return local_data
            return []
    
    async def get_token_info_by_contract(
        self, 
        contract_address: str, 
        chain_name: str
    ) -> Optional[Dict]:
        """
        通过合约地址获取代币信息
        
        Args:
            contract_address: 合约地址
            chain_name: 区块链名称
            
        Returns:
            代币信息，包含 id、symbol、name 等
        """
        try:
            # 检查缓存
            cache_key = f"{chain_name}_{contract_address.lower()}"
            current_time = time.time()
            
            if cache_key in self.contract_cache:
                cached_data, cache_time = self.contract_cache[cache_key]
                if current_time - cache_time < self.contract_cache_ttl:
                    logger.debug(f"使用缓存的合约信息: {contract_address}")
                    return cached_data
            
            # 映射链名称到 CoinGecko 平台名称
            platform_mapping = {
                "ethereum": "ethereum",
                "bsc": "binance-smart-chain",
                "polygon": "polygon-pos",
                "arbitrum": "arbitrum-one",
                "base": "base",
                "solana": "solana",
                "sui": "sui"
            }
            
            platform_id = platform_mapping.get(chain_name.lower())
            if not platform_id:
                logger.warning(f"不支持的区块链: {chain_name}")
                return None
            
            # 等待速率限制
            await self._wait_for_rate_limit()
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                url = f"{self.base_url}/coins/{platform_id}/contract/{contract_address}"
                headers = {}
                if self.api_key:
                    headers["x-cg-demo-api-key"] = self.api_key
                
                logger.info(f"查询合约地址: {contract_address} 在 {chain_name}")
                
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                
                data = response.json()
                self.request_stats["total_requests"] += 1
                
                # 提取关键信息
                token_info = {
                    "id": data.get("id"),
                    "symbol": data.get("symbol", "").upper(),
                    "name": data.get("name"),
                    "contract_address": contract_address,
                    "chain_name": chain_name,
                    "market_cap_rank": data.get("market_cap_rank"),
                    "coingecko_score": data.get("coingecko_score"),
                    "description": data.get("description", {}).get("en", "")[:200] if data.get("description") else ""
                }
                
                # 缓存结果
                self.contract_cache[cache_key] = (token_info, current_time)
                
                logger.info(f"成功获取合约信息: {token_info['symbol']} ({token_info['name']})")
                return token_info
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"合约地址未找到: {contract_address} 在 {chain_name}")
                # 缓存空结果，避免重复查询
                self.contract_cache[cache_key] = (None, current_time)
                return None
            else:
                logger.error(f"查询合约地址失败: {e}")
                return None
        except Exception as e:
            logger.error(f"查询合约地址时发生错误: {e}")
            return None
    
    async def _save_coins_list_to_file(self, coins_list: List[Dict]) -> None:
        """保存代币列表到本地文件"""
        try:
            file_path = os.path.join(settings.data_dir, "coingecko_coins_list.json")
            
            # 确保目录存在
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "timestamp": time.time(),
                    "count": len(coins_list),
                    "coins": coins_list
                }, f, ensure_ascii=False, indent=2)
            
            logger.info(f"代币列表已保存到: {file_path}")
            
        except Exception as e:
            logger.error(f"保存代币列表失败: {e}")
    
    async def _load_coins_list_from_file(self) -> Optional[List[Dict]]:
        """从本地文件加载代币列表"""
        try:
            file_path = os.path.join(settings.data_dir, "coingecko_coins_list.json")
            
            if not os.path.exists(file_path):
                return None
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 检查文件是否过期（超过7天）
            if time.time() - data.get("timestamp", 0) > 604800:  # 7天
                logger.warning("本地代币列表文件已过期")
                return None
            
            logger.info(f"从本地文件加载了 {data.get('count', 0)} 个代币信息")
            return data.get("coins", [])
            
        except Exception as e:
            logger.error(f"加载本地代币列表失败: {e}")
            return None

    async def get_token_price_usdc(
        self, 
        token_symbol: str, 
        chain_name: Optional[str] = None
    ) -> float:
        """
        获取代币价格（USDC）
        
        Args:
            token_symbol: 代币符号
            chain_name: 区块链名称
            
        Returns:
            float: 代币价格（USDC）
        """
        try:
            # 构建缓存键
            cache_key = f"{token_symbol.upper()}_{chain_name or 'default'}"
            
            # 首先尝试从缓存获取
            cached_price = self.price_cache.get(cache_key)
            if cached_price is not None:
                self.request_stats["cache_hits"] += 1
                logger.debug(f"从缓存获取价格: {cache_key} = ${cached_price}")
                return cached_price
            
            # 检查是否处于降级模式
            if self._check_degraded_mode():
                logger.warning(f"系统处于降级模式，返回默认价格: {token_symbol}")
                return 0.0
            
            # 特殊处理：如果是主流稳定币，直接返回1.0
            if token_symbol.upper() in ['USDC', 'USDT', 'DAI', 'BUSD']:
                price = 1.0
                self.price_cache.set(cache_key, price)
                return price
            
            # 获取代币对应的CoinGecko ID
            coin_id = await self._map_token_to_coingecko_id(token_symbol, chain_name)
            if not coin_id:
                logger.warning(f"无法找到代币 {token_symbol} 的CoinGecko ID")
                self.price_cache.set(cache_key, 0.0)
                return 0.0
            
            # 等待速率限制
            await self._wait_for_rate_limit()
            
            # 从CoinGecko获取价格（带重试机制）
            price = await self._fetch_price_from_coingecko_with_retry(coin_id)
            
            # 缓存结果
            if price > 0:
                self.price_cache.set(cache_key, price)
                self.request_stats["successful_requests"] += 1
                logger.debug(f"成功获取价格: {token_symbol} = ${price}")
            else:
                # 缓存零价格避免重复请求
                self.price_cache.set(cache_key, 0.0)
                logger.warning(f"获取到零价格: {token_symbol}")
            
            return price
            
        except Exception as e:
            logger.error(f"获取代币价格失败 {token_symbol}: {e}")
            self.error_stats["unknown_errors"] += 1
            self.error_stats["last_error_time"] = time.time()
            
            # 在错误情况下缓存零价格，避免重复请求
            cache_key = f"{token_symbol.upper()}_{chain_name or 'default'}"
            self.price_cache.set(cache_key, 0.0)
            
            return 0.0
    
    async def get_multiple_prices_batch(self, tokens: List[Dict[str, str]]) -> Dict[str, float]:
        """
        批量获取多个代币的价格（真正的批量查询）
        
        Args:
            tokens: 代币列表，每个元素包含 symbol 和 chain_name
            
        Returns:
            价格字典，key为 "symbol_chain"，value为价格
        """
        try:
            # 准备查询数据
            query_data = []
            result = {}
            
            for token in tokens:
                symbol = token.get("symbol", "")
                chain_name = token.get("chain_name")
                
                # 安全地处理字符串
                if symbol:
                    symbol = symbol.strip()
                if chain_name:
                    chain_name = chain_name.strip()
                
                if not symbol:
                    continue
                
                cache_key = f"{symbol.lower()}_{chain_name or 'default'}"
                
                # 检查缓存
                cached_price = self.price_cache.get(cache_key)
                if cached_price is not None:
                    result[cache_key] = cached_price
                    self.request_stats["cache_hits"] += 1
                    continue
                
                # 映射到 CoinGecko ID
                coin_id = await self._map_token_to_coingecko_id(symbol, chain_name)
                if coin_id:
                    query_data.append({
                        "cache_key": cache_key,
                        "coin_id": coin_id,
                        "symbol": symbol,
                        "chain_name": chain_name
                    })
            
            # 如果没有需要查询的代币，直接返回缓存结果
            if not query_data:
                return result
            
            # 分批查询
            batches = [query_data[i:i + self.batch_size] for i in range(0, len(query_data), self.batch_size)]
            
            for batch in batches:
                batch_prices = await self._fetch_batch_prices_from_coingecko(batch)
                result.update(batch_prices)
                
                # 缓存批量查询结果
                for cache_key, price in batch_prices.items():
                    self.price_cache.set(cache_key, price)
            
            return result
            
        except Exception as e:
            logger.error(f"批量获取价格失败: {e}")
            return {}
    
    async def get_multiple_prices(self, tokens: list) -> Dict[str, float]:
        """
        批量获取多个代币的价格（兼容旧接口）
        
        Args:
            tokens: 代币列表，可以是字符串或字典
            
        Returns:
            价格字典
        """
        # 标准化输入格式
        standardized_tokens = []
        for token_info in tokens:
            if isinstance(token_info, dict):
                symbol = token_info.get("symbol")
                chain = token_info.get("chain") or token_info.get("chain_name")
                if symbol:
                    standardized_tokens.append({
                        "symbol": symbol,
                        "chain_name": chain
                    })
            else:
                symbol = str(token_info) if token_info else None
                if symbol:
                    standardized_tokens.append({
                        "symbol": symbol,
                        "chain_name": None
                    })
        
        return await self.get_multiple_prices_batch(standardized_tokens)
    
    async def _map_token_to_coingecko_id(self, token_symbol: str, chain_name: Optional[str]) -> Optional[str]:
        """
        将代币符号映射到 CoinGecko ID（使用 LRU 缓存）
        
        首先尝试从代币库中查找，如果找不到则使用硬编码映射，最后尝试从代币列表中搜索
        """
        symbol_lower = token_symbol.lower()
        
        # 首先尝试从代币库中查找
        if chain_name:
            token_info = await self.token_library_service.find_token(token_symbol, chain_name)
            if token_info and token_info.coingecko_id:
                return token_info.coingecko_id
        
        # 如果代币库中没有找到，使用硬编码映射
        token_mapping = {
            "eth": "ethereum",
            "btc": "bitcoin",
            "bnb": "binancecoin",
            "sol": "solana",
            "sui": "sui",
            "matic": "matic-network",
            "usdc": "usd-coin",
            "usdt": "tether",
            "degen": "degen-base",  
            "dai": "dai",
            "weth": "weth",
            "link": "chainlink",
            "uni": "uniswap",
            "avax": "avalanche-2",
            "ftm": "fantom",
            "atom": "cosmos",
            "dot": "polkadot",
            "ada": "cardano",
            "slayer": "solayer",  
            "jip": "jupiter-exchange-solana",  
            "jup": "jupiter-exchange-solana",  
            "layer": "solayer",  
            "ssol": "solayer", 
            "susd": "solayer-usd",
        }
        
        # 根据链名称进行特殊处理
        if chain_name == "base" and symbol_lower == "degen":
            return "degen-base"
        if chain_name == "solana" and symbol_lower in ["slayer", "layer"]:
            return "solayer"
        if chain_name == "solana" and symbol_lower == "jip":
            return "jupiter-exchange-solana"
        if chain_name == "solana" and symbol_lower == "ssol":
            # sSOL (Solana Staked SOL) 应该使用 SOL 的价格作为基准
            # 因为它是质押的 SOL，价格通常接近或略高于 SOL
            logger.info("sSOL 使用 SOL 价格作为基准")
            return "solana"
        if chain_name == "solana" and symbol_lower == "susd":
            # sUSD (Solayer USD) 映射到正确的 CoinGecko ID
            logger.info("sUSD 映射到 Solayer USD")
            return "solayer-usd"
        if chain_name == "bsc" and symbol_lower == "asbnb":
            # 对于 asBNB，使用 BNB 的价格作为近似值
            logger.info(f"使用 BNB 价格作为 {token_symbol} 的近似价格")
            return "binancecoin"
        
        # 检查硬编码映射
        if symbol_lower in token_mapping:
            return token_mapping[symbol_lower]
        
        # 特殊处理 ASUSDF 代币
        if symbol_lower == "asusdf":
            logger.info("ASUSDF 代币映射到 astherus-staked-usdf")
            return "astherus-staked-usdf"
        
        # 如果硬编码映射中没有找到，尝试从代币列表中搜索
        try:
            coins_list = await self.get_all_coins_list()
            
            # 精确匹配符号
            for coin in coins_list:
                if coin.get("symbol", "").lower() == symbol_lower:
                    logger.info(f"在代币列表中找到 {token_symbol}: {coin.get('id')}")
                    return coin.get("id")
            
            # 如果精确匹配失败，尝试模糊匹配名称
            for coin in coins_list:
                coin_name = coin.get("name", "").lower()
                if token_symbol.lower() in coin_name or coin_name in token_symbol.lower():
                    logger.info(f"通过名称匹配找到 {token_symbol}: {coin.get('id')} ({coin.get('name')})")
                    return coin.get("id")
                    
        except Exception as e:
            logger.error(f"搜索代币列表时发生错误: {e}")
        
        return None
    
    async def _fetch_single_price_from_coingecko(self, coin_id: str) -> float:
        """从 CoinGecko API 获取单个代币价格"""
        return await self._fetch_price_from_coingecko_with_retry(coin_id)
    
    async def _fetch_batch_prices_from_coingecko(self, batch_data: List[Dict]) -> Dict[str, float]:
        """
        从 CoinGecko API 批量获取价格
        
        Args:
            batch_data: 批量查询数据，包含 coin_id 和 cache_key
            
        Returns:
            价格字典，key为cache_key，value为价格
        """
        if not batch_data:
            return {}
        
        max_retries = 3  # 添加重试机制
        
        for attempt in range(max_retries):
            try:
                # 提取所有 coin_id
                coin_ids = [item["coin_id"] for item in batch_data]
                unique_coin_ids = list(set(coin_ids))  # 去重
                
                # 等待速率限制
                await self._wait_for_rate_limit()
                
                # 构建批量查询URL
                ids_string = ",".join(unique_coin_ids)
                
                async with httpx.AsyncClient(timeout=30.0) as client:
                    url = f"{self.base_url}/simple/price"
                    params = {
                        "ids": ids_string,
                        "vs_currencies": "usd"
                    }
                    
                    # 如果有 API 密钥，添加到请求头
                    headers = {}
                    if self.api_key:
                        headers["x-cg-demo-api-key"] = self.api_key
                    
                    logger.info(f"批量查询 {len(unique_coin_ids)} 个代币价格: {unique_coin_ids}")
                    
                    response = await client.get(url, params=params, headers=headers)
                    response.raise_for_status()
                    
                    # 检查响应内容类型
                    content_type = response.headers.get('content-type', '')
                    if 'application/json' not in content_type:
                        logger.error(f"API 返回了非 JSON 响应，Content-Type: {content_type}")
                        raise ValueError(f"非 JSON 响应: {content_type}")
                    
                    # 尝试解析 JSON
                    try:
                        data = response.json()
                    except Exception as json_error:
                        logger.error(f"JSON 解析失败: {json_error}, 响应内容: {response.text[:500]}")
                        raise ValueError(f"JSON 解析失败: {json_error}")
                    
                    self.request_stats["total_requests"] += 1
                    self.request_stats["batch_requests"] += 1
                    
                    # 构建结果字典
                    result = {}
                    for item in batch_data:
                        coin_id = item["coin_id"]
                        cache_key = item["cache_key"]
                        
                        if coin_id in data and "usd" in data[coin_id]:
                            try:
                                price = float(data[coin_id]["usd"])
                                result[cache_key] = price
                                logger.debug(f"批量查询成功: {item['symbol']} = ${price}")
                            except (ValueError, TypeError) as price_error:
                                logger.error(f"价格转换失败: {coin_id}, 值: {data[coin_id]['usd']}, 错误: {price_error}")
                                result[cache_key] = 0.0
                        else:
                            result[cache_key] = 0.0
                            logger.warning(f"批量查询中未找到 {coin_id} 的价格数据")
                    
                    return result
                    
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:  # Too Many Requests
                    self.request_stats["rate_limit_hits"] += 1
                    logger.error(f"批量查询遇到速率限制: {e}")
                    # 对于批量查询，如果遇到速率限制，等待更长时间后重试
                    await asyncio.sleep(60)
                    return await self._fetch_batch_prices_from_coingecko(batch_data)
                else:
                    logger.error(f"批量查询 HTTP 错误: {e}, 状态码: {e.response.status_code}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)  # 指数退避
                        continue
                    return {item["cache_key"]: 0.0 for item in batch_data}
            except httpx.TimeoutException as e:
                self.error_stats["timeout_errors"] += 1
                self.error_stats["consecutive_failures"] += 1
                logger.warning(f"批量查询超时 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                return {item["cache_key"]: 0.0 for item in batch_data}
            except httpx.NetworkError as e:
                self.request_stats["network_errors"] += 1
                self.error_stats["network_errors"] += 1
                self.error_stats["consecutive_failures"] += 1
                self.error_stats["last_error_time"] = time.time()
                
                logger.warning(f"批量查询网络错误 (尝试 {attempt + 1}/{max_retries}): {e}")
                
                # 如果连续失败次数过多，启用降级模式
                if self.error_stats["consecutive_failures"] >= 3:
                    self._enable_degraded_mode()
                
                if attempt < max_retries - 1:
                    wait_time = min(2 ** attempt, 30)  # 最大等待30秒
                    logger.info(f"等待 {wait_time} 秒后重试...")
                    await asyncio.sleep(wait_time)
                    continue
                
                # 最后一次尝试失败，尝试备用端点
                if attempt == max_retries - 1:
                    logger.info("尝试使用备用端点...")
                    backup_result = await self._try_backup_endpoints(batch_data)
                    if backup_result:
                        return backup_result
                
                return {item["cache_key"]: 0.0 for item in batch_data}
            except ValueError as e:
                logger.error(f"批量查询数据处理错误: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                return {item["cache_key"]: 0.0 for item in batch_data}
            except Exception as e:
                # 添加更详细的错误信息
                import traceback
                error_details = traceback.format_exc()
                logger.error(f"批量查询发生未知错误: {type(e).__name__}: {e}")
                logger.error(f"错误详情: {error_details}")
                
                if attempt < max_retries - 1:
                    logger.info(f"重试批量查询 (尝试 {attempt + 2}/{max_retries})")
                    await asyncio.sleep(2 ** attempt)
                    continue
                
                # 最后一次尝试失败，返回默认值
                return {item["cache_key"]: 0.0 for item in batch_data}
        
        # 如果所有重试都失败，返回默认值
        return {item["cache_key"]: 0.0 for item in batch_data}
    
    async def _fetch_price_from_coingecko_with_retry(self, coin_id: str) -> float:
        """从 CoinGecko API 获取价格（带重试机制）"""
        max_retries = self.max_retries
        base_delay = self.base_delay
        
        for attempt in range(max_retries):
            try:
                # 等待速率限制
                await self._wait_for_rate_limit()
                
                async with httpx.AsyncClient(timeout=30.0) as client:
                    url = f"{self.base_url}/simple/price"
                    params = {
                        "ids": coin_id,
                        "vs_currencies": "usd"
                    }
                    
                    # 如果有 API 密钥，添加到请求头
                    headers = {}
                    if self.api_key:
                        headers["x-cg-demo-api-key"] = self.api_key
                    
                    response = await client.get(url, params=params, headers=headers)
                    response.raise_for_status()
                    
                    data = response.json()
                    self.request_stats["total_requests"] += 1
                    
                    if coin_id in data and "usd" in data[coin_id]:
                        price = float(data[coin_id]["usd"])
                        logger.debug(f"单个查询成功: {coin_id} = ${price}")
                        return price
                    else:
                        logger.warning(f"CoinGecko 响应中未找到 {coin_id} 的价格数据")
                        return 0.0
                        
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:  # Too Many Requests
                    self.request_stats["rate_limit_hits"] += 1
                    if attempt < max_retries - 1:
                        wait_time = base_delay * (2 ** attempt) + 60  # 指数退避 + 额外等待
                        logger.warning(f"API 速率限制，等待 {wait_time} 秒后重试... (尝试 {attempt + 1}/{max_retries})")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"达到最大重试次数，CoinGecko API 速率限制: {e}")
                        return 0.0
                else:
                    logger.error(f"CoinGecko API 请求失败: {e}")
                    return 0.0
            except Exception as e:
                logger.error(f"获取价格时发生未知错误: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(base_delay * (attempt + 1))
                    continue
                return 0.0
        
        return 0.0
    
    async def _wait_for_rate_limit(self) -> None:
        """
        等待速率限制
        """
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        
        # 确保请求间隔至少为rate_limit_delay秒
        if time_since_last_request < self.rate_limit_delay:
            wait_time = self.rate_limit_delay - time_since_last_request
            logger.debug(f"速率限制等待 {wait_time:.2f} 秒")
            await asyncio.sleep(wait_time)
        
        self.last_request_time = time.time()
    
    def get_cache_stats(self) -> Dict:
        """获取缓存和请求统计信息"""
        cache_stats = self.price_cache.get_cache_stats()
        return {
            "cache": cache_stats,
            "requests": self.request_stats.copy()
        }
    
    def clear_cache(self) -> None:
        """清空缓存"""
        self.price_cache.cache.clear()
        logger.info("价格缓存已清空")
    
    def clear_all_cache(self) -> None:
        """清空所有缓存，包括内存缓存、代币列表缓存和合约缓存"""
        # 清空价格缓存
        self.price_cache.cache.clear()
        
        # 清空代币列表缓存
        self.coins_list_cache = None
        self.coins_list_cache_time = 0
        
        # 清空合约地址查询缓存
        self.contract_cache.clear()
        
        # 重置错误统计
        self.error_stats = {
            "network_errors": 0,
            "timeout_errors": 0,
            "json_errors": 0,
            "unknown_errors": 0,
            "last_error_time": None,
            "consecutive_failures": 0
        }
        
        # 重置请求统计
        self.request_stats = {
            "total_requests": 0,
            "batch_requests": 0,
            "cache_hits": 0,
            "rate_limit_hits": 0,
            "network_errors": 0,
            "successful_requests": 0
        }
        
        logger.info("所有价格服务缓存已清空")
    
    def clear_expired_cache(self) -> None:
        """清理过期缓存"""
        self.price_cache.clear_expired()
        logger.info("过期缓存已清理")

    def _enable_degraded_mode(self):
        """启用降级模式"""
        self.degraded_mode = True
        self.degraded_mode_until = time.time() + 300  # 5分钟降级模式
        logger.warning("启用降级模式：将使用缓存价格和默认值，5分钟后恢复正常")

    def _check_degraded_mode(self) -> bool:
        """检查是否处于降级模式"""
        if self.degraded_mode and time.time() > self.degraded_mode_until:
            self.degraded_mode = False
            self.error_stats["consecutive_failures"] = 0
            logger.info("降级模式已结束，恢复正常价格查询")
        return self.degraded_mode

    async def _try_backup_endpoints(self, batch_data: List[Dict]) -> Optional[Dict[str, float]]:
        """尝试使用备用端点"""
        for endpoint in self.backup_endpoints[1:]:  # 跳过主端点
            try:
                logger.info(f"尝试备用端点: {endpoint}")
                
                # 临时更换端点
                original_url = self.base_url
                self.base_url = endpoint
                
                # 使用更短的超时时间
                async with httpx.AsyncClient(timeout=15.0) as client:
                    coin_ids = [item["coin_id"] for item in batch_data]
                    unique_coin_ids = list(set(coin_ids))
                    ids_string = ",".join(unique_coin_ids)
                    
                    url = f"{self.base_url}/simple/price"
                    params = {
                        "ids": ids_string,
                        "vs_currencies": "usd"
                    }
                    
                    response = await client.get(url, params=params)
                    if response.status_code == 200:
                        data = response.json()
                        
                        # 构建结果
                        result = {}
                        for item in batch_data:
                            coin_id = item["coin_id"]
                            cache_key = item["cache_key"]
                            
                            if coin_id in data and "usd" in data[coin_id]:
                                result[cache_key] = float(data[coin_id]["usd"])
                            else:
                                result[cache_key] = 0.0
                        
                        logger.info(f"备用端点成功: {endpoint}")
                        # 恢复原始端点
                        self.base_url = original_url
                        return result
                        
            except Exception as e:
                logger.warning(f"备用端点失败 {endpoint}: {e}")
                continue
            finally:
                # 确保恢复原始端点
                self.base_url = original_url
        
        return None
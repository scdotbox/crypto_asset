"""
历史数据缓存服务

提供历史数据缓存管理功能，包括：
- 价格历史缓存
- 余额历史缓存
- 缓存统计和清理
"""

import time
from datetime import datetime, timedelta
from typing import Optional, Tuple

from app.core.config import settings
from app.core.database import db_manager
from app.models.asset_models import (
    PriceHistoryPoint,
    BalanceHistoryPoint,
    HistoryCacheStats,
    HistoryQueryRequest,
    PriceHistoryResponse,
    BalanceHistoryResponse,
)

# 使用统一日志系统
from app.core.logger import get_logger

logger = get_logger(__name__)


class HistoryCacheService:
    """历史数据缓存服务类（使用主数据库）"""
    
    def __init__(self):
        self.retention_years = settings.history_retention_years
        self.interval_hours = settings.history_interval_hours
        self.auto_update_enabled = settings.history_auto_update_enabled
        self.batch_size = settings.history_batch_size
        self.max_gap_hours = settings.history_max_gap_hours
    
    async def save_price_history(
        self, 
        token_symbol: str, 
        price_usdc: float,
        chain_name: Optional[str] = None,
        coingecko_id: Optional[str] = None,
        timestamp: Optional[int] = None
    ) -> bool:
        """
        保存价格历史数据到主数据库
        
        Args:
            token_symbol: 代币符号
            price_usdc: USDC价格
            chain_name: 区块链名称
            coingecko_id: CoinGecko ID
            timestamp: 时间戳，为空则使用当前时间
            
        Returns:
            bool: 是否保存成功
        """
        try:
            if timestamp is None:
                timestamp = int(time.time())
            
            # 对齐到小时
            timestamp = self._align_to_hour(timestamp)
            date = datetime.fromtimestamp(timestamp).isoformat()
            
            async with db_manager.get_connection() as conn:
                # 获取或创建代币ID
                token_id = await self._get_or_create_token_id(
                    conn, token_symbol, chain_name, coingecko_id
                )
                
                if token_id:
                    await conn.execute("""
                        INSERT OR REPLACE INTO price_history 
                        (token_id, timestamp, date, price_usdc, source)
                        VALUES (?, ?, ?, ?, 'api')
                    """, (token_id, timestamp, date, price_usdc))
                    
                    await conn.commit()
                    logger.debug(f"保存价格历史数据: {token_symbol}@{chain_name} = ${price_usdc}")
                    return True
                else:
                    logger.warning(f"无法获取代币ID: {token_symbol}@{chain_name}")
                    return False
            
        except Exception as e:
            logger.error(f"保存价格历史数据失败: {e}")
            return False
    
    async def save_balance_history(
        self,
        address: str,
        chain_name: str,
        token_symbol: str,
        balance: float,
        token_contract_address: Optional[str] = None,
        timestamp: Optional[int] = None
    ) -> bool:
        """
        保存余额历史数据到主数据库
        
        Args:
            address: 钱包地址
            chain_name: 区块链名称
            token_symbol: 代币符号
            balance: 代币余额
            token_contract_address: 代币合约地址
            timestamp: 时间戳，为空则使用当前时间
            
        Returns:
            bool: 是否保存成功
        """
        try:
            if timestamp is None:
                timestamp = int(time.time())
            
            # 对齐到小时
            timestamp = self._align_to_hour(timestamp)
            date = datetime.fromtimestamp(timestamp).isoformat()
            
            async with db_manager.get_connection() as conn:
                # 获取资产ID
                asset_id = await self._get_asset_id(
                    conn, address, chain_name, token_symbol, token_contract_address
                )
                
                if asset_id:
                    await conn.execute("""
                        INSERT OR REPLACE INTO balance_history 
                        (asset_id, timestamp, date, balance)
                        VALUES (?, ?, ?, ?)
                    """, (asset_id, timestamp, date, balance))
                    
                    await conn.commit()
                    logger.debug(f"保存余额历史数据: {address}@{chain_name}:{token_symbol} = {balance}")
                    return True
                else:
                    logger.warning(f"无法获取资产ID: {address}@{chain_name}:{token_symbol}")
                    return False
                
        except Exception as e:
            logger.error(f"保存余额历史数据失败: {e}")
            return False
    
    async def get_price_history(
        self, 
        request: HistoryQueryRequest
    ) -> PriceHistoryResponse:
        """
        查询价格历史数据
        
        Args:
            request: 查询请求参数
            
        Returns:
            PriceHistoryResponse: 价格历史响应
        """
        try:
            async with db_manager.get_connection() as conn:
                # 构建查询条件
                where_conditions = []
                params = []
                
                # 时间范围条件
                if request.start_date:
                    # 将ISO格式字符串转换为时间戳
                    start_dt = datetime.fromisoformat(request.start_date.replace('Z', '+00:00'))
                    start_timestamp = int(start_dt.timestamp())
                    where_conditions.append("ph.timestamp >= ?")
                    params.append(start_timestamp)
                
                if request.end_date:
                    # 将ISO格式字符串转换为时间戳
                    end_dt = datetime.fromisoformat(request.end_date.replace('Z', '+00:00'))
                    end_timestamp = int(end_dt.timestamp())
                    where_conditions.append("ph.timestamp <= ?")
                    params.append(end_timestamp)
                
                # 代币条件（单个代币符号）
                if request.token_symbol:
                    where_conditions.append("t.symbol = ?")
                    params.append(request.token_symbol)
                
                # 链条件
                if request.chain_name:
                    where_conditions.append("b.name = ?")
                    params.append(request.chain_name)
                
                where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
                
                # 构建查询SQL
                query = f"""
                    SELECT 
                        ph.timestamp,
                        ph.date,
                        ph.price_usdc,
                        t.symbol as token_symbol,
                        b.name as chain_name,
                        t.coingecko_id
                    FROM price_history ph
                    JOIN tokens t ON ph.token_id = t.id
                    JOIN blockchains b ON t.blockchain_id = b.id
                    WHERE {where_clause}
                    ORDER BY ph.timestamp ASC
                    LIMIT ?
                """
                
                params.append(request.limit or 1000)
                
                # 执行查询
                history_points = []
                async with conn.execute(query, params) as cursor:
                    async for row in cursor:
                        point = PriceHistoryPoint(
                            timestamp=row['timestamp'],
                            date=row['date'],
                            value=row['price_usdc'],
                            price_usdc=row['price_usdc'],
                            token_symbol=row['token_symbol'],
                            chain_name=row['chain_name'],
                            coingecko_id=row['coingecko_id']
                        )
                        history_points.append(point)
                
                # 计算日期范围
                date_range = {}
                if history_points:
                    date_range = {
                        "start": history_points[0].date,
                        "end": history_points[-1].date
                    }
                
                return PriceHistoryResponse(
                    success=True,
                    data=history_points,
                    total_count=len(history_points),
                    date_range=date_range,
                    message=f"成功获取 {len(history_points)} 条价格历史记录"
                )
                
        except Exception as e:
            logger.error(f"查询价格历史数据失败: {e}")
            return PriceHistoryResponse(
                success=False,
                data=[],
                total_count=0,
                date_range={},
                message=f"查询失败: {str(e)}"
            )
    
    async def get_balance_history(
        self, 
        request: HistoryQueryRequest
    ) -> BalanceHistoryResponse:
        """
        查询余额历史数据
        
        Args:
            request: 查询请求参数
            
        Returns:
            BalanceHistoryResponse: 余额历史响应
        """
        try:
            async with db_manager.get_connection() as conn:
                # 构建查询条件
                where_conditions = []
                params = []
                
                # 时间范围条件
                if request.start_date:
                    # 将ISO格式字符串转换为时间戳
                    start_dt = datetime.fromisoformat(request.start_date.replace('Z', '+00:00'))
                    start_timestamp = int(start_dt.timestamp())
                    where_conditions.append("bh.timestamp >= ?")
                    params.append(start_timestamp)
                
                if request.end_date:
                    # 将ISO格式字符串转换为时间戳
                    end_dt = datetime.fromisoformat(request.end_date.replace('Z', '+00:00'))
                    end_timestamp = int(end_dt.timestamp())
                    where_conditions.append("bh.timestamp <= ?")
                    params.append(end_timestamp)
                
                # 地址条件
                if request.address:
                    where_conditions.append("w.address = ?")
                    params.append(request.address)
                
                # 代币条件
                if request.token_symbol:
                    where_conditions.append("t.symbol = ?")
                    params.append(request.token_symbol)
                
                # 链条件
                if request.chain_name:
                    where_conditions.append("b.name = ?")
                    params.append(request.chain_name)
                
                where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
                
                # 构建查询SQL
                query = f"""
                    SELECT 
                        bh.timestamp,
                        bh.date,
                        bh.balance,
                        w.address,
                        b.name as chain_name,
                        t.symbol as token_symbol,
                        t.contract_address as token_contract_address
                    FROM balance_history bh
                    JOIN assets a ON bh.asset_id = a.id
                    JOIN wallets w ON a.wallet_id = w.id
                    JOIN tokens t ON a.token_id = t.id
                    JOIN blockchains b ON w.blockchain_id = b.id
                    WHERE {where_clause}
                    ORDER BY bh.timestamp ASC
                    LIMIT ?
                """
                
                params.append(request.limit or 1000)
                
                # 执行查询
                history_points = []
                async with conn.execute(query, params) as cursor:
                    async for row in cursor:
                        point = BalanceHistoryPoint(
                            timestamp=row['timestamp'],
                            date=row['date'],
                            value=row['balance'],
                            balance=row['balance'],
                            address=row['address'],
                            chain_name=row['chain_name'],
                            token_symbol=row['token_symbol'],
                            token_contract_address=row['token_contract_address']
                        )
                        history_points.append(point)
                
                # 计算日期范围
                date_range = {}
                if history_points:
                    date_range = {
                        "start": history_points[0].date,
                        "end": history_points[-1].date
                    }
                
                return BalanceHistoryResponse(
                    success=True,
                    data=history_points,
                    total_count=len(history_points),
                    date_range=date_range,
                    message=f"成功获取 {len(history_points)} 条余额历史记录"
                )
                
        except Exception as e:
            logger.error(f"查询余额历史数据失败: {e}")
            return BalanceHistoryResponse(
                success=False,
                data=[],
                total_count=0,
                date_range={},
                message=f"查询失败: {str(e)}"
            )
    
    async def get_latest_price(
        self, 
        token_symbol: str, 
        chain_name: Optional[str] = None
    ) -> Optional[float]:
        """获取最新缓存价格"""
        try:
            async with db_manager.get_connection() as conn:
                where_conditions = ["t.symbol = ?"]
                params = [token_symbol]
                
                if chain_name:
                    where_conditions.append("b.name = ?")
                    params.append(chain_name)
                
                where_clause = " AND ".join(where_conditions)
                
                async with conn.execute(f"""
                    SELECT ph.price_usdc
                    FROM price_history ph
                    JOIN tokens t ON ph.token_id = t.id
                    JOIN blockchains b ON t.blockchain_id = b.id
                    WHERE {where_clause}
                    ORDER BY ph.timestamp DESC
                    LIMIT 1
                """, params) as cursor:
                    row = await cursor.fetchone()
                    return row['price_usdc'] if row else None
                    
        except Exception as e:
            logger.error(f"获取最新价格失败: {e}")
            return None
    
    async def get_latest_balance(
        self,
        address: str,
        chain_name: str,
        token_symbol: str
    ) -> Optional[float]:
        """获取最新缓存余额"""
        try:
            async with db_manager.get_connection() as conn:
                async with conn.execute("""
                    SELECT bh.balance
                    FROM balance_history bh
                    JOIN assets a ON bh.asset_id = a.id
                    JOIN wallets w ON a.wallet_id = w.id
                    JOIN tokens t ON a.token_id = t.id
                    JOIN blockchains b ON w.blockchain_id = b.id
                    WHERE w.address = ? AND b.name = ? AND t.symbol = ?
                    ORDER BY bh.timestamp DESC
                    LIMIT 1
                """, (address, chain_name, token_symbol)) as cursor:
                    row = await cursor.fetchone()
                    return row['balance'] if row else None
                    
        except Exception as e:
            logger.error(f"获取最新余额失败: {e}")
            return None
    
    async def cleanup_old_data(self) -> Tuple[int, int]:
        """清理过期历史数据"""
        try:
            cutoff_date = datetime.now() - timedelta(days=self.retention_years * 365)
            cutoff_timestamp = int(cutoff_date.timestamp())
            
            async with db_manager.get_connection() as conn:
                # 清理价格历史数据
                async with conn.execute("""
                    DELETE FROM price_history WHERE timestamp < ?
                """, (cutoff_timestamp,)) as cursor:
                    price_deleted = cursor.rowcount
                
                # 清理余额历史数据
                async with conn.execute("""
                    DELETE FROM balance_history WHERE timestamp < ?
                """, (cutoff_timestamp,)) as cursor:
                    balance_deleted = cursor.rowcount
                
                await conn.commit()
                
                logger.info(f"清理过期数据完成: 价格记录 {price_deleted} 条, 余额记录 {balance_deleted} 条")
                return price_deleted, balance_deleted
                
        except Exception as e:
            logger.error(f"清理过期数据失败: {e}")
            return 0, 0
    
    async def get_cache_stats(self) -> HistoryCacheStats:
        """获取缓存统计信息"""
        try:
            async with db_manager.get_connection() as conn:
                # 价格历史统计
                async with conn.execute("""
                    SELECT 
                        COUNT(*) as total_records,
                        MIN(timestamp) as earliest_timestamp,
                        MAX(timestamp) as latest_timestamp,
                        COUNT(DISTINCT token_id) as unique_tokens
                    FROM price_history
                """) as cursor:
                    price_stats = await cursor.fetchone()
                
                # 余额历史统计
                async with conn.execute("""
                    SELECT 
                        COUNT(*) as total_records,
                        MIN(timestamp) as earliest_timestamp,
                        MAX(timestamp) as latest_timestamp,
                        COUNT(DISTINCT asset_id) as unique_assets
                    FROM balance_history
                """) as cursor:
                    balance_stats = await cursor.fetchone()
                
                return HistoryCacheStats(
                    price_cache_size=price_stats['total_records'] if price_stats else 0,
                    balance_cache_size=balance_stats['total_records'] if balance_stats else 0,
                    oldest_price_record=datetime.fromtimestamp(price_stats['earliest_timestamp']).isoformat() if price_stats and price_stats['earliest_timestamp'] else None,
                    newest_price_record=datetime.fromtimestamp(price_stats['latest_timestamp']).isoformat() if price_stats and price_stats['latest_timestamp'] else None,
                    oldest_balance_record=datetime.fromtimestamp(balance_stats['earliest_timestamp']).isoformat() if balance_stats and balance_stats['earliest_timestamp'] else None,
                    newest_balance_record=datetime.fromtimestamp(balance_stats['latest_timestamp']).isoformat() if balance_stats and balance_stats['latest_timestamp'] else None,
                    total_tokens_tracked=price_stats['unique_tokens'] if price_stats else 0,
                    total_addresses_tracked=balance_stats['unique_assets'] if balance_stats else 0
                )
                
        except Exception as e:
            logger.error(f"获取缓存统计失败: {e}")
            return HistoryCacheStats(
                price_cache_size=0,
                balance_cache_size=0,
                oldest_price_record=None,
                newest_price_record=None,
                oldest_balance_record=None,
                newest_balance_record=None,
                total_tokens_tracked=0,
                total_addresses_tracked=0
            )
    
    def _align_to_hour(self, timestamp: int) -> int:
        """将时间戳对齐到小时"""
        dt = datetime.fromtimestamp(timestamp)
        aligned_dt = dt.replace(minute=0, second=0, microsecond=0)
        return int(aligned_dt.timestamp())
    
    async def _get_or_create_token_id(
        self, 
        conn, 
        token_symbol: str, 
        chain_name: Optional[str], 
        coingecko_id: Optional[str]
    ) -> Optional[int]:
        """获取或创建代币ID"""
        try:
            # 首先尝试查找现有代币
            where_conditions = ["t.symbol = ?"]
            params = [token_symbol]
            
            if chain_name:
                where_conditions.append("b.name = ?")
                params.append(chain_name)
            
            if coingecko_id:
                where_conditions.append("t.coingecko_id = ?")
                params.append(coingecko_id)
            
            where_clause = " AND ".join(where_conditions)
            
            async with conn.execute(f"""
                SELECT t.id
                FROM tokens t
                JOIN blockchains b ON t.blockchain_id = b.id
                WHERE {where_clause}
                LIMIT 1
            """, params) as cursor:
                row = await cursor.fetchone()
                if row:
                    return row['id']
            
            # 如果没有找到且有链名称，尝试创建
            if chain_name:
                # 获取区块链ID
                async with conn.execute("""
                    SELECT id FROM blockchains WHERE name = ?
                """, (chain_name,)) as cursor:
                    blockchain_row = await cursor.fetchone()
                    if blockchain_row:
                        # 创建新代币
                        cursor = await conn.execute("""
                            INSERT INTO tokens (symbol, name, blockchain_id, coingecko_id, is_predefined)
                            VALUES (?, ?, ?, ?, 0)
                        """, (token_symbol, token_symbol, blockchain_row['id'], coingecko_id))
                        return cursor.lastrowid
            
            return None
            
        except Exception as e:
            logger.error(f"获取或创建代币ID失败: {e}")
            return None
    
    async def _get_asset_id(
        self, 
        conn, 
        address: str, 
        chain_name: str, 
        token_symbol: str, 
        token_contract_address: Optional[str]
    ) -> Optional[str]:
        """获取资产ID"""
        try:
            where_conditions = [
                "w.address = ?",
                "b.name = ?", 
                "t.symbol = ?"
            ]
            params = [address, chain_name, token_symbol]
            
            if token_contract_address:
                where_conditions.append("t.contract_address = ?")
                params.append(token_contract_address)
            else:
                where_conditions.append("t.contract_address IS NULL")
            
            where_clause = " AND ".join(where_conditions)
            
            async with conn.execute(f"""
                SELECT a.id
                FROM assets a
                JOIN wallets w ON a.wallet_id = w.id
                JOIN tokens t ON a.token_id = t.id
                JOIN blockchains b ON w.blockchain_id = b.id
                WHERE {where_clause}
                LIMIT 1
            """, params) as cursor:
                row = await cursor.fetchone()
                return row['id'] if row else None
                
        except Exception as e:
            logger.error(f"获取资产ID失败: {e}")
            return None 
"""
历史数据自动更新服务
用于定期更新价格和余额历史数据，填补缺失的数据
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
import traceback

# 使用统一日志系统
from app.core.logger import get_logger

from app.core.config import settings
from app.services.history_cache_service import HistoryCacheService
from app.services.price_service import PriceService
from app.services.blockchain_service import BlockchainService
from app.services.asset_service import AssetService
from app.models.asset_models import (
    HistoryUpdateRequest,
    HistoryUpdateResponse
)

logger = get_logger(__name__)


class HistoryUpdaterService:
    """历史数据自动更新服务类"""
    
    def __init__(self):
        self.history_cache = HistoryCacheService()
        self.price_service = PriceService()
        self.blockchain_service = BlockchainService()
        self.asset_service = AssetService()
        
        self.update_interval = settings.history_interval_hours * 3600  # 转换为秒
        self.batch_size = settings.history_batch_size
        self.max_gap_hours = settings.history_max_gap_hours
        
        # 更新状态
        self.is_updating = False
        self.last_update_time = None
        self.update_stats = {
            "total_updates": 0,
            "successful_updates": 0,
            "failed_updates": 0,
            "last_error": None
        }
    
    async def start_auto_update(self):
        """启动自动更新任务"""
        if not settings.history_auto_update_enabled:
            logger.info("历史数据自动更新已禁用")
            return
        
        logger.info("启动历史数据自动更新服务")
        
        while True:
            try:
                if not self.is_updating:
                    await self.update_all_history_data()
                
                # 等待下一次更新
                await asyncio.sleep(self.update_interval)
                
            except Exception as e:
                logger.error(f"自动更新任务异常: {e}")
                self.update_stats["last_error"] = str(e)
                # 出错后等待较短时间再重试
                await asyncio.sleep(300)  # 5分钟
    
    async def update_all_history_data(
        self, 
        request: Optional[HistoryUpdateRequest] = None
    ) -> HistoryUpdateResponse:
        """
        更新所有历史数据
        
        Args:
            request: 更新请求参数，为空则使用默认配置
            
        Returns:
            HistoryUpdateResponse: 更新结果
        """
        if self.is_updating and not (request and request.force_update):
            return HistoryUpdateResponse(
                success=False,
                updated_price_records=0,
                updated_balance_records=0,
                failed_updates=[],
                message="更新任务正在进行中",
                duration_seconds=0
            )
        
        start_time = time.time()
        self.is_updating = True
        
        try:
            logger.info("开始更新历史数据")
            
            # 获取当前资产列表
            assets = await self.asset_service.get_detailed_assets()
            if not assets:
                logger.warning("没有找到任何资产，跳过历史数据更新")
                return HistoryUpdateResponse(
                    success=True,
                    updated_price_records=0,
                    updated_balance_records=0,
                    failed_updates=[],
                    message="没有资产需要更新",
                    duration_seconds=time.time() - start_time
                )
            
            # 确定更新时间范围
            end_date = datetime.now()
            if request and request.end_date:
                end_date = datetime.fromisoformat(request.end_date.replace('Z', '+00:00'))
            
            start_date = end_date - timedelta(days=7)  # 默认更新最近7天
            if request and request.start_date:
                start_date = datetime.fromisoformat(request.start_date.replace('Z', '+00:00'))
            
            # 更新价格历史数据
            price_updated = await self._update_price_history(
                assets, start_date, end_date, request
            )
            
            # 更新余额历史数据
            balance_updated = await self._update_balance_history(
                assets, start_date, end_date, request
            )
            
            duration = time.time() - start_time
            self.last_update_time = datetime.now()
            self.update_stats["total_updates"] += 1
            self.update_stats["successful_updates"] += 1
            
            logger.info(f"历史数据更新完成: 价格 {price_updated} 条, 余额 {balance_updated} 条, 耗时 {duration:.2f}s")
            
            return HistoryUpdateResponse(
                success=True,
                updated_price_records=price_updated,
                updated_balance_records=balance_updated,
                failed_updates=[],
                message=f"成功更新历史数据: 价格 {price_updated} 条, 余额 {balance_updated} 条",
                duration_seconds=duration
            )
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"更新历史数据失败: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            
            self.update_stats["failed_updates"] += 1
            self.update_stats["last_error"] = str(e)
            
            return HistoryUpdateResponse(
                success=False,
                updated_price_records=0,
                updated_balance_records=0,
                failed_updates=[{"error": str(e), "traceback": traceback.format_exc()}],
                message=error_msg,
                duration_seconds=duration
            )
            
        finally:
            self.is_updating = False
    
    async def _update_price_history(
        self,
        assets: List[Any],
        start_date: datetime,
        end_date: datetime,
        request: Optional[HistoryUpdateRequest] = None
    ) -> int:
        """
        更新价格历史数据
        
        Args:
            assets: 资产列表
            start_date: 开始日期
            end_date: 结束日期
            request: 更新请求参数
            
        Returns:
            int: 更新的记录数
        """
        try:
            updated_count = 0
            
            # 获取所有需要更新的代币
            tokens_to_update = set()
            for asset in assets:
                if request and request.token_symbols:
                    if asset.token_symbol in request.token_symbols:
                        tokens_to_update.add((asset.token_symbol, asset.chain_name))
                else:
                    tokens_to_update.add((asset.token_symbol, asset.chain_name))
            
            logger.info(f"需要更新价格历史的代币数量: {len(tokens_to_update)}")
            
            # 生成需要更新的时间点
            time_points = []
            current = start_date
            while current <= end_date:
                time_points.append(current)
                current += timedelta(hours=settings.history_interval_hours)
            
            # 按批次更新价格数据
            for i in range(0, len(time_points), self.batch_size):
                batch_time_points = time_points[i:i + self.batch_size]
                
                for time_point in batch_time_points:
                    timestamp = int(time_point.timestamp())
                    
                    # 检查是否已存在该时间点的数据
                    for token_symbol, chain_name in tokens_to_update:
                        try:
                            # 检查缓存中是否已有该时间点的数据
                            existing_price = await self._get_cached_price_at_time(
                                token_symbol, chain_name, timestamp
                            )
                            
                            if existing_price is None or (request and request.force_update):
                                # 获取当前价格（实际应用中可能需要历史价格API）
                                current_price = await self.price_service.get_token_price_usdc(
                                    token_symbol, chain_name
                                )
                                
                                if current_price > 0:
                                    # 保存价格历史数据
                                    success = await self.history_cache.save_price_history(
                                        token_symbol=token_symbol,
                                        price_usdc=current_price,
                                        chain_name=chain_name,
                                        timestamp=timestamp
                                    )
                                    
                                    if success:
                                        updated_count += 1
                                        logger.debug(f"更新价格历史: {token_symbol}@{chain_name} = ${current_price}")
                            
                        except Exception as e:
                            logger.error(f"更新代币 {token_symbol}@{chain_name} 价格历史失败: {e}")
                            continue
                
                # 批次间延迟，避免API限制
                if i + self.batch_size < len(time_points):
                    await asyncio.sleep(1)
            
            return updated_count
            
        except Exception as e:
            logger.error(f"更新价格历史数据失败: {e}")
            return 0
    
    async def _update_balance_history(
        self,
        assets: List[Any],
        start_date: datetime,
        end_date: datetime,
        request: Optional[HistoryUpdateRequest] = None
    ) -> int:
        """
        更新余额历史数据
        
        Args:
            assets: 资产列表
            start_date: 开始日期
            end_date: 结束日期
            request: 更新请求参数
            
        Returns:
            int: 更新的记录数
        """
        try:
            updated_count = 0
            
            # 过滤需要更新的资产
            assets_to_update = []
            for asset in assets:
                if request and request.addresses:
                    if asset.address in request.addresses:
                        assets_to_update.append(asset)
                else:
                    assets_to_update.append(asset)
            
            logger.info(f"需要更新余额历史的资产数量: {len(assets_to_update)}")
            
            # 生成需要更新的时间点
            time_points = []
            current = start_date
            while current <= end_date:
                time_points.append(current)
                current += timedelta(hours=settings.history_interval_hours)
            
            # 按批次更新余额数据
            for i in range(0, len(time_points), self.batch_size):
                batch_time_points = time_points[i:i + self.batch_size]
                
                for time_point in batch_time_points:
                    timestamp = int(time_point.timestamp())
                    
                    for asset in assets_to_update:
                        try:
                            # 检查缓存中是否已有该时间点的数据
                            existing_balance = await self._get_cached_balance_at_time(
                                asset.address, asset.chain_name, asset.token_symbol, timestamp
                            )
                            
                            if existing_balance is None or (request and request.force_update):
                                # 获取当前余额（实际应用中可能需要历史余额查询）
                                current_balance = await self.blockchain_service.get_token_balance(
                                    asset.address, asset.token_contract_address, asset.chain_name
                                )
                                
                                if current_balance >= 0:
                                    # 保存余额历史数据
                                    success = await self.history_cache.save_balance_history(
                                        address=asset.address,
                                        chain_name=asset.chain_name,
                                        token_symbol=asset.token_symbol,
                                        balance=current_balance,
                                        token_contract_address=asset.token_contract_address,
                                        timestamp=timestamp
                                    )
                                    
                                    if success:
                                        updated_count += 1
                                        logger.debug(f"更新余额历史: {asset.address}@{asset.chain_name} {asset.token_symbol} = {current_balance}")
                            
                        except Exception as e:
                            logger.error(f"更新资产 {asset.id} 余额历史失败: {e}")
                            continue
                
                # 批次间延迟，避免API限制
                if i + self.batch_size < len(time_points):
                    await asyncio.sleep(2)
            
            return updated_count
            
        except Exception as e:
            logger.error(f"更新余额历史数据失败: {e}")
            return 0
    
    async def _get_cached_price_at_time(
        self,
        token_symbol: str,
        chain_name: Optional[str],
        timestamp: int
    ) -> Optional[float]:
        """获取指定时间点的缓存价格"""
        try:
            # 对齐到小时
            aligned_timestamp = self.history_cache._align_to_hour(timestamp)
            
            # 查询数据库
            import aiosqlite
            async with aiosqlite.connect(self.history_cache.price_db_path) as db:
                where_conditions = ["timestamp = ?", "token_symbol = ?"]
                params = [aligned_timestamp, token_symbol]
                
                if chain_name:
                    where_conditions.append("chain_name = ?")
                    params.append(chain_name)
                
                where_clause = " AND ".join(where_conditions)
                
                async with db.execute(f"""
                    SELECT price_usdc FROM price_history 
                    WHERE {where_clause}
                    LIMIT 1
                """, params) as cursor:
                    row = await cursor.fetchone()
                    
                    if row:
                        return row[0]
                    return None
                    
        except Exception as e:
            logger.error(f"获取缓存价格失败: {e}")
            return None
    
    async def _get_cached_balance_at_time(
        self,
        address: str,
        chain_name: str,
        token_symbol: str,
        timestamp: int
    ) -> Optional[float]:
        """获取指定时间点的缓存余额"""
        try:
            # 对齐到小时
            aligned_timestamp = self.history_cache._align_to_hour(timestamp)
            
            # 查询数据库
            import aiosqlite
            async with aiosqlite.connect(self.history_cache.balance_db_path) as db:
                async with db.execute("""
                    SELECT balance FROM balance_history 
                    WHERE timestamp = ? AND address = ? AND chain_name = ? AND token_symbol = ?
                    LIMIT 1
                """, (aligned_timestamp, address, chain_name, token_symbol)) as cursor:
                    row = await cursor.fetchone()
                    
                    if row:
                        return row[0]
                    return None
                    
        except Exception as e:
            logger.error(f"获取缓存余额失败: {e}")
            return None
    
    async def fill_missing_data(
        self,
        start_date: datetime,
        end_date: datetime,
        token_symbols: Optional[List[str]] = None,
        addresses: Optional[List[str]] = None
    ) -> Dict[str, int]:
        """
        填补缺失的历史数据
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            token_symbols: 要填补的代币列表
            addresses: 要填补的地址列表
            
        Returns:
            Dict[str, int]: 填补的数据统计
        """
        try:
            logger.info(f"开始填补缺失数据: {start_date} 到 {end_date}")
            
            # 检查缺失数据
            missing_data = await self.history_cache.check_missing_data(
                start_date, end_date, token_symbols, addresses
            )
            
            filled_stats = {
                "price_records": 0,
                "balance_records": 0
            }
            
            # 填补价格数据缺口
            if missing_data["price_gaps"] and token_symbols:
                for gap_time in missing_data["price_gaps"]:
                    for token_symbol in token_symbols:
                        try:
                            # 获取当前价格作为历史价格的近似值
                            price = await self.price_service.get_token_price_usdc(token_symbol)
                            if price > 0:
                                success = await self.history_cache.save_price_history(
                                    token_symbol=token_symbol,
                                    price_usdc=price,
                                    timestamp=int(gap_time.timestamp())
                                )
                                if success:
                                    filled_stats["price_records"] += 1
                        except Exception as e:
                            logger.error(f"填补价格数据失败: {token_symbol} at {gap_time}: {e}")
            
            # 填补余额数据缺口
            if missing_data["balance_gaps"] and addresses:
                assets = await self.asset_service.get_detailed_assets()
                asset_map = {(a.address, a.chain_name, a.token_symbol): a for a in assets}
                
                for gap_time in missing_data["balance_gaps"]:
                    for address in addresses:
                        for key, asset in asset_map.items():
                            if key[0] == address:
                                try:
                                    # 获取当前余额作为历史余额的近似值
                                    balance = await self.blockchain_service.get_token_balance(
                                        asset.address, asset.token_contract_address, asset.chain_name
                                    )
                                    if balance >= 0:
                                        success = await self.history_cache.save_balance_history(
                                            address=asset.address,
                                            chain_name=asset.chain_name,
                                            token_symbol=asset.token_symbol,
                                            balance=balance,
                                            token_contract_address=asset.token_contract_address,
                                            timestamp=int(gap_time.timestamp())
                                        )
                                        if success:
                                            filled_stats["balance_records"] += 1
                                except Exception as e:
                                    logger.error(f"填补余额数据失败: {asset.id} at {gap_time}: {e}")
            
            logger.info(f"填补缺失数据完成: 价格 {filled_stats['price_records']} 条, 余额 {filled_stats['balance_records']} 条")
            return filled_stats
            
        except Exception as e:
            logger.error(f"填补缺失数据失败: {e}")
            return {"price_records": 0, "balance_records": 0}
    
    def get_update_status(self) -> Dict[str, Any]:
        """获取更新状态"""
        return {
            "is_updating": self.is_updating,
            "last_update_time": self.last_update_time.isoformat() if self.last_update_time else None,
            "update_interval_hours": self.update_interval / 3600,
            "auto_update_enabled": settings.history_auto_update_enabled,
            "stats": self.update_stats
        } 
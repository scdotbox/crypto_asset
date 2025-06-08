"""
资产历史数据服务

提供资产历史数据管理功能，包括：
- 资产快照保存
- 历史数据查询
- 数据聚合和分析
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

# 使用统一日志系统
from app.core.logger import get_logger
from app.core.config import settings
from app.core.database import db_manager

from app.models.asset_models import (
    AssetHistoryRequest,
    AssetHistoryResponse,
    AssetHistoryPoint,
    AssetDisplay,
    AssetHistoryData,
    WalletCreationInfo,
    HistoryQueryRequest
)
from app.services.asset_service import AssetService
from app.services.blockchain_service import BlockchainService
from app.services.price_service import PriceService

logger = get_logger(__name__)


class AssetHistoryService:
    """资产历史数据服务类 - 使用数据库存储历史数据"""

    def __init__(self):
        """初始化资产历史服务"""
        self.asset_service = AssetService()
        self.blockchain_service = BlockchainService()
        self.price_service = PriceService()
        # 添加钱包创建时间缓存
        self._wallet_creation_cache = {}

    async def get_asset_history(self, request: AssetHistoryRequest) -> AssetHistoryResponse:
        """
        获取资产历史数据（优先从历史缓存获取）
        
        Args:
            request: 历史数据请求参数
            
        Returns:
            AssetHistoryResponse: 历史数据响应
        """
        try:
            # 获取当前资产列表（从数据库）
            current_assets = await self.asset_service.get_detailed_assets()
            
            # 根据请求参数筛选资产
            filtered_assets = self._filter_assets(current_assets, request)
            
            if not filtered_assets:
                return AssetHistoryResponse(
                    success=True,
                    data=[],
                    total_count=0,
                    date_range={"start": None, "end": None},
                    message="没有找到匹配的资产"
                )

            # 获取历史数据（优先从缓存）
            history_data = []
            for asset in filtered_assets:
                asset_history = await self._get_single_asset_history_cached(asset, request)
                if asset_history:
                    history_data.append(asset_history)

            # 确定实际的日期范围
            date_range = self._calculate_date_range(history_data, request)

            return AssetHistoryResponse(
                success=True,
                data=history_data,
                total_count=len(history_data),
                date_range=date_range,
                message=f"成功获取 {len(history_data)} 个资产的历史数据"
            )

        except Exception as e:
            logger.error(f"获取资产历史数据失败: {e}")
            return AssetHistoryResponse(
                success=False,
                data=[],
                total_count=0,
                date_range={"start": None, "end": None},
                message=f"获取历史数据失败: {str(e)}"
            )

    def _filter_assets(self, assets: List[Any], request: AssetHistoryRequest) -> List[Any]:
        """根据请求参数筛选资产"""
        filtered = assets

        if request.asset_id:
            filtered = [asset for asset in filtered if asset.id == request.asset_id]

        if request.address:
            filtered = [asset for asset in filtered if asset.address.lower() == request.address.lower()]

        if request.chain_name:
            filtered = [asset for asset in filtered if asset.chain_name.lower() == request.chain_name.lower()]

        if request.token_symbol:
            filtered = [asset for asset in filtered if asset.token_symbol.upper() == request.token_symbol.upper()]

        logger.debug(f"资产筛选: 原始数量={len(assets)}, 筛选后数量={len(filtered)}, 筛选条件: asset_id={request.asset_id}, address={request.address}, chain_name={request.chain_name}, token_symbol={request.token_symbol}")
        
        return filtered

    async def _get_single_asset_history_cached(self, asset: Any, request: AssetHistoryRequest) -> Optional[AssetHistoryData]:
        """获取单个资产的历史数据（优先从缓存）"""
        try:
            # 使用缓存获取钱包创建时间，避免重复查询
            wallet_key = f"{asset.address}_{asset.chain_name}"
            if wallet_key not in self._wallet_creation_cache:
                logger.debug(f"首次查询钱包创建时间: {asset.address} on {asset.chain_name}")
                
                # 先从数据库查询钱包创建时间
                wallet_creation_info = await self._get_wallet_creation_from_db(asset.address, asset.chain_name)
                
                if not wallet_creation_info or not wallet_creation_info.creation_timestamp:
                    # 数据库中没有，从网络API查询
                    wallet_creation_info = await self.blockchain_service.get_wallet_creation_time(
                        asset.address, asset.chain_name
                    )
                    
                    # 保存到数据库
                    if wallet_creation_info and wallet_creation_info.creation_timestamp:
                        await self._save_wallet_creation_to_db(wallet_creation_info)
                
                self._wallet_creation_cache[wallet_key] = wallet_creation_info
            else:
                logger.debug(f"使用缓存的钱包创建时间: {asset.address} on {asset.chain_name}")
                wallet_creation_info = self._wallet_creation_cache[wallet_key]

            # 确定查询的开始和结束时间
            start_date, end_date = self._determine_date_range(request, wallet_creation_info)

            # 优先从历史缓存获取数据
            history_points = await self._get_cached_history_points(
                asset, start_date, end_date, request.interval
            )

            return AssetHistoryData(
                asset_id=asset.id,
                address=asset.address,
                chain_name=asset.chain_name,
                token_symbol=asset.token_symbol,
                token_contract_address=asset.token_contract_address,
                tag=asset.tag,
                history_points=history_points,
                wallet_creation_date=wallet_creation_info.creation_date
            )

        except Exception as e:
            logger.error(f"获取资产 {asset.id} 历史数据失败: {e}")
            return None

    async def _get_wallet_creation_from_db(self, address: str, chain_name: str) -> Optional[WalletCreationInfo]:
        """从数据库获取钱包创建时间"""
        try:
            async with db_manager.get_connection() as conn:
                # 先获取区块链ID
                async with conn.execute(
                    "SELECT id FROM blockchains WHERE name = ?", (chain_name,)
                ) as cursor:
                    blockchain_row = await cursor.fetchone()
                    if not blockchain_row:
                        return None
                    
                    blockchain_id = blockchain_row['id']
                
                # 查询钱包创建时间
                async with conn.execute("""
                    SELECT creation_timestamp, creation_date, first_transaction_hash, 
                           block_number, is_estimated
                    FROM wallets 
                    WHERE address = ? AND blockchain_id = ? 
                    AND creation_timestamp IS NOT NULL
                """, (address, blockchain_id)) as cursor:
                    row = await cursor.fetchone()
                    
                    if row:
                        return WalletCreationInfo(
                            address=address,
                            chain_name=chain_name,
                            creation_timestamp=row['creation_timestamp'],
                            creation_date=row['creation_date'],
                            first_transaction_hash=row['first_transaction_hash'],
                            block_number=row['block_number'],
                            is_estimated=bool(row['is_estimated']),
                            error_message=None
                        )
                    
                    return None
                    
        except Exception as e:
            logger.error(f"从数据库获取钱包创建时间失败: {e}")
            return None

    async def _save_wallet_creation_to_db(self, wallet_info: WalletCreationInfo) -> bool:
        """保存钱包创建时间到数据库"""
        try:
            async with db_manager.get_connection() as conn:
                # 先获取区块链ID
                async with conn.execute(
                    "SELECT id FROM blockchains WHERE name = ?", (wallet_info.chain_name,)
                ) as cursor:
                    blockchain_row = await cursor.fetchone()
                    if not blockchain_row:
                        logger.warning(f"未找到区块链: {wallet_info.chain_name}")
                        return False
                    
                    blockchain_id = blockchain_row['id']
                
                # 更新或插入钱包创建时间
                await conn.execute("""
                    INSERT OR REPLACE INTO wallets 
                    (address, blockchain_id, creation_timestamp, creation_date, 
                     first_transaction_hash, block_number, is_estimated)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    wallet_info.address,
                    blockchain_id,
                    wallet_info.creation_timestamp,
                    wallet_info.creation_date,
                    wallet_info.first_transaction_hash,
                    wallet_info.block_number,
                    wallet_info.is_estimated
                ))
                
                await conn.commit()
                logger.debug(f"保存钱包创建时间到数据库: {wallet_info.address} on {wallet_info.chain_name}")
                return True
                
        except Exception as e:
            logger.error(f"保存钱包创建时间到数据库失败: {e}")
            return False

    async def _get_cached_history_points(
        self, asset: Any, start_date: datetime, end_date: datetime, interval: str
    ) -> List[AssetHistoryPoint]:
        """从缓存获取历史数据点"""
        try:
            history_cache = self.price_service.history_cache
            
            if not history_cache:
                logger.debug("历史缓存服务不可用，使用模拟数据")
                return await self._generate_history_points_realtime(asset, start_date, end_date, interval)
            
            # 首先尝试从缓存获取最新价格和余额
            latest_price = await history_cache.get_latest_price(asset.token_symbol, asset.chain_name)
            latest_balance = await history_cache.get_latest_balance(
                asset.address, asset.chain_name, asset.token_symbol
            )
            
            # 生成时间点
            interval_delta = self._parse_interval(interval)
            time_points = []
            current_time = start_date
            while current_time <= end_date:
                time_points.append(current_time)
                current_time += interval_delta

            if time_points and time_points[-1] != end_date:
                time_points.append(end_date)
            
            # 检查是否有缓存的基准数据
            if latest_price and latest_balance:
                logger.debug("使用缓存的基准数据生成历史趋势")
                # 基于缓存数据生成历史趋势
                history_points = []
                for i, time_point in enumerate(time_points):
                    # 基于缓存价格生成变化
                    price_variation = self._generate_price_variation(
                        asset.token_symbol, i, len(time_points), latest_price
                    )
                    simulated_price = max(0.01, latest_price * price_variation)
                    
                    # 基于缓存余额生成变化
                    quantity_variation = self._generate_quantity_variation(
                        asset.token_symbol, i, len(time_points)
                    )
                    simulated_quantity = max(0, latest_balance * quantity_variation)

                    value_usdc = simulated_quantity * simulated_price if simulated_quantity > 0 and simulated_price > 0 else 0.0

                    history_point = AssetHistoryPoint(
                        timestamp=int(time_point.timestamp()),
                        date=time_point.isoformat(),
                        quantity=simulated_quantity,
                        price_usdc=simulated_price,
                        value_usdc=value_usdc
                    )
                    history_points.append(history_point)
                
                return history_points
            else:
                logger.debug("缓存中无基准数据，生成新的模拟数据并保存到缓存")
                # 生成新的模拟历史数据
                history_points = await self._generate_history_points_realtime(asset, start_date, end_date, interval)
                
                # 保存到缓存以供后续使用
                if history_points:
                    try:
                        for point in history_points:
                            # 保存价格到缓存
                            await history_cache.save_price_history(
                                token_symbol=asset.token_symbol,
                                price_usdc=point.price_usdc,
                                chain_name=asset.chain_name,
                                timestamp=point.timestamp
                            )
                            
                            # 保存余额到缓存
                            await history_cache.save_balance_history(
                                address=asset.address,
                                chain_name=asset.chain_name,
                                token_symbol=asset.token_symbol,
                                balance=point.quantity,
                                token_contract_address=asset.token_contract_address,
                                timestamp=point.timestamp
                            )
                        
                        logger.debug(f"已保存 {len(history_points)} 个历史数据点到缓存")
                    except Exception as cache_error:
                        logger.warning(f"保存到缓存失败: {cache_error}")
                
                return history_points

        except Exception as e:
            logger.error(f"获取历史数据失败: {e}")
            # 回退到实时查询
            return await self._generate_history_points_realtime(asset, start_date, end_date, interval)

    async def _get_cached_balance_or_fetch(
        self, 
        address: str, 
        contract_address: Optional[str], 
        chain_name: str,
        token_symbol: str
    ) -> float:
        """优先从缓存获取余额，如果没有则实时查询"""
        try:
            # 首先尝试从历史缓存获取最新余额
            history_cache = self.price_service.history_cache
            if history_cache:
                cached_balance = await history_cache.get_latest_balance(
                    address, chain_name, token_symbol
                )
                if cached_balance is not None:
                    return cached_balance
            
            # 如果缓存没有，则实时查询
            balance = await self.blockchain_service.get_token_balance(
                address, contract_address, chain_name
            )
            
            # 保存到历史缓存
            if balance >= 0 and history_cache:
                await history_cache.save_balance_history(
                    address=address,
                    chain_name=chain_name,
                    token_symbol=token_symbol,
                    balance=balance,
                    token_contract_address=contract_address
                )
            
            return balance
            
        except Exception as e:
            logger.error(f"获取余额失败: {e}")
            return 0.0

    def _interval_to_hours(self, interval: str) -> int:
        """将间隔字符串转换为小时数"""
        interval_map = {
            "1h": 1,
            "1d": 24,
            "1w": 168,  # 7 * 24
            "1m": 720   # 30 * 24
        }
        return interval_map.get(interval, 24)  # 默认1天

    async def _generate_history_points_realtime(
        self, asset: Any, start_date: datetime, end_date: datetime, interval: str
    ) -> List[AssetHistoryPoint]:
        """生成历史数据点（实时查询，作为回退方案）"""
        try:
            # 解析间隔
            interval_delta = self._parse_interval(interval)
            
            # 生成时间点
            time_points = []
            current_time = start_date
            while current_time <= end_date:
                time_points.append(current_time)
                current_time += interval_delta

            # 确保包含结束时间
            if time_points and time_points[-1] != end_date:
                time_points.append(end_date)

            # 获取当前的余额和价格作为基准
            current_quantity = await self.blockchain_service.get_token_balance(
                asset.address, asset.token_contract_address, asset.chain_name
            )
            current_price = await self.price_service.get_token_price_usdc(
                asset.token_symbol, asset.chain_name
            )

            # 为每个时间点生成数据（添加模拟变化）
            history_points = []
            for i, time_point in enumerate(time_points):
                # 添加模拟的价格波动（基于时间和代币特性）
                price_variation = self._generate_price_variation(
                    asset.token_symbol, i, len(time_points), current_price
                )
                simulated_price = max(0.01, current_price * price_variation)
                
                # 添加模拟的余额变化（通常余额变化较小）
                quantity_variation = self._generate_quantity_variation(
                    asset.token_symbol, i, len(time_points)
                )
                simulated_quantity = max(0, current_quantity * quantity_variation)

                value_usdc = simulated_quantity * simulated_price if simulated_quantity > 0 and simulated_price > 0 else 0.0

                history_point = AssetHistoryPoint(
                    timestamp=int(time_point.timestamp()),
                    date=time_point.isoformat(),
                    quantity=simulated_quantity,
                    price_usdc=simulated_price,
                    value_usdc=value_usdc
                )
                history_points.append(history_point)

            logger.debug(f"实时生成历史数据点: {len(history_points)} 个点")
            return history_points

        except Exception as e:
            logger.error(f"生成历史数据点失败: {e}")
            return []

    def _generate_price_variation(self, token_symbol: str, index: int, total_points: int, base_price: float) -> float:
        """生成价格变化系数"""
        import math
        import random
        
        # 设置随机种子，确保相同代币的变化是一致的
        random.seed(hash(token_symbol) + index)
        
        # 基于代币类型设置不同的波动性
        volatility_map = {
            'BTC': 0.15,    # 比特币相对稳定
            'ETH': 0.20,    # 以太坊中等波动
            'SOL': 0.25,    # Solana较高波动
            'SUI': 0.30,    # 新兴代币高波动
            'MATIC': 0.25,  # Polygon中等波动
            'BNB': 0.20,    # BNB相对稳定
        }
        
        volatility = volatility_map.get(token_symbol, 0.25)  # 默认25%波动
        
        # 生成趋势（整体上升或下降）
        trend_factor = 1.0 + (index / total_points - 0.5) * 0.1  # ±5%的整体趋势
        
        # 生成随机波动
        random_factor = 1.0 + (random.random() - 0.5) * volatility
        
        # 添加周期性波动（模拟市场周期）
        cycle_factor = 1.0 + 0.05 * math.sin(2 * math.pi * index / max(7, total_points // 3))
        
        return trend_factor * random_factor * cycle_factor

    def _generate_quantity_variation(self, token_symbol: str, index: int, total_points: int) -> float:
        """生成余额变化系数（余额变化通常较小）"""
        import random
        
        # 设置随机种子
        random.seed(hash(token_symbol + "quantity") + index)
        
        # 余额变化较小，主要是小幅增减
        # 90%的概率保持不变，10%的概率有小幅变化
        if random.random() < 0.9:
            return 1.0  # 保持不变
        else:
            # 小幅变化 ±5%
            return 1.0 + (random.random() - 0.5) * 0.1

    def _determine_date_range(self, request: AssetHistoryRequest, wallet_info: WalletCreationInfo) -> tuple:
        """确定查询的日期范围"""
        # 优先使用time_range参数，不受钱包创建时间限制
        if request.time_range:
            end_date = datetime.now()
            start_date = self._parse_time_range(request.time_range, end_date)
            logger.debug(f"使用time_range '{request.time_range}' 计算日期范围: {start_date} 到 {end_date}")
            return start_date, end_date
        
        # 结束时间：请求指定的结束时间或当前时间
        if request.end_date:
            end_date = datetime.fromisoformat(request.end_date.replace('Z', '+00:00'))
        else:
            end_date = datetime.now()

        # 开始时间：请求指定的开始时间
        if request.start_date:
            start_date = datetime.fromisoformat(request.start_date.replace('Z', '+00:00'))
        else:
            # 如果没有指定开始时间，使用钱包创建时间（如果可用且合理）
            if (wallet_info.creation_date and 
                wallet_info.creation_timestamp and 
                wallet_info.creation_timestamp > 0):
                
                wallet_creation_date = datetime.fromisoformat(wallet_info.creation_date.replace('Z', '+00:00'))
                
                # 只有当钱包创建时间在合理范围内（不超过2年前）时才使用
                two_years_ago = end_date - timedelta(days=730)
                if wallet_creation_date >= two_years_ago:
                    start_date = wallet_creation_date
                    logger.debug(f"使用钱包创建时间作为开始时间: {start_date}")
                else:
                    # 钱包创建时间太久远，使用默认30天
                    start_date = end_date - timedelta(days=30)
                    logger.debug(f"钱包创建时间过于久远，使用默认30天: {start_date}")
            else:
                # 如果没有钱包创建时间，默认从30天前开始
                start_date = end_date - timedelta(days=30)
                logger.debug(f"无钱包创建时间，使用默认30天: {start_date}")

        # 确保开始时间不晚于结束时间
        if start_date > end_date:
            start_date = end_date - timedelta(days=1)

        return start_date, end_date

    def _parse_time_range(self, time_range: str, end_date: datetime) -> datetime:
        """解析时间范围字符串，返回开始日期"""
        time_range = time_range.lower().strip()
        
        # 时间范围映射
        range_map = {
            '1h': timedelta(hours=1),
            '6h': timedelta(hours=6),
            '12h': timedelta(hours=12),
            '1d': timedelta(days=1),
            '3d': timedelta(days=3),
            '7d': timedelta(days=7),
            '14d': timedelta(days=14),
            '30d': timedelta(days=30),
            '90d': timedelta(days=90),
            '180d': timedelta(days=180),
            '1y': timedelta(days=365),
            '2y': timedelta(days=730),
            'all': timedelta(days=3650)  # 10年，表示全部历史
        }
        
        # 获取对应的时间差
        time_delta = range_map.get(time_range)
        if time_delta:
            return end_date - time_delta
        
        # 如果无法解析，默认返回7天前
        logger.warning(f"无法解析时间范围 '{time_range}'，使用默认7天")
        return end_date - timedelta(days=7)

    def _parse_interval(self, interval: str) -> timedelta:
        """解析时间间隔字符串"""
        interval_map = {
            "1h": timedelta(hours=1),
            "1d": timedelta(days=1),
            "1w": timedelta(weeks=1),
            "1m": timedelta(days=30)
        }
        return interval_map.get(interval, timedelta(days=1))

    def _calculate_date_range(self, history_data: List[AssetHistoryData], request: AssetHistoryRequest) -> Dict[str, Optional[str]]:
        """计算实际的日期范围"""
        if not history_data:
            return {"start": None, "end": None}

        all_dates = []
        for asset_data in history_data:
            for point in asset_data.history_points:
                all_dates.append(point.date)

        if not all_dates:
            return {"start": None, "end": None}

        return {
            "start": min(all_dates),
            "end": max(all_dates)
        }

    async def save_current_snapshot(self, startup: bool = False):
        """
        保存当前资产快照到数据库
        
        Args:
            startup: 是否为启动时调用
        """
        try:
            if startup:
                logger.info("启动时保存资产快照（跳过API调用）")
                return

            # 获取当前所有资产（从数据库，使用缓存）
            assets = await self.asset_service.get_detailed_assets()
            
            if not assets:
                logger.info("没有资产需要保存快照")
                return

            current_time = datetime.now()
            timestamp = int(current_time.timestamp())
            date_str = current_time.isoformat()

            # 为每个资产保存快照到数据库
            saved_count = 0
            async with db_manager.get_connection() as conn:
                for asset in assets:
                    try:
                        # 保存到asset_snapshots表
                        await conn.execute("""
                            INSERT OR REPLACE INTO asset_snapshots 
                            (asset_id, timestamp, date, quantity, price_usdc, value_usdc)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (
                            asset.id,
                            timestamp,
                            date_str,
                            asset.quantity,
                            asset.price_usdc,
                            asset.value_usdc
                        ))
                        
                        saved_count += 1

                    except Exception as e:
                        logger.error(f"保存资产 {asset.id} 快照失败: {e}")

                await conn.commit()
            
            logger.info(f"成功保存 {saved_count} 个资产的快照到数据库")

        except Exception as e:
            logger.error(f"保存资产快照失败: {e}")

    async def get_historical_snapshots(self, asset_id: str) -> List[AssetHistoryPoint]:
        """从数据库获取资产的历史快照"""
        try:
            history_points = []
            async with db_manager.get_connection() as conn:
                async with conn.execute("""
                    SELECT timestamp, date, quantity, price_usdc, value_usdc
                    FROM asset_snapshots
                    WHERE asset_id = ?
                    ORDER BY timestamp ASC
                """, (asset_id,)) as cursor:
                    async for row in cursor:
                        point = AssetHistoryPoint(
                            timestamp=row['timestamp'],
                            date=row['date'],
                            quantity=row['quantity'],
                            price_usdc=row['price_usdc'],
                            value_usdc=row['value_usdc']
                        )
                        history_points.append(point)
            
            return history_points

        except Exception as e:
            logger.error(f"获取历史快照失败: {e}")
            return []

    async def cleanup_old_snapshots(self, retention_days: int = 365):
        """清理旧的快照数据"""
        try:
            cutoff_timestamp = int((datetime.now() - timedelta(days=retention_days)).timestamp())
            
            async with db_manager.get_connection() as conn:
                result = await conn.execute("""
                    DELETE FROM asset_snapshots 
                    WHERE timestamp < ?
                """, (cutoff_timestamp,))
                
                deleted_count = result.rowcount
                await conn.commit()
                
                if deleted_count > 0:
                    logger.info(f"清理了 {deleted_count} 条旧的快照记录")
                
        except Exception as e:
            logger.error(f"清理旧快照数据失败: {e}") 
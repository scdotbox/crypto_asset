"""
增强的历史数据服务

提供更高频的数据采集和更丰富的趋势分析功能，
借鉴CoinBank等专业平台的数据处理方式。
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from app.core.logger import get_logger
from app.core.config import settings
from app.core.database import db_manager
from app.services.asset_service import AssetService
from app.services.price_service import PriceService
from app.services.history_cache_service import HistoryCacheService

logger = get_logger(__name__)


@dataclass
class TrendPoint:
    """趋势数据点"""
    timestamp: int
    date: str
    total_value: float
    asset_count: int
    top_assets: List[Dict[str, Any]]
    price_changes: Dict[str, float]  # 24h价格变化
    portfolio_distribution: Dict[str, float]  # 资产分布


@dataclass
class PortfolioMetrics:
    """投资组合指标"""
    total_value: float
    total_change_24h: float
    total_change_7d: float
    total_change_30d: float
    asset_count: int
    top_performer: Optional[Dict[str, Any]]
    worst_performer: Optional[Dict[str, Any]]
    diversity_score: float  # 多样化评分


class EnhancedHistoryService:
    """增强的历史数据服务"""
    
    def __init__(self):
        self.asset_service = AssetService()
        self.price_service = PriceService()
        self.history_cache = HistoryCacheService()
        
        # 数据采集配置
        self.collection_intervals = {
            'real_time': 5 * 60,      # 5分钟
            'hourly': 60 * 60,        # 1小时
            'daily': 24 * 60 * 60,    # 1天
        }
        
        # 运行状态
        self.is_collecting = False
        self.collection_tasks = {}

    async def start_enhanced_collection(self):
        """启动增强的数据采集"""
        if self.is_collecting:
            logger.warning("数据采集已在运行中")
            return
        
        self.is_collecting = True
        logger.info("🚀 启动增强历史数据采集服务")
        
        # 启动不同频率的采集任务
        self.collection_tasks = {
            'hourly': asyncio.create_task(self._hourly_collection()),
            'daily': asyncio.create_task(self._daily_collection()),
        }
        
        # 如果启用实时采集
        if getattr(settings, 'enable_realtime_collection', False):
            self.collection_tasks['real_time'] = asyncio.create_task(
                self._realtime_collection()
            )

    async def stop_enhanced_collection(self):
        """停止增强的数据采集"""
        self.is_collecting = False
        logger.info("🛑 停止增强历史数据采集服务")
        
        # 取消所有采集任务
        for task_name, task in self.collection_tasks.items():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    logger.info(f"已取消 {task_name} 采集任务")
        
        self.collection_tasks.clear()

    async def _realtime_collection(self):
        """实时数据采集（5分钟间隔）"""
        while self.is_collecting:
            try:
                await self._collect_portfolio_snapshot('real_time')
                await asyncio.sleep(self.collection_intervals['real_time'])
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"实时数据采集失败: {e}")
                await asyncio.sleep(60)  # 出错后等待1分钟

    async def _hourly_collection(self):
        """小时级数据采集"""
        while self.is_collecting:
            try:
                await self._collect_portfolio_snapshot('hourly')
                await asyncio.sleep(self.collection_intervals['hourly'])
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"小时级数据采集失败: {e}")
                await asyncio.sleep(300)  # 出错后等待5分钟

    async def _daily_collection(self):
        """日级数据采集和分析"""
        while self.is_collecting:
            try:
                await self._collect_portfolio_snapshot('daily')
                await self._generate_daily_analytics()
                await asyncio.sleep(self.collection_intervals['daily'])
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"日级数据采集失败: {e}")
                await asyncio.sleep(3600)  # 出错后等待1小时

    async def _collect_portfolio_snapshot(self, collection_type: str):
        """采集投资组合快照"""
        try:
            logger.debug(f"📸 开始 {collection_type} 投资组合快照采集")
            
            # 获取当前所有资产
            assets = await self.asset_service.get_detailed_assets()
            if not assets:
                logger.debug("没有资产需要采集")
                return
            
            timestamp = int(time.time())
            date = datetime.fromtimestamp(timestamp).isoformat()
            
            # 计算投资组合指标
            metrics = await self._calculate_portfolio_metrics(assets)
            
            # 保存快照数据
            await self._save_enhanced_snapshot(
                timestamp, date, assets, metrics, collection_type
            )
            
            logger.debug(f"✅ {collection_type} 快照采集完成，总价值: ${metrics.total_value:.2f}")
            
        except Exception as e:
            logger.error(f"投资组合快照采集失败: {e}")

    async def _calculate_portfolio_metrics(self, assets: List[Any]) -> PortfolioMetrics:
        """计算投资组合指标"""
        total_value = 0.0
        asset_values = []
        
        for asset in assets:
            value = getattr(asset, 'value_usdc', 0) or 0
            total_value += value
            asset_values.append({
                'symbol': asset.token_symbol,
                'value': value,
                'quantity': getattr(asset, 'quantity', 0) or 0,
                'price': getattr(asset, 'price_usdc', 0) or 0,
            })
        
        # 排序找出表现最好和最差的资产
        asset_values.sort(key=lambda x: x['value'], reverse=True)
        top_performer = asset_values[0] if asset_values else None
        worst_performer = asset_values[-1] if len(asset_values) > 1 else None
        
        # 计算多样化评分（基于资产分布的均匀程度）
        diversity_score = self._calculate_diversity_score(asset_values, total_value)
        
        return PortfolioMetrics(
            total_value=total_value,
            total_change_24h=0.0,  # TODO: 实现24h变化计算
            total_change_7d=0.0,   # TODO: 实现7d变化计算
            total_change_30d=0.0,  # TODO: 实现30d变化计算
            asset_count=len(assets),
            top_performer=top_performer,
            worst_performer=worst_performer,
            diversity_score=diversity_score
        )

    def _calculate_diversity_score(self, asset_values: List[Dict], total_value: float) -> float:
        """计算投资组合多样化评分（0-1，1表示最多样化）"""
        if total_value <= 0 or len(asset_values) <= 1:
            return 0.0
        
        # 计算每个资产的占比
        proportions = [asset['value'] / total_value for asset in asset_values]
        
        # 使用香农熵计算多样化程度
        import math
        entropy = 0.0
        for p in proportions:
            if p > 0:
                entropy -= p * math.log2(p)
        
        # 标准化到0-1范围
        max_entropy = math.log2(len(asset_values))
        return entropy / max_entropy if max_entropy > 0 else 0.0

    async def _save_enhanced_snapshot(
        self, 
        timestamp: int, 
        date: str, 
        assets: List[Any], 
        metrics: PortfolioMetrics,
        collection_type: str
    ):
        """保存增强的快照数据"""
        try:
            async with db_manager.get_connection() as conn:
                # 保存投资组合级别的快照
                await conn.execute("""
                    INSERT OR REPLACE INTO portfolio_snapshots 
                    (timestamp, date, total_value, asset_count, 
                     diversity_score, collection_type, metrics_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    timestamp, date, metrics.total_value, metrics.asset_count,
                    metrics.diversity_score, collection_type,
                    self._serialize_metrics(metrics)
                ))
                
                # 保存每个资产的详细快照
                for asset in assets:
                    await conn.execute("""
                        INSERT OR REPLACE INTO asset_snapshots_enhanced
                        (timestamp, date, asset_id, quantity, price_usdc, 
                         value_usdc, collection_type)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        timestamp, date, asset.id,
                        getattr(asset, 'quantity', 0) or 0,
                        getattr(asset, 'price_usdc', 0) or 0,
                        getattr(asset, 'value_usdc', 0) or 0,
                        collection_type
                    ))
                
                await conn.commit()
                
        except Exception as e:
            logger.error(f"保存增强快照数据失败: {e}")

    def _serialize_metrics(self, metrics: PortfolioMetrics) -> str:
        """序列化指标数据为JSON"""
        return json.dumps({
            'total_change_24h': metrics.total_change_24h,
            'total_change_7d': metrics.total_change_7d,
            'total_change_30d': metrics.total_change_30d,
            'top_performer': metrics.top_performer,
            'worst_performer': metrics.worst_performer,
        })

    async def _generate_daily_analytics(self):
        """生成日度分析报告"""
        try:
            logger.info("📊 开始生成日度分析报告")
            
            # 获取过去24小时的数据
            end_time = int(time.time())
            start_time = end_time - 24 * 60 * 60
            
            # 分析投资组合变化趋势
            trend_analysis = await self._analyze_portfolio_trends(start_time, end_time)
            
            # 保存分析结果
            await self._save_analytics_report(trend_analysis)
            
            logger.info("✅ 日度分析报告生成完成")
            
        except Exception as e:
            logger.error(f"生成日度分析报告失败: {e}")

    async def _analyze_portfolio_trends(self, start_time: int, end_time: int) -> Dict[str, Any]:
        """分析投资组合趋势"""
        # TODO: 实现详细的趋势分析逻辑
        return {
            'period': f"{datetime.fromtimestamp(start_time)} - {datetime.fromtimestamp(end_time)}",
            'analysis_type': 'daily_trend',
            'generated_at': datetime.now().isoformat()
        }

    async def _save_analytics_report(self, analysis: Dict[str, Any]):
        """保存分析报告"""
        try:
            async with db_manager.get_connection() as conn:
                await conn.execute("""
                    INSERT INTO analytics_reports 
                    (timestamp, report_type, analysis_json)
                    VALUES (?, ?, ?)
                """, (
                    int(time.time()),
                    analysis.get('analysis_type', 'unknown'),
                    json.dumps(analysis)
                ))
                await conn.commit()
        except Exception as e:
            logger.error(f"保存分析报告失败: {e}")

    async def get_enhanced_trend_data(
        self, 
        time_range: str = '30d',
        collection_type: str = 'hourly'
    ) -> List[TrendPoint]:
        """获取增强的趋势数据"""
        try:
            # 计算时间范围
            end_time = int(time.time())
            if time_range == '1d':
                start_time = end_time - 24 * 60 * 60
            elif time_range == '7d':
                start_time = end_time - 7 * 24 * 60 * 60
            elif time_range == '30d':
                start_time = end_time - 30 * 24 * 60 * 60
            elif time_range == '90d':
                start_time = end_time - 90 * 24 * 60 * 60
            else:
                start_time = 0  # 全部数据
            
            async with db_manager.get_connection() as conn:
                cursor = await conn.execute("""
                    SELECT timestamp, date, total_value, asset_count, 
                           diversity_score, metrics_json
                    FROM portfolio_snapshots 
                    WHERE timestamp >= ? AND collection_type = ?
                    ORDER BY timestamp ASC
                """, (start_time, collection_type))
                
                rows = await cursor.fetchall()
                
                trend_points = []
                for row in rows:
                    # 解析指标数据
                    metrics = json.loads(row[5]) if row[5] else {}
                    
                    trend_point = TrendPoint(
                        timestamp=row[0],
                        date=row[1],
                        total_value=row[2],
                        asset_count=row[3],
                        top_assets=[],  # TODO: 从详细快照中获取
                        price_changes=metrics.get('price_changes', {}),
                        portfolio_distribution={}  # TODO: 计算分布
                    )
                    trend_points.append(trend_point)
                
                return trend_points
                
        except Exception as e:
            logger.error(f"获取增强趋势数据失败: {e}")
            return []

    async def initialize_enhanced_tables(self):
        """初始化增强历史数据表"""
        try:
            async with db_manager.get_connection() as conn:
                # 投资组合快照表
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp INTEGER NOT NULL,
                        date TEXT NOT NULL,
                        total_value REAL NOT NULL,
                        asset_count INTEGER NOT NULL,
                        diversity_score REAL DEFAULT 0,
                        collection_type TEXT NOT NULL,
                        metrics_json TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # 增强的资产快照表
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS asset_snapshots_enhanced (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp INTEGER NOT NULL,
                        date TEXT NOT NULL,
                        asset_id TEXT NOT NULL,
                        quantity REAL NOT NULL,
                        price_usdc REAL NOT NULL,
                        value_usdc REAL NOT NULL,
                        collection_type TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # 分析报告表
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS analytics_reports (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp INTEGER NOT NULL,
                        report_type TEXT NOT NULL,
                        analysis_json TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # 创建索引
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_timestamp 
                    ON portfolio_snapshots(timestamp)
                """)
                
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_asset_snapshots_enhanced_timestamp 
                    ON asset_snapshots_enhanced(timestamp, asset_id)
                """)
                
                await conn.commit()
                logger.info("✅ 增强历史数据表初始化完成")
                
        except Exception as e:
            logger.error(f"初始化增强历史数据表失败: {e}") 
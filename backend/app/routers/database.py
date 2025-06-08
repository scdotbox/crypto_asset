"""
数据库管理路由模块

包含数据库初始化、统计、清理、重置等相关API端点
"""

from fastapi import APIRouter, HTTPException

from app.models.asset_models import (
    DatabaseClearResponse,
    DatabaseResetResponse,
)
from app.core.database import db_manager
from app.core.logger import get_logger

logger = get_logger(__name__)

# 创建路由器
router = APIRouter(prefix="/api", tags=["数据库管理"])


@router.post("/database/init", response_model=dict)
async def init_database():
    """初始化数据库"""
    try:
        await db_manager.init_database()
        return {
            "status": "success",
            "message": "数据库初始化成功"
        }
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        raise HTTPException(status_code=500, detail=f"数据库初始化失败: {str(e)}")


@router.get("/database/stats", response_model=dict)
async def get_database_stats():
    """获取数据库统计信息"""
    try:
        async with db_manager.get_connection() as conn:
            stats = {}
            
            # 获取各个表的记录数量
            tables = [
                "assets",
                "wallets", 
                "tokens",
                "blockchains",
                "asset_snapshots",
                "price_cache",
                "price_history",
                "balance_history"
            ]
            
            for table in tables:
                try:
                    async with conn.execute(f"SELECT COUNT(*) as count FROM {table}") as cursor:
                        row = await cursor.fetchone()
                        stats[f"{table}_count"] = row['count'] if row else 0
                except Exception as e:
                    logger.warning(f"获取表 {table} 统计失败: {e}")
                    stats[f"{table}_count"] = 0
            
            # 获取数据库大小
            try:
                async with conn.execute("PRAGMA page_count") as cursor:
                    page_count_row = await cursor.fetchone()
                async with conn.execute("PRAGMA page_size") as cursor:
                    page_size_row = await cursor.fetchone()
                
                if page_count_row and page_size_row:
                    db_size = page_count_row[0] * page_size_row[0]
                    stats["database_size_bytes"] = db_size
                    stats["database_size_mb"] = round(db_size / (1024 * 1024), 2)
                else:
                    stats["database_size_bytes"] = 0
                    stats["database_size_mb"] = 0
            except Exception as e:
                logger.warning(f"获取数据库大小失败: {e}")
                stats["database_size_bytes"] = 0
                stats["database_size_mb"] = 0
            
            # 添加一些计算字段
            stats["total_records"] = sum(
                stats.get(f"{table}_count", 0) for table in tables
            )
            
            return {
                "success": True,
                "message": "数据库统计信息获取成功",
                "data": stats
            }
            
    except Exception as e:
        logger.error(f"获取数据库统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取数据库统计失败: {str(e)}")


@router.get("/database/management-stats")
async def get_database_management_stats():
    """获取数据库管理统计信息"""
    try:
        async with db_manager.get_connection() as conn:
            stats = {}
            
            # 获取最近的记录时间戳
            recent_tables = {
                "assets": "created_at",
                "asset_snapshots": "timestamp",
                "price_history": "timestamp",
                "balance_history": "timestamp"
            }
            
            for table, timestamp_col in recent_tables.items():
                try:
                    query = f"SELECT {timestamp_col} FROM {table} ORDER BY {timestamp_col} DESC LIMIT 1"
                    async with conn.execute(query) as cursor:
                        row = await cursor.fetchone()
                        if row:
                            stats[f"latest_{table}_time"] = row[0]
                        else:
                            stats[f"latest_{table}_time"] = None
                except Exception as e:
                    logger.warning(f"获取表 {table} 最新时间戳失败: {e}")
                    stats[f"latest_{table}_time"] = None
            
            # 获取缓存表的数据分布
            try:
                # 价格历史按代币符号分组统计（通过JOIN获取token symbol）
                async with conn.execute("""
                    SELECT t.symbol as token_symbol, COUNT(*) as count 
                    FROM price_history ph
                    JOIN tokens t ON ph.token_id = t.id
                    GROUP BY t.symbol 
                    ORDER BY count DESC 
                    LIMIT 10
                """) as cursor:
                    price_distribution = []
                    async for row in cursor:
                        price_distribution.append({
                            "token_symbol": row[0],
                            "count": row[1]
                        })
                    stats["price_history_distribution"] = price_distribution
            except Exception as e:
                logger.warning(f"获取价格历史分布失败: {e}")
                stats["price_history_distribution"] = []
            
            # 余额历史按链名称分组统计（通过多层JOIN获取chain name）
            try:
                async with conn.execute("""
                    SELECT b.display_name as chain_name, COUNT(*) as count 
                    FROM balance_history bh
                    JOIN assets a ON bh.asset_id = a.id
                    JOIN wallets w ON a.wallet_id = w.id
                    JOIN blockchains b ON w.blockchain_id = b.id
                    GROUP BY b.display_name 
                    ORDER BY count DESC 
                    LIMIT 10
                """) as cursor:
                    balance_distribution = []
                    async for row in cursor:
                        balance_distribution.append({
                            "chain_name": row[0],
                            "count": row[1]
                        })
                    stats["balance_history_distribution"] = balance_distribution
            except Exception as e:
                logger.warning(f"获取余额历史分布失败: {e}")
                stats["balance_history_distribution"] = []
            
            return {
                "status": "success",
                "data": stats
            }
            
    except Exception as e:
        logger.error(f"获取数据库管理统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取数据库管理统计失败: {str(e)}")


@router.post("/database/clear-all", response_model=DatabaseClearResponse)
async def clear_all_database_data():
    """
    清空所有数据库数据
    
    警告：此操作将删除所有数据，包括：
    - 所有资产记录
    - 所有钱包记录
    - 所有代币记录
    - 所有区块链记录
    - 所有历史快照
    - 所有价格缓存
    - 所有余额历史
    - 所有价格历史
    
    此操作不可逆！
    """
    try:
        logger.warning("开始清空所有数据库数据...")
        
        async with db_manager.get_connection() as conn:
            # 删除所有表的数据（按依赖关系顺序）
            tables_to_clear = [
                "asset_snapshots",      # 资产快照
                "balance_history",      # 余额历史
                "price_history",        # 价格历史
                "price_cache",          # 价格缓存
                "assets",               # 资产记录
                "wallets",              # 钱包记录
                "tokens",               # 代币记录
                "blockchains"           # 区块链记录
            ]
            
            cleared_counts = {}
            total_cleared = 0
            
            for table in tables_to_clear:
                try:
                    # 先查询记录数量
                    async with conn.execute(f"SELECT COUNT(*) as count FROM {table}") as cursor:
                        row = await cursor.fetchone()
                        count = row['count'] if row else 0
                    
                    if count > 0:
                        # 删除数据
                        await conn.execute(f"DELETE FROM {table}")
                        cleared_counts[table] = count
                        total_cleared += count
                        logger.info(f"清空表 {table}: {count} 条记录")
                    else:
                        cleared_counts[table] = 0
                        
                except Exception as e:
                    logger.error(f"清空表 {table} 失败: {e}")
                    cleared_counts[table] = -1
            
            # 重置自增ID序列
            try:
                await conn.execute("DELETE FROM sqlite_sequence")
                logger.info("重置自增ID序列")
            except Exception as e:
                logger.warning(f"重置自增ID序列失败: {e}")
            
            # 提交事务
            await conn.commit()
            
        logger.warning(f"数据库清空完成，总共删除 {total_cleared} 条记录")
        
        return DatabaseClearResponse(
            success=True,
            message=f"数据库清空成功，总共删除 {total_cleared} 条记录",
            cleared_counts=cleared_counts,
            total_cleared=total_cleared
        )
        
    except Exception as e:
        logger.error(f"清空数据库失败: {e}")
        return DatabaseClearResponse(
            success=False,
            message=f"清空数据库失败: {str(e)}",
            cleared_counts={},
            total_cleared=0
        )


@router.post("/database/reset", response_model=DatabaseResetResponse)
async def reset_database():
    """
    重置数据库
    
    此操作将：
    1. 清空所有数据
    2. 重新初始化数据库表结构
    3. 添加默认的区块链配置
    """
    try:
        logger.warning("开始重置数据库...")
        
        # 先清空所有数据
        clear_result = await clear_all_database_data()
        if not clear_result.success:
            return DatabaseResetResponse(
                success=False,
                message=f"清空数据失败: {clear_result.message}",
                steps_completed=["clear_data_failed"]
            )
        
        # 重新初始化数据库表结构
        try:
            await db_manager.init_database()
            logger.info("数据库表结构重新初始化完成")
        except Exception as e:
            logger.error(f"重新初始化数据库表结构失败: {e}")
            return DatabaseResetResponse(
                success=False,
                message=f"重新初始化数据库表结构失败: {str(e)}",
                steps_completed=["clear_data_success", "init_tables_failed"]
            )
        
        logger.warning("数据库重置完成")
        
        return DatabaseResetResponse(
            success=True,
            message="数据库重置成功",
            cleared_records=clear_result.total_cleared,
            steps_completed=["clear_data_success", "init_tables_success"]
        )
        
    except Exception as e:
        logger.error(f"重置数据库失败: {e}")
        return DatabaseResetResponse(
            success=False,
            message=f"重置数据库失败: {str(e)}",
            steps_completed=["failed"]
        ) 
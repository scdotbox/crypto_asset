"""
历史数据路由模块

包含历史数据缓存、查询、更新等相关API端点
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from app.models.asset_models import (
    AssetHistoryRequest,
    AssetHistoryResponse,
    HistoryQueryRequest,
    HistoryUpdateRequest,
)
from app.services.asset_history_service import AssetHistoryService
from app.services.asset_service import AssetService
from app.core.logger import get_logger

logger = get_logger(__name__)

# 创建路由器
router = APIRouter(prefix="/api", tags=["历史数据"])

# 创建服务实例
asset_history_service = AssetHistoryService()
asset_service = AssetService()


@router.post(
    "/assets/history",
    response_model=AssetHistoryResponse,
    summary="获取资产历史数据",
    description="获取资产的历史数量和价值变化数据，支持按时间范围和间隔查询",
)
async def get_asset_history(request: AssetHistoryRequest):
    """获取资产历史数据"""
    try:
        history_data = await asset_history_service.get_asset_history(request)
        return history_data
    except Exception as e:
        logger.error(f"获取资产历史数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取资产历史数据失败: {str(e)}")


@router.post(
    "/assets/save-snapshot",
    summary="保存当前资产快照",
    description="保存当前所有资产的快照数据到历史记录中",
)
async def save_asset_snapshot():
    """保存当前资产快照"""
    try:
        await asset_history_service.save_current_snapshot()
        return {
            "status": "success",
            "message": "资产快照保存成功"
        }
    except Exception as e:
        logger.error(f"保存资产快照失败: {e}")
        raise HTTPException(status_code=500, detail=f"保存资产快照失败: {str(e)}")


@router.get(
    "/history/cache/stats",
    summary="获取历史缓存统计信息",
    description="获取价格和余额历史缓存的统计信息，包括记录数量、时间范围等",
)
async def get_history_cache_stats():
    """获取历史缓存统计信息"""
    try:
        # 获取历史缓存服务
        history_cache = asset_service.price_service.history_cache
        
        if history_cache:
            stats = await history_cache.get_cache_stats()
            return {
                "status": "success",
                "data": stats
            }
        else:
            return {
                "status": "error",
                "message": "历史缓存服务不可用"
            }
            
    except Exception as e:
        logger.error(f"获取历史缓存统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取历史缓存统计失败: {str(e)}")


@router.post(
    "/history/price/query",
    summary="查询价格历史数据",
    description="根据条件查询价格历史数据，支持按时间范围、代币、链等条件筛选",
)
async def query_price_history(request: HistoryQueryRequest):
    """查询价格历史数据"""
    try:
        history_cache = asset_service.price_service.history_cache
        
        if history_cache:
            results = await history_cache.query_price_history(
                token_symbol=request.token_symbol,
                chain_name=request.chain_name,
                start_time=request.start_time,
                end_time=request.end_time,
                limit=request.limit
            )
            return {
                "status": "success",
                "data": results,
                "total_count": len(results)
            }
        else:
            return {
                "status": "error",
                "message": "历史缓存服务不可用",
                "data": []
            }
            
    except Exception as e:
        logger.error(f"查询价格历史数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询价格历史数据失败: {str(e)}")


@router.post(
    "/history/balance/query",
    summary="查询余额历史数据",
    description="根据条件查询余额历史数据，支持按时间范围、地址、代币等条件筛选",
)
async def query_balance_history(request: HistoryQueryRequest):
    """查询余额历史数据"""
    try:
        history_cache = asset_service.price_service.history_cache
        
        if history_cache:
            results = await history_cache.query_balance_history(
                address=request.address,
                token_symbol=request.token_symbol,
                chain_name=request.chain_name,
                start_time=request.start_time,
                end_time=request.end_time,
                limit=request.limit
            )
            return {
                "status": "success",
                "data": results,
                "total_count": len(results)
            }
        else:
            return {
                "status": "error",
                "message": "历史缓存服务不可用",
                "data": []
            }
            
    except Exception as e:
        logger.error(f"查询余额历史数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询余额历史数据失败: {str(e)}")


@router.post(
    "/history/update",
    summary="更新历史数据",
    description="手动触发历史数据更新，可指定更新范围和强制更新选项",
)
async def update_history_data(request: HistoryUpdateRequest):
    """更新历史数据"""
    try:
        history_cache = asset_service.price_service.history_cache
        
        if history_cache:
            # 根据请求类型更新不同的历史数据
            if request.update_type == "price":
                await history_cache.update_price_cache(
                    force_update=request.force_update
                )
                message = "价格历史数据更新完成"
            elif request.update_type == "balance":
                await history_cache.update_balance_cache(
                    force_update=request.force_update
                )
                message = "余额历史数据更新完成"
            else:
                # 更新所有数据
                await history_cache.update_price_cache(
                    force_update=request.force_update
                )
                await history_cache.update_balance_cache(
                    force_update=request.force_update
                )
                message = "所有历史数据更新完成"
            
            return {
                "status": "success",
                "message": message
            }
        else:
            return {
                "status": "error",
                "message": "历史缓存服务不可用"
            }
            
    except Exception as e:
        logger.error(f"更新历史数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"更新历史数据失败: {str(e)}")


@router.get(
    "/history/update/status",
    summary="获取历史数据更新状态",
    description="获取历史数据自动更新服务的状态信息",
)
async def get_history_update_status():
    """获取历史数据更新状态"""
    try:
        history_cache = asset_service.price_service.history_cache
        
        if history_cache:
            status = await history_cache.get_update_status()
            return {
                "status": "success",
                "data": status
            }
        else:
            return {
                "status": "error",
                "message": "历史缓存服务不可用",
                "data": {
                    "price_cache_enabled": False,
                    "balance_cache_enabled": False,
                    "last_update_time": None,
                    "update_in_progress": False
                }
            }
            
    except Exception as e:
        logger.error(f"获取历史数据更新状态失败: {e}")
        # 返回默认状态而不是抛出异常
        return {
            "status": "error",
            "message": f"获取状态失败: {str(e)}",
            "data": {
                "price_cache_enabled": False,
                "balance_cache_enabled": False,
                "last_update_time": None,
                "update_in_progress": False
            }
        }


@router.post(
    "/history/cleanup",
    summary="清理过期历史数据",
    description="清理超过保留期限的历史数据，释放存储空间",
)
async def cleanup_history_data():
    """清理过期历史数据"""
    try:
        history_cache = asset_service.price_service.history_cache
        
        if history_cache:
            # 清理过期的价格历史数据
            price_cleaned = await history_cache.cleanup_expired_price_history()
            
            # 清理过期的余额历史数据
            balance_cleaned = await history_cache.cleanup_expired_balance_history()
            
            return {
                "status": "success",
                "message": "历史数据清理完成",
                "details": {
                    "price_records_cleaned": price_cleaned,
                    "balance_records_cleaned": balance_cleaned,
                    "total_cleaned": price_cleaned + balance_cleaned
                }
            }
        else:
            return {
                "status": "error",
                "message": "历史缓存服务不可用"
            }
            
    except Exception as e:
        logger.error(f"清理历史数据失败: {e}")
        # 返回错误信息而不是抛出异常
        return {
            "status": "error",
            "message": f"清理失败: {str(e)}",
            "details": {
                "price_records_cleaned": 0,
                "balance_records_cleaned": 0,
                "total_cleaned": 0
            }
        }


@router.get(
    "/history/price/latest/{token_symbol}",
    summary="获取最新缓存价格",
    description="获取指定代币的最新缓存价格",
)
async def get_latest_cached_price(
    token_symbol: str,
    chain_name: Optional[str] = Query(None, description="区块链名称")
):
    """获取最新缓存价格"""
    try:
        history_cache = asset_service.price_service.history_cache
        
        if history_cache:
            latest_price = await history_cache.get_latest_price(token_symbol, chain_name)
            
            if latest_price is not None:
                return {
                    "status": "success",
                    "found": True,
                    "data": {
                        "token_symbol": token_symbol,
                        "chain_name": chain_name,
                        "price_usdc": latest_price
                    },
                    "message": f"找到 {token_symbol} 的最新缓存价格"
                }
            else:
                return {
                    "status": "success",
                    "found": False,
                    "data": None,
                    "message": f"未找到 {token_symbol} 的缓存价格"
                }
        else:
            return {
                "status": "error",
                "found": False,
                "data": None,
                "message": "历史缓存服务不可用"
            }
            
    except Exception as e:
        logger.error(f"获取最新缓存价格失败: {e}")
        return {
            "status": "error",
            "found": False,
            "data": None,
            "message": f"获取失败: {str(e)}"
        }


@router.get(
    "/history/balance/latest/{address}/{chain_name}/{token_symbol}",
    summary="获取最新缓存余额",
    description="获取指定地址和代币的最新缓存余额",
)
async def get_latest_cached_balance(
    address: str,
    chain_name: str,
    token_symbol: str
):
    """获取最新缓存余额"""
    try:
        history_cache = asset_service.price_service.history_cache
        
        if history_cache:
            latest_balance = await history_cache.get_latest_balance(
                address=address,
                token_symbol=token_symbol,
                chain_name=chain_name
            )
            
            if latest_balance is not None:
                return {
                    "status": "success",
                    "found": True,
                    "data": {
                        "address": address,
                        "chain_name": chain_name,
                        "token_symbol": token_symbol,
                        "balance": latest_balance
                    },
                    "message": f"找到 {address} 的 {token_symbol} 最新缓存余额"
                }
            else:
                return {
                    "status": "success",
                    "found": False,
                    "data": None,
                    "message": f"未找到 {address} 的 {token_symbol} 缓存余额"
                }
        else:
            return {
                "status": "error",
                "found": False,
                "data": None,
                "message": "历史缓存服务不可用"
            }
            
    except Exception as e:
        logger.error(f"获取最新缓存余额失败: {e}")
        return {
            "status": "error",
            "found": False,
            "data": None,
            "message": f"获取失败: {str(e)}"
        } 
"""
价格服务路由模块

包含价格服务统计、缓存管理等相关API端点
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from app.services.asset_service import AssetService
from app.core.logger import get_logger

logger = get_logger(__name__)

# 创建路由器
router = APIRouter(prefix="/api", tags=["价格服务"])

# 创建服务实例
asset_service = AssetService()


@router.get(
    "/price-service/stats",
    summary="获取价格服务统计信息",
    description="获取价格服务的缓存统计和API调用统计信息",
)
async def get_price_service_stats():
    """获取价格服务统计信息"""
    try:
        cache_stats = asset_service.price_service.get_cache_stats()
        return {
            "status": "success",
            "data": {
                "cache_stats": cache_stats,
                "request_stats": asset_service.price_service.request_stats,
                "error_stats": asset_service.price_service.error_stats
            }
        }
    except Exception as e:
        logger.error(f"获取价格服务统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取价格服务统计失败: {str(e)}")


@router.post(
    "/price-service/clear-cache",
    summary="清空价格缓存",
    description="清空所有价格缓存数据，包括内存缓存、代币列表缓存和合约缓存",
)
async def clear_price_cache():
    """清空价格缓存"""
    try:
        asset_service.price_service.clear_all_cache()
        return {
            "status": "success",
            "message": "所有价格缓存已清空，包括内存缓存、代币列表缓存和合约缓存"
        }
    except Exception as e:
        logger.error(f"清空价格缓存失败: {e}")
        raise HTTPException(status_code=500, detail=f"清空价格缓存失败: {str(e)}")


@router.post(
    "/price-service/clear-expired-cache",
    summary="清理过期缓存",
    description="清理所有过期的价格缓存数据",
)
async def clear_expired_price_cache():
    """清理过期缓存"""
    try:
        asset_service.price_service.clear_expired_cache()
        return {
            "status": "success",
            "message": "过期缓存已清理"
        }
    except Exception as e:
        logger.error(f"清理过期缓存失败: {e}")
        raise HTTPException(status_code=500, detail=f"清理过期缓存失败: {str(e)}")


@router.get("/price-service/health")
async def check_price_service_health():
    """检查价格服务健康状态"""
    try:
        # 测试价格服务是否正常工作
        test_result = await asset_service.price_service.get_token_price_usdc("bitcoin")
        
        if test_result and test_result > 0:
            return {
                "status": "healthy",
                "message": "价格服务正常运行",
                "test_token": "bitcoin",
                "test_price": test_result
            }
        else:
            return {
                "status": "degraded",
                "message": "价格服务可能存在问题",
                "test_result": test_result
            }
            
    except Exception as e:
        logger.error(f"价格服务健康检查失败: {e}")
        return {
            "status": "unhealthy",
            "message": f"价格服务健康检查失败: {str(e)}"
        }


@router.get(
    "/tokens/coingecko/list",
    summary="获取 CoinGecko 所有代币列表",
    description="获取 CoinGecko 上所有代币的列表，包含 ID、符号和名称信息",
)
async def get_coingecko_coins_list(
    force_refresh: bool = Query(False, description="是否强制刷新缓存"),
    limit: Optional[int] = Query(None, description="返回结果数量限制", ge=1, le=10000),
):
    """获取 CoinGecko 所有代币列表"""
    try:
        coins_list = await asset_service.price_service.get_all_coins_list(
            force_refresh=force_refresh
        )
        
        # 如果设置了限制，截取结果
        if limit and len(coins_list) > limit:
            coins_list = coins_list[:limit]
        
        return {
            "status": "success",
            "data": coins_list,
            "total_count": len(coins_list),
            "cached": not force_refresh
        }
        
    except Exception as e:
        logger.error(f"获取 CoinGecko 代币列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取代币列表失败: {str(e)}")


@router.get(
    "/tokens/contract/{chain_name}/{contract_address}",
    summary="通过合约地址查询代币信息",
    description="使用合约地址从 CoinGecko 查询代币的详细信息，包括 ID、符号、名称等",
)
async def get_token_by_contract(chain_name: str, contract_address: str):
    """通过合约地址查询代币信息"""
    try:
        # 获取代币信息
        token_info = await asset_service.price_service.get_token_info_by_contract(
            chain_name=chain_name,
            contract_address=contract_address
        )
        
        if token_info:
            return {
                "status": "success",
                "found": True,
                "data": token_info,
                "message": f"找到代币: {token_info.get('symbol', 'Unknown')}"
            }
        else:
            return {
                "status": "success",
                "found": False,
                "data": None,
                "message": f"未找到合约地址 {contract_address} 对应的代币信息"
            }
            
    except Exception as e:
        logger.error(f"通过合约地址查询代币信息失败: {e}")
        # 不抛出异常，返回错误信息但保持200状态码
        return {
            "status": "error",
            "found": False,
            "data": None,
            "message": f"查询失败: {str(e)}"
        }


@router.get(
    "/tokens/validation/contract",
    summary="验证合约地址并获取代币信息",
    description="验证合约地址是否有效，并尝试获取代币信息，用于添加资产时的验证",
)
async def validate_contract_address(
    contract_address: str = Query(..., description="合约地址"),
    chain_name: str = Query(..., description="区块链名称"),
):
    """验证合约地址并获取代币信息"""
    try:
        # 验证地址格式
        if not contract_address or len(contract_address) < 10:
            return {
                "valid": False,
                "token_info": None,
                "message": "合约地址格式无效"
            }
        
        # 根据链类型验证地址格式
        chain_name_lower = chain_name.lower()
        
        if chain_name_lower == "sui":
            # Sui支持两种格式：
            # 1. 标准地址格式: 0x + 64个十六进制字符
            # 2. Coin type格式: 0x + 64个十六进制字符 + :: + module + :: + type
            import re
            
            # 标准地址格式
            standard_pattern = r'^0x[a-fA-F0-9]{64}$'
            # Coin type格式
            coin_type_pattern = r'^0x[a-fA-F0-9]{64}::[a-zA-Z0-9_]+::[a-zA-Z0-9_]+$'
            
            if not (re.match(standard_pattern, contract_address) or re.match(coin_type_pattern, contract_address)):
                return {
                    "valid": False,
                    "token_info": None,
                    "message": "无效的Sui地址格式。支持标准地址(0x+64字符)或coin type格式(0x+64字符::module::type)"
                }
        
        elif chain_name_lower in ["ethereum", "arbitrum", "base", "polygon", "bsc"]:
            # EVM链地址格式验证
            import re
            if not re.match(r'^0x[a-fA-F0-9]{40}$', contract_address):
                return {
                    "valid": False,
                    "token_info": None,
                    "message": f"无效的{chain_name}合约地址格式"
                }
        
        elif chain_name_lower == "solana":
            # Solana地址格式验证 (Base58, 32-44字符)
            if not (32 <= len(contract_address) <= 44):
                return {
                    "valid": False,
                    "token_info": None,
                    "message": "无效的Solana代币地址格式"
                }
            # 简化的Base58检查
            base58_chars = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
            if not all(c in base58_chars for c in contract_address):
                return {
                    "valid": False,
                    "token_info": None,
                    "message": "无效的Solana代币地址格式"
                }
        
        # 尝试获取代币信息
        token_info = await asset_service.price_service.get_token_info_by_contract(
            chain_name=chain_name,
            contract_address=contract_address
        )
        
        if token_info:
            return {
                "valid": True,
                "token_info": token_info,
                "message": f"合约地址有效，代币: {token_info.get('symbol', 'Unknown')}"
            }
        else:
            # 地址格式正确，但找不到代币信息
            return {
                "valid": True,  # 格式验证通过
                "token_info": None,
                "message": "合约地址格式正确，但未找到对应的代币信息。您仍可以手动添加此代币。"
            }
            
    except Exception as e:
        logger.error(f"验证合约地址失败: {e}")
        return {
            "valid": False,
            "token_info": None,
            "message": f"验证失败: {str(e)}"
        } 
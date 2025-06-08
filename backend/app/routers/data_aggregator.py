"""
数据聚合层API路由

提供数据提供商状态查询、代币发现、手动添加代币、缓存管理等功能
"""

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from typing import List, Optional 
from pydantic import BaseModel, Field

from app.core.logger import get_logger
from app.services.data_aggregator import data_aggregator
from app.services.token_discovery_service import token_discovery_service
from app.models.asset_models import (
    DiscoveredToken,
    WalletDiscoveryResponse
)

logger = get_logger(__name__)

# 创建路由器
router = APIRouter(prefix="/api/aggregator", tags=["数据聚合层"])


class ProviderStatusResponse(BaseModel):
    """数据提供商状态响应模型"""
    success: bool = Field(..., description="查询是否成功")
    providers: dict = Field(..., description="提供商状态信息")
    message: str = Field(..., description="响应消息")


class TokenDiscoveryRequest(BaseModel):
    """代币发现请求模型"""
    address: str = Field(..., description="钱包地址")
    chain_name: str = Field(..., description="区块链名称")
    include_zero_balance: bool = Field(False, description="是否包含零余额代币")
    min_value_usdc: float = Field(0.01, description="最小价值阈值（USDC）")
    use_cache: bool = Field(True, description="是否使用缓存")
    force_refresh: bool = Field(False, description="是否强制刷新")


class BatchTokenDiscoveryRequest(BaseModel):
    """批量代币发现请求模型"""
    addresses: List[str] = Field(..., description="钱包地址列表")
    chain_name: str = Field(..., description="区块链名称")
    include_zero_balance: bool = Field(False, description="是否包含零余额代币")
    min_value_usdc: float = Field(0.01, description="最小价值阈值（USDC）")
    max_concurrent: int = Field(5, description="最大并发数")


class BatchTokenDiscoveryResponse(BaseModel):
    """批量代币发现响应模型"""
    success: bool = Field(..., description="发现是否成功")
    results: dict = Field(..., description="地址到代币列表的映射")
    total_addresses: int = Field(..., description="处理的地址总数")
    total_tokens_found: int = Field(..., description="发现的代币总数")
    processing_time_seconds: float = Field(..., description="处理耗时（秒）")
    message: str = Field(..., description="响应消息")


class ManualTokenRequest(BaseModel):
    """手动添加代币请求模型"""
    address: str = Field(..., description="钱包地址")
    chain_name: str = Field(..., description="区块链名称")
    token_contract: Optional[str] = Field(None, description="代币合约地址")
    token_symbol: str = Field(..., description="代币符号")


class ManualTokenResponse(BaseModel):
    """手动添加代币响应模型"""
    success: bool = Field(..., description="添加是否成功")
    token: Optional[DiscoveredToken] = Field(None, description="发现的代币信息")
    message: str = Field(..., description="响应消息")


class CacheStatsResponse(BaseModel):
    """缓存统计响应模型"""
    success: bool = Field(..., description="查询是否成功")
    aggregator_cache: dict = Field(..., description="聚合器缓存统计")
    discovery_cache: dict = Field(..., description="发现服务缓存统计")
    message: str = Field(..., description="响应消息")


class HealthCheckResponse(BaseModel):
    """健康检查响应模型"""
    success: bool = Field(..., description="服务是否健康")
    status: str = Field(..., description="服务状态")
    providers_status: dict = Field(..., description="提供商状态摘要")
    cache_status: dict = Field(..., description="缓存状态摘要")
    timestamp: str = Field(..., description="检查时间")
    message: str = Field(..., description="响应消息")


@router.get("/providers/status", response_model=ProviderStatusResponse)
async def get_provider_status():
    """获取所有数据提供商的状态"""
    try:
        status = data_aggregator.get_provider_status()
        
        return ProviderStatusResponse(
            success=True,
            providers=status,
            message="数据提供商状态获取成功"
        )
        
    except Exception as e:
        logger.error(f"获取数据提供商状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取数据提供商状态失败: {str(e)}")


@router.post("/discover/tokens", response_model=WalletDiscoveryResponse)
async def discover_wallet_tokens(request: TokenDiscoveryRequest):
    """发现钱包中的代币"""
    try:
        logger.info(f"开始发现代币: {request.address} on {request.chain_name}")
        
        discovered_tokens = await token_discovery_service.discover_wallet_tokens(
            address=request.address,
            chain_name=request.chain_name,
            include_zero_balance=request.include_zero_balance,
            min_value_usdc=request.min_value_usdc,
            use_cache=request.use_cache,
            force_refresh=request.force_refresh
        )
        
        # 计算总价值
        total_value_usdc = sum(
            token.value_usdc for token in discovered_tokens 
            if token.value_usdc is not None
        )
        
        return WalletDiscoveryResponse(
            success=True,
            address=request.address,
            chain_name=request.chain_name,
            discovered_tokens=discovered_tokens,
            total_count=len(discovered_tokens),
            total_value_usdc=total_value_usdc,
            message=f"成功发现 {len(discovered_tokens)} 个代币"
        )
        
    except Exception as e:
        logger.error(f"代币发现失败: {e}")
        return WalletDiscoveryResponse(
            success=False,
            address=request.address,
            chain_name=request.chain_name,
            discovered_tokens=[],
            total_count=0,
            total_value_usdc=0.0,
            message=f"代币发现失败: {str(e)}"
        )


@router.post("/discover/tokens/batch", response_model=BatchTokenDiscoveryResponse)
async def batch_discover_tokens(request: BatchTokenDiscoveryRequest):
    """批量发现多个地址的代币"""
    import time
    start_time = time.time()
    
    try:
        logger.info(f"开始批量发现代币: {len(request.addresses)} 个地址 on {request.chain_name}")
        
        results = await token_discovery_service.batch_discover_tokens(
            addresses=request.addresses,
            chain_name=request.chain_name,
            include_zero_balance=request.include_zero_balance,
            min_value_usdc=request.min_value_usdc,
            max_concurrent=request.max_concurrent
        )
        
        # 计算统计信息
        total_tokens_found = sum(len(tokens) for tokens in results.values())
        processing_time = time.time() - start_time
        
        return BatchTokenDiscoveryResponse(
            success=True,
            results=results,
            total_addresses=len(request.addresses),
            total_tokens_found=total_tokens_found,
            processing_time_seconds=round(processing_time, 2),
            message=f"成功处理 {len(request.addresses)} 个地址，发现 {total_tokens_found} 个代币"
        )
        
    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"批量代币发现失败: {e}")
        return BatchTokenDiscoveryResponse(
            success=False,
            results={},
            total_addresses=len(request.addresses),
            total_tokens_found=0,
            processing_time_seconds=round(processing_time, 2),
            message=f"批量代币发现失败: {str(e)}"
        )


@router.post("/tokens/manual-add", response_model=ManualTokenResponse)
async def add_manual_token(request: ManualTokenRequest):
    """手动添加代币"""
    try:
        logger.info(f"手动添加代币: {request.token_symbol} for {request.address} on {request.chain_name}")
        
        token = await token_discovery_service.add_manual_token(
            address=request.address,
            chain_name=request.chain_name,
            token_contract=request.token_contract,
            token_symbol=request.token_symbol
        )
        
        if token:
            return ManualTokenResponse(
                success=True,
                token=token,
                message=f"成功添加代币 {request.token_symbol}"
            )
        else:
            return ManualTokenResponse(
                success=False,
                token=None,
                message=f"代币 {request.token_symbol} 余额为0或添加失败"
            )
            
    except Exception as e:
        logger.error(f"手动添加代币失败: {e}")
        return ManualTokenResponse(
            success=False,
            token=None,
            message=f"手动添加代币失败: {str(e)}"
        )


@router.get("/cache/stats", response_model=CacheStatsResponse)
async def get_cache_stats():
    """获取缓存统计信息"""
    try:
        aggregator_stats = data_aggregator.get_cache_stats()
        discovery_stats = token_discovery_service.get_cache_stats()
        
        return CacheStatsResponse(
            success=True,
            aggregator_cache=aggregator_stats,
            discovery_cache=discovery_stats,
            message="缓存统计信息获取成功"
        )
        
    except Exception as e:
        logger.error(f"获取缓存统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取缓存统计失败: {str(e)}")


@router.post("/cache/clear")
async def clear_cache(
    cache_type: str = Query("all", description="缓存类型: all, aggregator, discovery")
):
    """清空缓存"""
    try:
        if cache_type == "all":
            data_aggregator.clear_cache()
            token_discovery_service.clear_cache()
            message = "所有缓存已清空"
        elif cache_type == "aggregator":
            data_aggregator.clear_cache()
            message = "数据聚合器缓存已清空"
        elif cache_type == "discovery":
            token_discovery_service.clear_cache()
            message = "代币发现服务缓存已清空"
        else:
            raise HTTPException(status_code=400, detail="无效的缓存类型")
        
        return {"success": True, "message": message}
        
    except Exception as e:
        logger.error(f"清空缓存失败: {e}")
        raise HTTPException(status_code=500, detail=f"清空缓存失败: {str(e)}")


@router.post("/cache/clear-expired")
async def clear_expired_cache():
    """清理过期缓存"""
    try:
        token_discovery_service.clear_expired_cache()
        
        return {
            "success": True,
            "message": "过期缓存已清理"
        }
        
    except Exception as e:
        logger.error(f"清理过期缓存失败: {e}")
        raise HTTPException(status_code=500, detail=f"清理过期缓存失败: {str(e)}")


@router.get("/tokens/balance")
async def get_token_balance(
    address: str = Query(..., description="钱包地址"),
    chain_name: str = Query(..., description="区块链名称"),
    token_contract: Optional[str] = Query(None, description="代币合约地址，原生代币可为空")
):
    """获取代币余额"""
    try:
        balance = await data_aggregator.get_token_balance(address, token_contract, chain_name)
        
        return {
            "success": True,
            "address": address,
            "chain_name": chain_name,
            "token_contract": token_contract,
            "balance": balance,
            "message": "代币余额获取成功"
        }
        
    except Exception as e:
        logger.error(f"获取代币余额失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取代币余额失败: {str(e)}")


@router.get("/tokens/price")
async def get_token_price(
    token_symbol: str = Query(..., description="代币符号"),
    chain_name: str = Query(..., description="区块链名称")
):
    """获取代币价格"""
    try:
        price = await data_aggregator.get_token_price(token_symbol, chain_name)
        
        return {
            "success": True,
            "token_symbol": token_symbol,
            "chain_name": chain_name,
            "price_usdc": price,
            "message": "代币价格获取成功" if price is not None else "未找到代币价格"
        }
        
    except Exception as e:
        logger.error(f"获取代币价格失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取代币价格失败: {str(e)}")


@router.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """健康检查"""
    try:
        from datetime import datetime
        
        # 获取提供商状态
        provider_status = data_aggregator.get_provider_status()
        healthy_providers = provider_status.get("healthy_providers", 0)
        total_providers = provider_status.get("total_providers", 0)
        
        # 获取缓存状态
        aggregator_cache = data_aggregator.get_cache_stats()
        discovery_cache = token_discovery_service.get_cache_stats()
        
        # 判断服务状态
        is_healthy = healthy_providers > 0
        status = "healthy" if is_healthy else "unhealthy"
        
        return HealthCheckResponse(
            success=is_healthy,
            status=status,
            providers_status={
                "healthy_providers": healthy_providers,
                "total_providers": total_providers,
                "health_ratio": healthy_providers / total_providers if total_providers > 0 else 0
            },
            cache_status={
                "aggregator_cache_entries": aggregator_cache.get("total_cache_entries", 0),
                "discovery_cache_entries": discovery_cache.get("total_cache_entries", 0),
                "total_cache_entries": (
                    aggregator_cache.get("total_cache_entries", 0) + 
                    discovery_cache.get("total_cache_entries", 0)
                )
            },
            timestamp=datetime.now().isoformat(),
            message=f"数据聚合层服务状态: {status}"
        )
        
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        raise HTTPException(status_code=500, detail=f"健康检查失败: {str(e)}")


@router.get("/supported-chains")
async def get_supported_chains():
    """获取支持的区块链列表"""
    try:
        provider_status = data_aggregator.get_provider_status()
        
        # 统计所有提供商支持的链
        all_chains = set()
        chain_providers = {}
        
        for provider in provider_status.get("providers", []):
            for chain in provider.get("supported_chains", []):
                all_chains.add(chain)
                if chain not in chain_providers:
                    chain_providers[chain] = []
                chain_providers[chain].append({
                    "name": provider["name"],
                    "type": provider["type"],
                    "is_healthy": provider["is_healthy"]
                })
        
        return {
            "success": True,
            "supported_chains": sorted(list(all_chains)),
            "chain_providers": chain_providers,
            "total_chains": len(all_chains),
            "message": "支持的区块链列表获取成功"
        }
        
    except Exception as e:
        logger.error(f"获取支持的区块链列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取支持的区块链列表失败: {str(e)}")


@router.post("/providers/reset-errors")
async def reset_provider_errors(
    provider_name: Optional[str] = Query(None, description="提供商名称，为空则重置所有提供商")
):
    """重置提供商错误计数"""
    try:
        reset_count = 0
        
        for provider in data_aggregator.providers:
            if provider_name is None or provider.name == provider_name:
                provider.reset_errors()
                reset_count += 1
        
        if reset_count == 0:
            return {
                "success": False,
                "message": f"未找到提供商: {provider_name}"
            }
        
        return {
            "success": True,
            "reset_count": reset_count,
            "message": f"已重置 {reset_count} 个提供商的错误计数"
        }
        
    except Exception as e:
        logger.error(f"重置提供商错误计数失败: {e}")
        raise HTTPException(status_code=500, detail=f"重置提供商错误计数失败: {str(e)}")


@router.post("/maintenance/optimize-cache")
async def optimize_cache(background_tasks: BackgroundTasks):
    """优化缓存（后台任务）"""
    def _optimize_cache():
        try:
            # 清理过期缓存
            token_discovery_service.clear_expired_cache()
            logger.info("缓存优化完成")
        except Exception as e:
            logger.error(f"缓存优化失败: {e}")
    
    background_tasks.add_task(_optimize_cache)
    
    return {
        "success": True,
        "message": "缓存优化任务已启动"
    } 
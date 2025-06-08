"""
区块链服务路由模块

包含区块链连接、钱包管理等相关API端点
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query

from app.models.asset_models import (
    WalletCreationResponse,
    WalletDiscoveryRequest,
    WalletDiscoveryResponse,
    WalletData,
    BlockchainData,
)
from app.services.blockchain_service import BlockchainService
from app.core.config import SUPPORTED_CHAINS
from app.core.logger import get_logger

logger = get_logger(__name__)

# 创建路由器
router = APIRouter(prefix="/api", tags=["区块链服务"])

# 创建服务实例
blockchain_service = BlockchainService()


@router.get(
    "/chains",
    summary="获取支持的区块链列表",
    description="获取系统支持的所有区块链信息",
)
async def get_supported_chains():
    """获取支持的区块链列表"""
    try:
        chains = []
        for chain_name, chain_config in SUPPORTED_CHAINS.items():
            # 从预定义代币库获取原生代币信息
            from app.core.config import get_native_token_symbol
            native_token_symbol = get_native_token_symbol(chain_name)
            
            chains.append({
                "name": chain_name,
                "display_name": chain_config.get("display_name", chain_name.title()),
                "native_token": native_token_symbol,
                "explorer_url": chain_config.get("explorer_url"),
                "chain_type": chain_config.get("chain_type", "evm")
            })
        
        return {"chains": chains}
    except Exception as e:
        logger.error(f"获取支持的区块链列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取区块链列表失败: {str(e)}")


@router.get(
    "/wallets/{address}/creation-time",
    response_model=WalletCreationResponse,
    summary="查询钱包创建时间",
    description="查询指定钱包地址在指定区块链上的创建时间",
)
async def get_wallet_creation_time(
    address: str, chain_name: str = Query(..., description="区块链名称")
):
    """查询钱包创建时间"""
    try:
        # 确保区块链服务已初始化
        await blockchain_service.ensure_initialized()
        
        # 获取钱包创建时间
        creation_info = await blockchain_service.get_wallet_creation_time(
            address, chain_name
        )
        
        return WalletCreationResponse(
            success=True,
            data=creation_info,
            message="钱包创建时间查询成功"
        )
        
    except Exception as e:
        logger.error(f"查询钱包创建时间失败: {e}")
        return WalletCreationResponse(
            success=False,
            data=None,
            message=f"查询失败: {str(e)}"
        )


@router.post(
    "/wallets/discover-tokens",
    response_model=WalletDiscoveryResponse,
    summary="发现钱包代币",
    description="自动发现指定钱包地址中有余额的代币，支持设置最小价值阈值过滤",
)
async def discover_wallet_tokens(request: WalletDiscoveryRequest):
    """发现钱包代币"""
    try:
        # 确保区块链服务已初始化
        await blockchain_service.ensure_initialized()
        
        # 发现代币
        discovered_tokens = await blockchain_service.discover_wallet_tokens(
            address=request.address,
            chain_name=request.chain_name,
            include_zero_balance=request.include_zero_balance,
            min_value_usdc=request.min_value_usdc
        )
        
        # 计算总价值
        total_value = sum(token.value_usdc or 0.0 for token in discovered_tokens)
        
        return WalletDiscoveryResponse(
            success=True,
            address=request.address,
            chain_name=request.chain_name,
            discovered_tokens=discovered_tokens,
            total_count=len(discovered_tokens),
            total_value_usdc=total_value,
            message=f"发现 {len(discovered_tokens)} 个代币"
        )
        
    except Exception as e:
        logger.error(f"发现钱包代币失败: {e}")
        return WalletDiscoveryResponse(
            success=False,
            address=request.address,
            chain_name=request.chain_name,
            discovered_tokens=[],
            total_count=0,
            total_value_usdc=0.0,
            message=f"发现失败: {str(e)}"
        )


@router.get(
    "/blockchain/discover-tokens/{chain_name}/{address}",
    response_model=WalletDiscoveryResponse,
    summary="发现钱包代币 (GET)",
    description="通过GET方式自动发现指定钱包地址中有余额的代币，使用默认的最小价值阈值过滤",
)
async def discover_wallet_tokens_get(
    address: str, 
    chain_name: str,
    include_zero_balance: bool = Query(False, description="是否包含零余额代币"),
    min_value_usdc: float = Query(0.00001, description="最小价值阈值（USDC）")
):
    """通过GET方式发现钱包代币"""
    try:
        # 确保区块链服务已初始化
        await blockchain_service.ensure_initialized()
        
        # 发现代币
        discovered_tokens = await blockchain_service.discover_wallet_tokens(
            address=address,
            chain_name=chain_name,
            include_zero_balance=include_zero_balance,
            min_value_usdc=min_value_usdc
        )
        
        # 计算总价值
        total_value = sum(token.value_usdc or 0.0 for token in discovered_tokens)
        
        return WalletDiscoveryResponse(
            success=True,
            address=address,
            chain_name=chain_name,
            discovered_tokens=discovered_tokens,
            total_count=len(discovered_tokens),
            total_value_usdc=total_value,
            message=f"发现 {len(discovered_tokens)} 个代币"
        )
        
    except Exception as e:
        logger.error(f"发现钱包代币失败: {e}")
        return WalletDiscoveryResponse(
            success=False,
            address=address,
            chain_name=chain_name,
            discovered_tokens=[],
            total_count=0,
            total_value_usdc=0.0,
            message=f"发现失败: {str(e)}"
        )


@router.get("/blockchain/health")
async def check_blockchain_health():
    """检查区块链服务健康状态"""
    try:
        connection_status = blockchain_service.get_connection_status()
        
        healthy_chains = 0
        total_chains = len(SUPPORTED_CHAINS)
        
        for chain_name, status in connection_status.items():
            if status.get("status") == "connected":
                healthy_chains += 1
        
        # 如果超过50%的链连接正常，则认为服务健康
        is_healthy = healthy_chains / total_chains >= 0.5 if total_chains > 0 else False
        
        return {
            "status": "healthy" if is_healthy else "degraded",
            "healthy_chains": healthy_chains,
            "total_chains": total_chains,
            "connection_details": connection_status,
            "message": f"{healthy_chains}/{total_chains} 链连接正常"
        }
        
    except Exception as e:
        logger.error(f"检查区块链健康状态失败: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "message": "无法检查区块链服务状态"
        }


@router.post("/blockchain/reconnect")
async def reconnect_blockchain(
    chain_name: Optional[str] = Query(None, description="指定要重连的链名称，为空则重连所有链")
):
    """重新连接区块链"""
    try:
        if chain_name:
            # 重连指定链
            success = await blockchain_service.reconnect_chain(chain_name)
            if success is None:
                return {
                    "success": True,
                    "message": f"{chain_name} 是非EVM链，无需重连",
                    "chain_name": chain_name
                }
            elif success:
                return {
                    "success": True,
                    "message": f"{chain_name} 重连成功",
                    "chain_name": chain_name
                }
            else:
                return {
                    "success": False,
                    "message": f"{chain_name} 重连失败",
                    "chain_name": chain_name
                }
        else:
            # 重连所有链
            results = await blockchain_service.reconnect_all_chains()
            
            successful_chains = []
            failed_chains = []
            skipped_chains = []
            
            for chain, result in results.items():
                if result is None:
                    skipped_chains.append(chain)
                elif result:
                    successful_chains.append(chain)
                else:
                    failed_chains.append(chain)
            
            return {
                "success": len(failed_chains) == 0,
                "successful_chains": successful_chains,
                "failed_chains": failed_chains,
                "skipped_chains": skipped_chains,
                "message": f"重连完成: {len(successful_chains)} 成功, {len(failed_chains)} 失败, {len(skipped_chains)} 跳过"
            }
            
    except Exception as e:
        logger.error(f"重连区块链失败: {e}")
        raise HTTPException(status_code=500, detail=f"重连失败: {str(e)}")


@router.get("/blockchain/status")
async def get_blockchain_status():
    """获取区块链连接状态"""
    try:
        connection_status = blockchain_service.get_connection_status()
        
        # 统计连接状态
        status_summary = {
            "connected": 0,
            "failed": 0,
            "skipped": 0
        }
        
        for status in connection_status.values():
            status_type = status.get("status", "unknown")
            if status_type in status_summary:
                status_summary[status_type] += 1
        
        return {
            "summary": status_summary,
            "details": connection_status,
            "timestamp": "now"
        }
        
    except Exception as e:
        logger.error(f"获取区块链状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取状态失败: {str(e)}")


@router.get("/blockchains", response_model=List[BlockchainData])
async def list_blockchains():
    """获取区块链列表"""
    try:
        blockchains = []
        for chain_name, chain_config in SUPPORTED_CHAINS.items():
            blockchains.append(BlockchainData(
                id=hash(chain_name) % 1000000,  # 简单的ID生成
                name=chain_name,
                display_name=chain_config.get("display_name", chain_name.title()),
                rpc_url=chain_config.get("rpc_url", ""),
                explorer_url=chain_config.get("explorer_url"),
                chain_type=chain_config.get("chain_type", "evm"),
                is_active=True,
                created_at=None
            ))
        
        return blockchains
        
    except Exception as e:
        logger.error(f"获取区块链列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取区块链列表失败: {str(e)}")


@router.get("/wallets", response_model=List[WalletData])
async def list_wallets(chain_name: Optional[str] = None):
    """获取钱包列表"""
    try:
        # 这里应该从数据库获取钱包信息
        # 暂时返回空列表，需要实现钱包数据库表
        return []
        
    except Exception as e:
        logger.error(f"获取钱包列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取钱包列表失败: {str(e)}") 
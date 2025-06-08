"""
资产管理路由模块

包含资产的增删改查等相关API端点
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
import time

from app.models.asset_models import (
    AssetInput,
    AssetResponse,
    AssetData,
    EnhancedAssetResponse,
    AssetDisplay,
    AssetUpdateInput,
    QuickAddTokenRequest,
    BatchAddTokensRequest,
    BatchAddTokensResponse,
)
from app.services.asset_service import AssetService
from app.services.db_asset_service import DatabaseAssetService
from app.core.logger import get_logger
from app.core.database import db_manager
from app.services.price_service import PriceService

logger = get_logger(__name__)

# 创建路由器
router = APIRouter(prefix="/api", tags=["资产管理"])

# 创建服务实例
asset_service = AssetService()


@router.post(
    "/assets",
    response_model=EnhancedAssetResponse,
    status_code=201,
    summary="添加新资产",
            description="添加一个新的加密货币资产以供管理，如果资产已存在则返回现有资产信息",
)
async def add_asset(asset_input: AssetInput):
    """添加新资产（使用数据库）"""
    try:
        # 使用数据库版本的资产服务
        db_asset_service = DatabaseAssetService()
        
        # 先检查资产是否已存在
        existing_assets = await db_asset_service.get_detailed_assets(
            chain_name=asset_input.chain_name, address=asset_input.address
        )

        # 检查是否有相同的代币符号和合约地址
        for existing in existing_assets:
            if (
                existing.token_symbol.upper() == asset_input.token_symbol.upper()
                and existing.token_contract_address == asset_input.token_contract_address
            ):
                # 转换为 AssetData 格式
                existing_asset_data = AssetData(
                    id=existing.id,
                    address=existing.address,
                    chain_name=existing.chain_name,
                    token_symbol=existing.token_symbol,
                    token_contract_address=existing.token_contract_address,
                    wallet_name=existing.wallet_name,
                    notes=existing.notes,
                    tag=existing.tag,
                    created_at="",  # 从数据库获取实际的创建时间
                )

                return EnhancedAssetResponse(
                    message="资产已存在",
                    asset=existing_asset_data,
                    status="existing",
                    is_duplicate=True,
                )

        # 创建新资产
        asset_data = await db_asset_service.add_asset(asset_input)
        
        return EnhancedAssetResponse(
            message="资产添加成功",
            asset=asset_data,
            status="created",
            is_duplicate=False,
        )

    except Exception as e:
        logger.error(f"添加资产失败: {e}")
        raise HTTPException(status_code=500, detail=f"添加资产失败: {str(e)}")


@router.post(
    "/assets/quick-add",
    response_model=AssetResponse,
    status_code=201,
    summary="快速添加资产",
    description="使用代币库中的信息快速添加资产，自动填充合约地址等信息",
)
async def quick_add_asset(request: QuickAddTokenRequest):
    """快速添加资产"""
    try:
        # 直接使用数据库服务添加资产
        db_asset_service = DatabaseAssetService()
        
        # 构建完整的资产输入数据
        asset_input = AssetInput(
            address=request.address,
            chain_name=request.chain_name,
            token_symbol=request.token_symbol,
            token_contract_address=None,  # 通过代币库自动查找
            wallet_name=None,
            notes=None,
            tag=request.tag
        )
        
        result = await db_asset_service.add_asset(asset_input)
        
        return AssetResponse(
            message="资产添加成功",
            asset=result
        )
        
    except Exception as e:
        logger.error(f"快速添加资产失败: {e}")
        raise HTTPException(status_code=500, detail=f"快速添加资产失败: {str(e)}")


@router.get(
    "/assets",
    response_model=List[AssetDisplay],
    summary="获取资产列表",
            description="检索所有已管理资产的当前数量和价值（从数据库）",
)
async def get_assets(
    chain_name: Optional[str] = Query(None, description="按链名称筛选"),
    address: Optional[str] = Query(None, description="按地址筛选"),
    tag: Optional[str] = Query(None, description="按标签筛选"),
):
    """获取资产列表"""
    try:
        filters = {}
        if chain_name:
            filters["chain_name"] = chain_name
        if address:
            filters["address"] = address
        if tag:
            filters["tag"] = tag

        return await asset_service.get_detailed_assets(
            chain_name=filters.get("chain_name"),
            address=filters.get("address"),
            tag=filters.get("tag")
        )

    except Exception as e:
        logger.error(f"获取资产列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取资产列表失败: {str(e)}")


@router.post(
    "/assets/check",
    summary="检查资产是否存在",
            description="检查指定的资产是否已经被管理",
)
async def check_asset_exists(asset_input: AssetInput):
    """检查资产是否存在"""
    try:
        async with db_manager.get_connection() as conn:
            # 获取区块链ID
            async with conn.execute(
                "SELECT id FROM blockchains WHERE name = ?", (asset_input.chain_name,)
            ) as cursor:
                blockchain_row = await cursor.fetchone()
                if not blockchain_row:
                    return {
                        "exists": False,
                        "message": f"不支持的区块链: {asset_input.chain_name}",
                    }
                blockchain_id = blockchain_row["id"]

            # 查找钱包
            async with conn.execute(
                "SELECT id FROM wallets WHERE address = ? AND blockchain_id = ?",
                (asset_input.address, blockchain_id),
            ) as cursor:
                wallet_row = await cursor.fetchone()
                if not wallet_row:
                    return {
                        "exists": False,
                        "message": "钱包不存在",
                    }
                wallet_id = wallet_row["id"]

            # 查找代币
            if asset_input.token_contract_address:
                token_query = """
                    SELECT id FROM tokens 
                    WHERE symbol = ? AND blockchain_id = ? AND contract_address = ? AND is_active = 1
                """
                token_params = (asset_input.token_symbol.upper(), blockchain_id, asset_input.token_contract_address)
            else:
                token_query = """
                    SELECT id FROM tokens 
                    WHERE symbol = ? AND blockchain_id = ? AND contract_address IS NULL AND is_active = 1
                """
                token_params = (asset_input.token_symbol.upper(), blockchain_id)

            async with conn.execute(token_query, token_params) as cursor:
                token_row = await cursor.fetchone()
                if not token_row:
                    return {
                        "exists": False,
                        "message": "代币不存在",
                    }
                token_id = token_row["id"]

            # 检查资产是否存在
            async with conn.execute(
                """
                SELECT a.id, a.tag, a.created_at,
                       w.address, w.wallet_name, w.notes,
                       t.symbol, t.contract_address,
                       b.name as chain_name
                FROM assets a
                JOIN wallets w ON a.wallet_id = w.id
                JOIN tokens t ON a.token_id = t.id
                JOIN blockchains b ON w.blockchain_id = b.id
                WHERE a.wallet_id = ? AND a.token_id = ? AND a.is_active = 1
                """,
                (wallet_id, token_id),
            ) as cursor:
                existing_asset = await cursor.fetchone()
                if existing_asset:
                    return {
                        "exists": True,
                        "existing_asset": {
                            "id": existing_asset["id"],
                            "address": existing_asset["address"],
                            "chain_name": existing_asset["chain_name"],
                            "token_symbol": existing_asset["symbol"],
                            "token_contract_address": existing_asset["contract_address"],
                            "wallet_name": existing_asset["wallet_name"],
                            "notes": existing_asset["notes"],
                            "tag": existing_asset["tag"],
                            "created_at": existing_asset["created_at"],
                        },
                        "message": "资产已存在",
                    }

            return {
                "exists": False,
                "message": "资产不存在，可以安全添加",
            }

    except Exception as e:
        logger.error(f"检查资产存在性失败: {e}")
        raise HTTPException(status_code=500, detail=f"检查资产存在性失败: {str(e)}")


@router.get(
    "/assets/summary",
    summary="获取资产汇总",
    description="获取资产的汇总统计信息（从数据库）",
)
async def get_assets_summary():
    """获取资产汇总"""
    try:
        return await asset_service.get_assets_summary()

    except Exception as e:
        logger.error(f"获取资产汇总失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取资产汇总失败: {str(e)}")


@router.delete(
    "/assets/{asset_id}",
    summary="删除资产",
            description="删除一个已管理的资产（从数据库）",
)
async def delete_asset(asset_id: str):
    """删除资产"""
    try:
        db_asset_service = DatabaseAssetService()
        success = await db_asset_service.delete_asset(asset_id)
        
        if success:
            return {"message": "资产删除成功"}
        else:
            raise HTTPException(status_code=404, detail="资产不存在")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除资产失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除资产失败: {str(e)}")


@router.put(
    "/assets/{asset_id}",
    response_model=AssetResponse,
    summary="更新资产信息",
    description="更新资产的钱包名称和备注信息（在数据库中）",
)
async def update_asset(asset_id: str, asset_update: AssetUpdateInput):
    """更新资产信息"""
    try:
        db_asset_service = DatabaseAssetService()
        updated_asset = await db_asset_service.update_asset(asset_id, asset_update)
        
        if updated_asset:
            return AssetResponse(
                message="资产更新成功",
                asset=updated_asset
            )
        else:
            raise HTTPException(status_code=404, detail="资产不存在")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新资产失败: {e}")
        raise HTTPException(status_code=500, detail=f"更新资产失败: {str(e)}")


@router.post(
    "/assets/batch-add",
    response_model=BatchAddTokensResponse,
    summary="批量添加代币",
    description="批量添加多个代币到资产列表，自动从代币库查找合约地址信息",
)
async def batch_add_tokens(request: BatchAddTokensRequest):
    """批量添加代币"""
    try:
        # 使用数据库服务进行批量添加
        db_asset_service = DatabaseAssetService()
        added_assets = []
        failed_tokens = []
        
        for token_symbol in request.tokens:
            try:
                asset_input = AssetInput(
                    address=request.address,
                    chain_name=request.chain_name,
                    token_symbol=token_symbol,
                    token_contract_address=None,  # 自动查找
                    wallet_name=request.wallet_name,
                    notes=None,
                    tag=request.tag
                )
                
                asset_data = await db_asset_service.add_asset(asset_input)
                added_assets.append(asset_data)
                
            except Exception as e:
                failed_tokens.append({
                    "token_symbol": token_symbol,
                    "error": str(e)
                })
        
        return BatchAddTokensResponse(
            success=len(added_assets) > 0,
            added_assets=added_assets,
            failed_tokens=failed_tokens,
            total_added=len(added_assets),
            total_failed=len(failed_tokens),
            message=f"成功添加 {len(added_assets)} 个代币，{len(failed_tokens)} 个失败"
        )
        
    except Exception as e:
        logger.error(f"批量添加代币失败: {e}")
        raise HTTPException(status_code=500, detail=f"批量添加代币失败: {str(e)}")


@router.get(
    "/wallets",
    summary="获取钱包名称列表",
    description="获取所有已使用的钱包名称列表（从数据库）",
)
async def get_wallet_names():
    """获取钱包名称列表"""
    try:
        db_asset_service = DatabaseAssetService()
        wallet_names = await db_asset_service.get_wallet_names()
        
        return {"wallet_names": wallet_names}

    except Exception as e:
        logger.error(f"获取钱包名称列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取钱包名称列表失败: {str(e)}")



@router.post(
    "/assets/refresh-prices",
    summary="刷新资产价格",
    description="手动刷新所有资产的价格信息",
)
async def refresh_asset_prices():
    """刷新资产价格"""
    try:
        # 使用数据库版本的资产服务
        db_asset_service = DatabaseAssetService()
        
        # 清空价格缓存，强制重新获取价格
        price_service = PriceService()
        price_service.clear_cache()
        
        # 重新获取详细资产信息（包含最新价格）
        detailed_assets = await db_asset_service.get_detailed_assets(refresh_prices=True)
        
        return {
            "message": f"成功刷新 {len(detailed_assets)} 个资产的价格",
            "asset_count": len(detailed_assets),
            "timestamp": time.time()
        }
        
    except Exception as e:
        logger.error(f"刷新资产价格失败: {e}")
        raise HTTPException(status_code=500, detail=f"刷新价格失败: {str(e)}") 
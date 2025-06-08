"""
代币管理路由模块

包含代币库和代币相关API端点
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query

from app.models.asset_models import (
    TokenLibraryResponse,
    TokenSuggestionResponse,
    TokenInput,
    TokenData,
    TokenUpdateInput,
)
from app.services.token_library_service import TokenLibraryService
from app.services.db_token_service import DatabaseTokenService
from app.core.logger import get_logger

logger = get_logger(__name__)

# 创建路由器
router = APIRouter(prefix="/api", tags=["代币管理"])

# 创建服务实例
token_library_service = TokenLibraryService()


@router.get(
    "/tokens/library",
    response_model=TokenLibraryResponse,
    summary="获取代币库",
    description="获取所有可用的代币信息（预定义 + 自定义）",
)
async def get_token_library(
    chain_name: Optional[str] = Query(None, description="按链名称筛选"),
    predefined_only: bool = Query(False, description="仅返回预定义代币"),
):
    """获取代币库"""
    try:
        if predefined_only:
            tokens = await token_library_service.get_predefined_tokens(chain_name)
        else:
            tokens = await token_library_service.get_all_tokens(chain_name)
        
        return TokenLibraryResponse(
            tokens=tokens,
            total_count=len(tokens)
        )
    except Exception as e:
        logger.error(f"获取代币库失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取代币库失败: {str(e)}")


@router.get(
    "/tokens/suggestions",
    response_model=TokenSuggestionResponse,
    summary="获取代币建议",
    description="根据查询字符串获取代币建议",
)
async def get_token_suggestions(
    query: str = Query(..., description="搜索查询（代币符号或名称）"),
    chain_name: Optional[str] = Query(None, description="按链名称筛选"),
    limit: int = Query(10, description="返回结果数量限制", ge=1, le=50),
):
    """获取代币建议"""
    try:
        suggestions = await token_library_service.get_token_suggestions(query, chain_name, limit)
        
        return TokenSuggestionResponse(suggestions=suggestions)
    except Exception as e:
        logger.error(f"获取代币建议失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取代币建议失败: {str(e)}")


@router.get(
    "/tokens/{chain_name}/{symbol}",
    summary="获取特定代币信息",
    description="获取指定链上特定代币的详细信息",
)
async def get_token_info(chain_name: str, symbol: str):
    """获取特定代币信息"""
    try:
        token = await token_library_service.find_token(symbol, chain_name)
        
        if token:
            return {
                "success": True,
                "token": token.dict(),
                "message": f"找到代币 {symbol}"
            }
        else:
            return {
                "success": False,
                "token": None,
                "message": f"未找到代币 {symbol}"
            }
    except Exception as e:
        logger.error(f"获取代币信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取代币信息失败: {str(e)}")


@router.post("/tokens", response_model=TokenData)
async def add_token(token_input: TokenInput):
    """添加自定义代币"""
    try:
        db_token_service = DatabaseTokenService()
        result = await db_token_service.add_token(token_input)
        return result
    except Exception as e:
        logger.error(f"添加代币失败: {e}")
        raise HTTPException(status_code=500, detail=f"添加代币失败: {str(e)}")


@router.get("/tokens", response_model=List[TokenData])
async def list_tokens(
    chain_name: Optional[str] = None,
    is_predefined: Optional[bool] = None,
    is_active: bool = True
):
    """获取代币列表"""
    try:
        db_token_service = DatabaseTokenService()
        return await db_token_service.list_tokens(chain_name, is_predefined, is_active)
    except Exception as e:
        logger.error(f"获取代币列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取代币列表失败: {str(e)}")


@router.get("/tokens/{token_id}", response_model=TokenData)
async def get_token(token_id: int):
    """获取单个代币信息"""
    try:
        db_token_service = DatabaseTokenService()
        token = await db_token_service.get_token_by_id(token_id)
        if not token:
            raise HTTPException(status_code=404, detail="代币不存在")
        return token
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取代币信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取代币信息失败: {str(e)}")


@router.put("/tokens/{token_id}", response_model=TokenData)
async def update_token(token_id: int, token_update: TokenUpdateInput):
    """更新代币信息"""
    try:
        db_token_service = DatabaseTokenService()
        token = await db_token_service.update_token(token_id, token_update)
        if not token:
            raise HTTPException(status_code=404, detail="代币不存在")
        return token
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新代币失败: {e}")
        raise HTTPException(status_code=500, detail=f"更新代币失败: {str(e)}")


@router.delete("/tokens/{token_id}")
async def delete_token(token_id: int):
    """删除代币"""
    try:
        db_token_service = DatabaseTokenService()
        success = await db_token_service.delete_token(token_id)
        if not success:
            raise HTTPException(status_code=404, detail="代币不存在")
        return {"message": "代币删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除代币失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除代币失败: {str(e)}")


@router.get("/tokens/search/{keyword}", response_model=List[TokenData])
async def search_tokens(
    keyword: str,
    chain_name: Optional[str] = None,
    limit: int = 20
):
    """搜索代币"""
    try:
        db_token_service = DatabaseTokenService()
        return await db_token_service.search_tokens(keyword, chain_name, limit)
    except Exception as e:
        logger.error(f"搜索代币失败: {e}")
        raise HTTPException(status_code=500, detail=f"搜索代币失败: {str(e)}")


@router.get("/tokens/statistics", response_model=dict)
async def get_token_statistics():
    """获取代币统计信息"""
    try:
        db_token_service = DatabaseTokenService()
        return await db_token_service.get_token_statistics()
    except Exception as e:
        logger.error(f"获取代币统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取代币统计失败: {str(e)}") 
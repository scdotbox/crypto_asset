"""
FastAPI 主应用文件（重构版）
使用模块化路由架构，整合所有功能
"""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# 导入统一日志系统
from app.core.logger import get_logger, setup_logging
from app.core.config import settings
from app.core.database import db_manager

# 导入所有模块化路由
from app.routers import (
    assets,
    tokens,
    blockchain,
    price_service,
    history,
    database,
    data_aggregator
)

# 导入历史数据服务
from app.services.asset_history_service import AssetHistoryService

# 初始化统一日志系统
setup_logging()

# 获取日志器
logger = get_logger(__name__)

# 创建历史数据服务实例
asset_history_service = AssetHistoryService()


async def periodic_snapshot_task():
    """定期保存资产快照的任务"""
    while True:
        try:
            # 每小时保存一次快照
            await asyncio.sleep(3600)  # 3600秒 = 1小时
            await asset_history_service.save_current_snapshot()
            logger.info("定期资产快照保存成功")
        except asyncio.CancelledError:
            logger.info("定期快照任务已取消")
            break
        except Exception as e:
            logger.error(f"定期保存资产快照失败: {e}")
            # 出错后等待5分钟再重试
            await asyncio.sleep(300)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """应用生命周期管理"""
    logger.info("启动加密货币资产管理 API")

    # 初始化数据库
    try:
        logger.info("正在初始化数据库...")
        await db_manager.init_database()
        logger.info("数据库初始化完成")
        
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        # 不阻止应用启动，但记录错误
    
    # 启动时保存一次快照（使用startup模式避免API调用）
    try:
        await asset_history_service.save_current_snapshot(startup=True)
        logger.info("启动时资产快照保存成功")
    except Exception as e:
        logger.error(f"启动时保存资产快照失败: {e}")

    # 启动定时任务
    snapshot_task = asyncio.create_task(periodic_snapshot_task())

    yield

    # 关闭时取消定时任务
    snapshot_task.cancel()
    try:
        await snapshot_task
    except asyncio.CancelledError:
        pass

    logger.info("关闭加密货币资产管理 API")


# 创建 FastAPI 应用实例
app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description=settings.api_description,
    lifespan=lifespan,
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境中应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册所有模块化路由
app.include_router(assets.router)
app.include_router(price_service.router)
app.include_router(tokens.router)
app.include_router(blockchain.router)
app.include_router(history.router)
app.include_router(database.router)

app.include_router(data_aggregator.router)


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """全局异常处理器"""
    logger.error(f"未处理的异常: {exc}")
    return JSONResponse(status_code=500, content={"detail": "服务器内部错误"})


@app.get("/", tags=["健康检查"])
async def root():
    """根路径健康检查"""
    return {
        "message": "加密货币资产管理 API",
        "version": settings.api_version,
        "status": "运行中",
        "architecture": "模块化路由",
        "modules": [
            "资产管理",
            "代币管理", 
            "区块链服务",
            "价格服务",
            "历史数据",
            "数据库管理",
            "日志管理",
            "数据聚合层"
        ]
    }


@app.get("/health", tags=["健康检查"])
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy", 
        "timestamp": "2024-01-01T00:00:00Z",
        "version": settings.api_version,
        "architecture": "modularized"
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )


"""
uv run python -m app.main
"""

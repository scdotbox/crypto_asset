"""
路由模块

将API路由按功能模块分类管理
"""

# 导入所有路由模块
from . import assets
from . import tokens
from . import blockchain
from . import price_service
from . import history
from . import database

# 导出所有路由器，供主应用使用
__all__ = [
    "assets",
    "tokens", 
    "blockchain",
    "price_service",
    "history",
    "database"
] 
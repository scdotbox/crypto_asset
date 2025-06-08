"""
代币库服务

提供代币信息管理功能，包括：
- 预定义代币库
- 自定义代币管理
- 代币搜索和建议
"""

import json
import os
from typing import List, Dict, Optional

# 使用统一日志系统
from app.core.logger import get_logger
from datetime import datetime

from app.core.config import PREDEFINED_TOKENS
from app.models.asset_models import TokenInfo

logger = get_logger(__name__)


class TokenLibraryService:
    """代币库服务类"""

    def __init__(self):
        # 使用相对于当前文件的路径
        current_dir = os.path.dirname(os.path.abspath(__file__))  # app/services/
        app_dir = os.path.dirname(current_dir)  # app/
        backend_dir = os.path.dirname(app_dir)  # backend/
        self.custom_tokens_file = os.path.join(backend_dir, "data", "custom_tokens.json")
        self._ensure_data_directory()

    def _ensure_data_directory(self):
        """确保数据目录存在"""
        data_dir = os.path.dirname(self.custom_tokens_file)
        if data_dir and not os.path.exists(data_dir):
            os.makedirs(data_dir, exist_ok=True)

    async def get_predefined_tokens(
        self, chain_name: Optional[str] = None
    ) -> List[TokenInfo]:
        """
        获取预定义代币列表

        Args:
            chain_name: 可选的链名称筛选

        Returns:
            预定义代币列表
        """
        tokens = []

        for chain, chain_tokens in PREDEFINED_TOKENS.items():
            if chain_name and chain.lower() != chain_name.lower():
                continue

            for symbol, token_data in chain_tokens.items():
                token_info = TokenInfo(
                    symbol=token_data["symbol"],
                    name=token_data["name"],
                    chain_name=chain,
                    contract_address=token_data.get("contract_address"),
                    decimals=token_data.get("decimals", 18),
                    coingecko_id=token_data.get("coingecko_id"),
                    is_predefined=True,
                    created_at=datetime.now().isoformat(),
                )
                tokens.append(token_info)

        return tokens

    async def get_custom_tokens(
        self, chain_name: Optional[str] = None
    ) -> List[TokenInfo]:
        """
        获取用户自定义代币列表

        Args:
            chain_name: 可选的链名称筛选

        Returns:
            自定义代币列表
        """
        try:
            if not os.path.exists(self.custom_tokens_file):
                return []

            with open(self.custom_tokens_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            tokens = []
            for token_data in data:
                if (
                    chain_name
                    and token_data["chain_name"].lower() != chain_name.lower()
                ):
                    continue
                tokens.append(TokenInfo.model_validate(token_data))

            return tokens

        except Exception as e:
            logger.error(f"加载自定义代币失败: {e}")
            return []

    async def get_all_tokens(self, chain_name: Optional[str] = None) -> List[TokenInfo]:
        """
        获取所有代币（预定义 + 自定义）

        Args:
            chain_name: 可选的链名称筛选

        Returns:
            所有代币列表
        """
        predefined_tokens = await self.get_predefined_tokens(chain_name)
        custom_tokens = await self.get_custom_tokens(chain_name)

        return predefined_tokens + custom_tokens

    async def find_token(self, symbol: str, chain_name: str) -> Optional[TokenInfo]:
        """
        查找特定代币

        Args:
            symbol: 代币符号
            chain_name: 链名称

        Returns:
            找到的代币信息，如果未找到则返回 None
        """
        all_tokens = await self.get_all_tokens(chain_name)

        for token in all_tokens:
            if (
                token.symbol.upper() == symbol.upper()
                and token.chain_name.lower() == chain_name.lower()
            ):
                return token

        return None

    async def add_custom_token(
        self,
        symbol: str,
        name: str,
        chain_name: str,
        contract_address: Optional[str] = None,
        decimals: int = 18,
        coingecko_id: Optional[str] = None,
    ) -> TokenInfo:
        """
        添加自定义代币

        Args:
            symbol: 代币符号
            name: 代币名称
            chain_name: 链名称
            contract_address: 合约地址
            decimals: 小数位数
            coingecko_id: CoinGecko ID

        Returns:
            创建的代币信息
        """
        try:
            # 检查是否已存在
            existing_token = await self.find_token(symbol, chain_name)
            if existing_token:
                raise ValueError(f"代币 {symbol} 在 {chain_name} 链上已存在")

            # 创建新代币
            token_info = TokenInfo(
                symbol=symbol,
                name=name,
                chain_name=chain_name,
                contract_address=contract_address,
                decimals=decimals,
                coingecko_id=coingecko_id,
                is_predefined=False,
                created_at=datetime.now().isoformat(),
            )

            # 加载现有自定义代币
            custom_tokens = await self.get_custom_tokens()

            # 添加新代币
            custom_tokens.append(token_info)

            # 保存到文件
            await self._save_custom_tokens(custom_tokens)

            logger.info(f"成功添加自定义代币: {symbol} on {chain_name}")
            return token_info

        except Exception as e:
            logger.error(f"添加自定义代币失败: {e}")
            raise

    async def _save_custom_tokens(self, tokens: List[TokenInfo]):
        """保存自定义代币到文件"""
        try:
            data = [token.model_dump() for token in tokens]

            with open(self.custom_tokens_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"保存自定义代币失败: {e}")
            raise

    async def get_token_suggestions(
        self, query: str, chain_name: Optional[str] = None, limit: int = 10
    ) -> List[TokenInfo]:
        """
        根据查询获取代币建议

        Args:
            query: 搜索查询（代币符号或名称）
            chain_name: 可选的链名称筛选
            limit: 返回结果数量限制

        Returns:
            匹配的代币列表
        """
        all_tokens = await self.get_all_tokens(chain_name)

        query_lower = query.lower()
        suggestions = []

        # 优先匹配符号
        for token in all_tokens:
            if token.symbol.lower().startswith(query_lower):
                suggestions.append(token)

        # 然后匹配名称
        for token in all_tokens:
            if token not in suggestions and query_lower in token.name.lower():
                suggestions.append(token)

        return suggestions[:limit]

    async def get_tokens(self, filters: Optional[Dict] = None) -> List[TokenInfo]:
        """
        获取代币列表（支持筛选）

        Args:
            filters: 筛选条件字典
                - chain_name: 按链名称筛选
                - predefined_only: 仅返回预定义代币

        Returns:
            代币列表
        """
        if not filters:
            filters = {}

        chain_name = filters.get("chain_name")
        predefined_only = filters.get("predefined_only", False)

        if predefined_only:
            return await self.get_predefined_tokens(chain_name)
        else:
            return await self.get_all_tokens(chain_name)

    async def search_tokens(self, filters: Dict) -> List[TokenInfo]:
        """
        搜索代币（支持查询和筛选）

        Args:
            filters: 搜索条件字典
                - query: 搜索查询字符串
                - chain_name: 可选的链名称筛选
                - limit: 返回结果数量限制

        Returns:
            匹配的代币列表
        """
        query = filters.get("query", "")
        chain_name = filters.get("chain_name")
        limit = filters.get("limit", 10)

        return await self.get_token_suggestions(query, chain_name, limit)

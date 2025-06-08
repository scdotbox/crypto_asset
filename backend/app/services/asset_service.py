"""
资产管理服务
"""

from typing import List, Optional, Dict, Any

# 使用统一日志系统
from app.core.logger import get_logger

from app.models.asset_models import (
    AssetInput,
    AssetData,
    AssetDisplay,
    AssetUpdateInput,
    AssetSummary
)
from app.services.blockchain_service import BlockchainService
from app.services.price_service import PriceService
from app.services.token_library_service import TokenLibraryService
from app.services.db_asset_service import DatabaseAssetService

logger = get_logger(__name__)


class AssetService:
    """资产服务类 - 现在基于数据库实现"""
    
    def __init__(self):
        self.blockchain_service = BlockchainService()
        self.price_service = PriceService()
        self.token_library_service = TokenLibraryService()
        self.db_asset_service = DatabaseAssetService()
        
    
    async def add_asset(self, asset_input: AssetInput) -> AssetData:
        """
        添加新资产（使用数据库）
        
        Args:
            asset_input: 用户输入的资产信息
            
        Returns:
            创建的资产数据
        """
        return await self.db_asset_service.add_asset(asset_input)
    
    async def get_detailed_assets(
        self, 
        chain_name: Optional[str] = None,
        address: Optional[str] = None,
        tag: Optional[str] = None
    ) -> List[AssetDisplay]:
        """
        获取详细的资产列表（包含价格和余额）
        优先使用缓存数据
        
        Args:
            chain_name: 按链名称筛选
            address: 按地址筛选
            tag: 按标签筛选
            
        Returns:
            资产展示列表
        """
        try:
            # 从数据库获取基础资产信息
            assets = await self.db_asset_service.get_detailed_assets(chain_name, address, tag)
            
            # 优化：使用缓存获取价格和余额
            enhanced_assets = []
            for asset in assets:
                try:
                    # 优先从历史缓存获取价格
                    price_usdc = await self.price_service.get_token_price_usdc_with_cache(
                        asset.token_symbol, asset.chain_name, use_history_cache=True
                    )
                    
                    # 优先从历史缓存获取余额
                    quantity = await self._get_cached_balance_or_fetch(
                        asset.address, asset.token_contract_address, asset.chain_name, asset.token_symbol
                    )
                    
                    # 计算价值
                    value_usdc = quantity * price_usdc if quantity > 0 and price_usdc > 0 else 0.0
                    
                    # 更新资产信息
                    asset.quantity = quantity
                    asset.price_usdc = price_usdc
                    asset.value_usdc = value_usdc
                    
                    enhanced_assets.append(asset)
                    
                except Exception as e:
                    logger.error(f"获取资产 {asset.id} 的详细信息失败: {e}")
                    # 即使出错也保留基础信息
                    asset.quantity = 0.0
                    asset.price_usdc = 0.0
                    asset.value_usdc = 0.0
                    enhanced_assets.append(asset)
            
            return enhanced_assets
            
        except Exception as e:
            logger.error(f"获取详细资产列表失败: {e}")
            raise
    
    async def _get_cached_balance_or_fetch(
        self, 
        address: str, 
        contract_address: Optional[str], 
        chain_name: str,
        token_symbol: str
    ) -> float:
        """
        优先从缓存获取余额，如果没有则实时查询
        
        Args:
            address: 钱包地址
            contract_address: 代币合约地址
            chain_name: 区块链名称
            token_symbol: 代币符号
            
        Returns:
            代币余额
        """
        try:
            # 首先尝试从历史缓存获取最新余额
            history_cache = self.price_service.history_cache
            if history_cache:
                cached_balance = await history_cache.get_latest_balance(
                    address, chain_name, token_symbol
                )
                if cached_balance is not None:
                    logger.debug(f"从历史缓存获取余额: {address}@{chain_name}:{token_symbol} = {cached_balance}")
                    return cached_balance
            
            # 如果缓存没有，则实时查询
            balance = await self.blockchain_service.get_token_balance(
                address, contract_address, chain_name
            )
            
            # 保存到历史缓存
            if balance >= 0 and history_cache:
                await history_cache.save_balance_history(
                    address=address,
                    chain_name=chain_name,
                    token_symbol=token_symbol,
                    balance=balance,
                    token_contract_address=contract_address
                )
                logger.debug(f"保存余额到历史缓存: {address}@{chain_name}:{token_symbol} = {balance}")
            
            return balance
            
        except Exception as e:
            logger.error(f"获取余额失败: {e}")
            return 0.0
    
    async def list_assets(self) -> List[AssetData]:
        """获取所有基础资产信息（从数据库）"""
        return await self.db_asset_service.list_assets()
    
    async def delete_asset(self, asset_id: str) -> bool:
        """删除资产（从数据库）"""
        return await self.db_asset_service.delete_asset(asset_id)
    
    async def update_asset(self, asset_id: str, asset_update: AssetUpdateInput) -> Optional[AssetData]:
        """更新资产信息（在数据库中）"""
        return await self.db_asset_service.update_asset(asset_id, asset_update)
    
    async def get_assets_summary(self) -> AssetSummary:
        """获取资产汇总信息（从数据库）"""
        return await self.db_asset_service.get_assets_summary()
    
    async def get_wallet_names(self) -> List[str]:
        """获取所有已使用的钱包名称（从数据库）"""
        return await self.db_asset_service.get_wallet_names()
    
    async def discover_wallet_tokens(
        self,
        address: str,
        chain_name: str,
        include_zero_balance: bool = False,
        min_value_usdc: float = 0.01
    ) -> List[Dict[str, Any]]:
        """发现钱包中的代币（使用数据库服务）"""
        return await self.db_asset_service.discover_wallet_tokens(
            address, chain_name, include_zero_balance, min_value_usdc
        )
    
    async def batch_add_tokens(
        self,
        address: str,
        chain_name: str,
        token_symbols: List[str],
        wallet_name: Optional[str] = None,
        tag: Optional[str] = None
    ) -> Dict[str, Any]:
        """批量添加代币（使用数据库服务）"""
        return await self.db_asset_service.batch_add_tokens(
            address, chain_name, token_symbols, wallet_name, tag
        )
    
    async def auto_add_discovered_tokens(
        self,
        address: str,
        chain_name: str,
        min_value_usdc: float = 0.01
    ) -> Dict[str, Any]:
        """自动添加发现的代币（使用数据库服务）"""
        return await self.db_asset_service.auto_add_discovered_tokens(
            address, chain_name, min_value_usdc
        )

    # ==================== 已弃用的JSON文件方法 ====================
    # 以下方法已弃用，保留用于向后兼容，但会记录警告
    
    def _load_assets_from_file(self) -> List[AssetData]:
        """已弃用：从JSON文件加载资产"""
        logger.warning("_load_assets_from_file 方法已弃用，请使用数据库版本")
        return []
    
    def _save_assets_to_file(self, assets: List[AssetData]) -> None:
        """已弃用：保存资产到JSON文件"""
        logger.warning("_save_assets_to_file 方法已弃用，请使用数据库版本")
        pass
    
    def _find_asset_by_id(self, asset_id: str, assets: List[AssetData]) -> Optional[AssetData]:
        """已弃用：在列表中查找资产"""
        logger.warning("_find_asset_by_id 方法已弃用，请使用数据库版本")
        return None
    
    def _asset_exists(self, asset_input: AssetInput, assets: List[AssetData]) -> bool:
        """已弃用：检查资产是否存在"""
        logger.warning("_asset_exists 方法已弃用，请使用数据库版本")
        return False

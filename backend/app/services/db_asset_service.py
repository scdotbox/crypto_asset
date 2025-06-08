"""
基于数据库的资产管理服务
"""

from typing import List, Optional, Dict, Any
import uuid

# 使用统一日志系统
from app.core.logger import get_logger

from app.models.asset_models import (
    AssetInput,
    AssetData,
    AssetDisplay,
    AssetUpdateInput,
    AssetSummary,
)
from app.core.database import db_manager
from app.services.blockchain_service import BlockchainService
from app.services.price_service import PriceService

logger = get_logger(__name__)


class DatabaseAssetService:
    """基于数据库的资产服务类"""

    def __init__(self):
        self.blockchain_service = BlockchainService()
        self.price_service = PriceService()

    async def add_asset(self, asset_input: AssetInput) -> AssetData:
        """
        添加新资产到数据库

        Args:
            asset_input: 资产输入信息

        Returns:
            创建或现有的资产数据
        """
        try:
            async with db_manager.get_connection() as conn:
                # 获取区块链ID
                blockchain_id = await self._get_blockchain_id(
                    conn, asset_input.chain_name
                )
                if not blockchain_id:
                    raise ValueError(f"不支持的区块链: {asset_input.chain_name}")

                # 获取或创建钱包
                wallet_id = await self._get_or_create_wallet(
                    conn, asset_input.address, blockchain_id, asset_input.wallet_name
                )

                # 获取或创建代币
                token_id = await self._get_or_create_token(
                    conn,
                    asset_input.token_symbol,
                    blockchain_id,
                    asset_input.token_contract_address,
                )

                # 检查资产是否已存在
                async with conn.execute(
                    """
                    SELECT id FROM assets WHERE wallet_id = ? AND token_id = ? AND is_active = 1
                """,
                    (wallet_id, token_id),
                ) as cursor:
                    existing_asset = await cursor.fetchone()
                    if existing_asset:
                        logger.info(f"资产已存在，返回现有资产: {existing_asset['id']}")
                        return await self._get_asset_by_id(conn, existing_asset["id"])

                # 创建新资产
                asset_id = str(uuid.uuid4())

                await conn.execute(
                    """
                    INSERT INTO assets (id, wallet_id, token_id, tag)
                    VALUES (?, ?, ?, ?)
                """,
                    (asset_id, wallet_id, token_id, asset_input.tag),
                )

                await conn.commit()

                # 返回创建的资产
                asset_data = await self._get_asset_by_id(conn, asset_id)
                logger.info(
                    f"成功添加资产: {asset_input.token_symbol} on {asset_input.chain_name}"
                )
                return asset_data

        except Exception as e:
            logger.error(f"添加资产失败: {e}")
            raise

    async def get_detailed_assets(
        self,
        chain_name: Optional[str] = None,
        address: Optional[str] = None,
        tag: Optional[str] = None,
        refresh_prices: bool = False,
    ) -> List[AssetDisplay]:
        """
        获取详细的资产列表（包含价格和余额）

        Args:
            chain_name: 按链名称筛选
            address: 按地址筛选
            tag: 按标签筛选
            refresh_prices: 是否刷新价格（重新从API获取）

        Returns:
            资产展示列表
        """
        try:
            async with db_manager.get_connection() as conn:
                # 构建查询条件
                where_conditions = ["a.is_active = 1"]
                params = []

                if chain_name:
                    where_conditions.append("b.name = ?")
                    params.append(chain_name)

                if address:
                    where_conditions.append("w.address = ?")
                    params.append(address)

                if tag:
                    where_conditions.append("a.tag = ?")
                    params.append(tag)

                where_clause = " AND ".join(where_conditions)

                # 查询资产
                query = f"""
                    SELECT 
                        a.id, a.tag,
                        w.address, w.wallet_name, w.notes,
                        t.symbol, t.name as token_name, t.contract_address, t.coingecko_id,
                        b.name as chain_name, b.display_name as chain_display_name
                    FROM assets a
                    JOIN wallets w ON a.wallet_id = w.id
                    JOIN tokens t ON a.token_id = t.id
                    JOIN blockchains b ON w.blockchain_id = b.id
                    WHERE {where_clause}
                    ORDER BY a.created_at DESC
                """

                assets = []
                async with conn.execute(query, params) as cursor:
                    async for row in cursor:
                        # 获取余额
                        quantity = await self.blockchain_service.get_token_balance(
                            row["address"], row["contract_address"], row["chain_name"]
                        )

                        # 获取价格（优先使用缓存，避免启动时大量API调用）
                        price_usdc = 0.0
                        try:
                            if refresh_prices:
                                # 强制刷新价格，从API获取最新价格
                                price_usdc = (
                                    await self.price_service.get_token_price_usdc(
                                        row["symbol"], row["chain_name"]
                                    )
                                )
                            else:
                                # 先尝试从缓存获取价格
                                cache_key = f"{row['symbol'].upper()}_{row['chain_name'] or 'default'}"
                                cached_price = self.price_service.price_cache.get(
                                    cache_key
                                )

                                if cached_price is not None:
                                    price_usdc = cached_price
                                elif row["symbol"].upper() in [
                                    "USDC",
                                    "USDT",
                                    "DAI",
                                    "BUSD",
                                ]:
                                    # 稳定币使用固定价格
                                    price_usdc = 1.0
                                    self.price_service.price_cache.set(
                                        cache_key, price_usdc
                                    )
                                else:
                                    # 对于其他代币，暂时使用0价格，避免启动时阻塞
                                    price_usdc = 0.0
                                    logger.debug(
                                        f"启动阶段跳过价格查询: {row['symbol']}"
                                    )
                        except Exception as price_error:
                            logger.warning(
                                f"获取价格失败，使用默认值: {row['symbol']}, 错误: {price_error}"
                            )
                            price_usdc = 0.0

                        # 计算价值
                        value_usdc = (
                            quantity * price_usdc
                            if quantity > 0 and price_usdc > 0
                            else 0.0
                        )

                        asset_display = AssetDisplay(
                            id=row["id"],
                            address=row["address"],
                            chain_name=row["chain_name"],
                            token_symbol=row["symbol"],
                            token_contract_address=row["contract_address"],
                            wallet_name=row["wallet_name"],
                            notes=row["notes"],
                            tag=row["tag"],
                            quantity=quantity,
                            price_usdc=price_usdc,
                            value_usdc=value_usdc,
                        )
                        assets.append(asset_display)

                return assets

        except Exception as e:
            logger.error(f"获取详细资产列表失败: {e}")
            raise

    async def list_assets(self) -> List[AssetData]:
        """获取所有基础资产信息"""
        try:
            async with db_manager.get_connection() as conn:
                query = """
                    SELECT 
                        a.id, a.tag, a.created_at,
                        w.address, w.wallet_name, w.notes,
                        t.symbol, t.contract_address,
                        b.name as chain_name
                    FROM assets a
                    JOIN wallets w ON a.wallet_id = w.id
                    JOIN tokens t ON a.token_id = t.id
                    JOIN blockchains b ON w.blockchain_id = b.id
                    WHERE a.is_active = 1
                    ORDER BY a.created_at DESC
                """

                assets = []
                async with conn.execute(query) as cursor:
                    async for row in cursor:
                        asset_data = AssetData(
                            id=row["id"],
                            address=row["address"],
                            chain_name=row["chain_name"],
                            token_symbol=row["symbol"],
                            token_contract_address=row["contract_address"],
                            wallet_name=row["wallet_name"],
                            notes=row["notes"],
                            tag=row["tag"],
                            created_at=row["created_at"],
                        )
                        assets.append(asset_data)

                return assets

        except Exception as e:
            logger.error(f"获取基础资产列表失败: {e}")
            raise

    async def delete_asset(self, asset_id: str) -> bool:
        """
        删除资产（软删除）

        Args:
            asset_id: 资产ID

        Returns:
            是否删除成功
        """
        try:
            async with db_manager.get_connection() as conn:
                # 软删除资产
                cursor = await conn.execute(
                    """
                    UPDATE assets 
                    SET is_active = 0, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND is_active = 1
                """,
                    (asset_id,),
                )

                await conn.commit()

                if cursor.rowcount > 0:
                    logger.info(f"成功删除资产: {asset_id}")
                    return True
                else:
                    return False

        except Exception as e:
            logger.error(f"删除资产失败: {e}")
            raise

    async def update_asset(
        self, asset_id: str, asset_update: AssetUpdateInput
    ) -> Optional[AssetData]:
        """
        更新资产信息

        Args:
            asset_id: 资产ID
            asset_update: 更新的资产信息

        Returns:
            更新后的资产数据，如果资产不存在则返回None
        """
        try:
            async with db_manager.get_connection() as conn:
                # 更新资产
                update_fields = []
                params = []

                if asset_update.tag is not None:
                    update_fields.append("tag = ?")
                    params.append(asset_update.tag)

                if (
                    asset_update.wallet_name is not None
                    or asset_update.notes is not None
                ):
                    # 需要更新钱包信息
                    wallet_update_fields = []
                    wallet_params = []

                    if asset_update.wallet_name is not None:
                        wallet_update_fields.append("wallet_name = ?")
                        wallet_params.append(asset_update.wallet_name)

                    if asset_update.notes is not None:
                        wallet_update_fields.append("notes = ?")
                        wallet_params.append(asset_update.notes)

                    if wallet_update_fields:
                        wallet_update_fields.append("updated_at = CURRENT_TIMESTAMP")
                        wallet_update_sql = f"UPDATE wallets SET {', '.join(wallet_update_fields)} WHERE id = (SELECT wallet_id FROM assets WHERE id = ?)"
                        wallet_params.append(asset_id)
                        await conn.execute(wallet_update_sql, wallet_params)

                if update_fields:
                    update_fields.append("updated_at = CURRENT_TIMESTAMP")
                    update_sql = f"UPDATE assets SET {', '.join(update_fields)} WHERE id = ? AND is_active = 1"
                    params.append(asset_id)
                    cursor = await conn.execute(update_sql, params)

                    if cursor.rowcount == 0:
                        return None

                await conn.commit()

                # 返回更新后的资产
                return await self._get_asset_by_id(conn, asset_id)

        except Exception as e:
            logger.error(f"更新资产失败: {e}")
            raise

    async def get_assets_summary(self) -> AssetSummary:
        """获取资产汇总信息"""
        try:
            assets = await self.get_detailed_assets()

            total_value_usdc = sum(asset.value_usdc for asset in assets)
            total_assets = len(assets)

            # 按链汇总
            chains_summary = {}
            for asset in assets:
                chain = asset.chain_name
                if chain not in chains_summary:
                    chains_summary[chain] = {
                        "chain_name": chain,
                        "asset_count": 0,
                        "total_value_usdc": 0.0,
                    }
                chains_summary[chain]["asset_count"] += 1
                chains_summary[chain]["total_value_usdc"] += asset.value_usdc

            # 按地址汇总
            addresses_summary = {}
            for asset in assets:
                address = asset.address
                if address not in addresses_summary:
                    addresses_summary[address] = {
                        "address": address,
                        "wallet_name": asset.wallet_name,
                        "asset_count": 0,
                        "total_value_usdc": 0.0,
                    }
                addresses_summary[address]["asset_count"] += 1
                addresses_summary[address]["total_value_usdc"] += asset.value_usdc

            return AssetSummary(
                total_value_usdc=total_value_usdc,
                total_assets=total_assets,
                chains_summary=list(chains_summary.values()),
                addresses_summary=list(addresses_summary.values()),
            )

        except Exception as e:
            logger.error(f"获取资产汇总失败: {e}")
            raise

    async def get_wallet_names(self) -> List[str]:
        """获取所有已使用的钱包名称"""
        try:
            async with db_manager.get_connection() as conn:
                wallet_names = []
                async with conn.execute("""
                    SELECT DISTINCT wallet_name FROM wallets 
                    WHERE wallet_name IS NOT NULL AND wallet_name != ''
                    ORDER BY wallet_name
                """) as cursor:
                    async for row in cursor:
                        wallet_names.append(row["wallet_name"])

                return wallet_names

        except Exception as e:
            logger.error(f"获取钱包名称列表失败: {e}")
            return []

    async def discover_wallet_tokens(
        self,
        address: str,
        chain_name: str,
        include_zero_balance: bool = False,
        min_value_usdc: float = 0.01,
    ) -> List[Dict[str, Any]]:
        """发现钱包中的代币"""
        try:
            # 导入区块链服务
            from app.services.blockchain_service import BlockchainService

            # 创建区块链服务实例
            blockchain_service = BlockchainService()

            # 不再调用 ensure_initialized()，改为按需初始化
            # 区块链服务会在需要时自动初始化指定的链

            # 调用区块链服务发现代币
            discovered_tokens = await blockchain_service.discover_wallet_tokens(
                address=address,
                chain_name=chain_name,
                include_zero_balance=include_zero_balance,
                min_value_usdc=min_value_usdc,
            )

            # 转换为字典格式
            result = []
            for token in discovered_tokens:
                token_dict = {
                    "symbol": token.symbol,
                    "name": token.name,
                    "contract_address": token.contract_address,
                    "balance": token.balance,
                    "decimals": token.decimals,
                    "is_native": token.is_native,
                    "price_usdc": token.price_usdc,
                    "value_usdc": token.value_usdc,
                }
                result.append(token_dict)

            logger.info(
                f"发现钱包 {address} 在 {chain_name} 链上的 {len(result)} 个代币"
            )
            return result

        except Exception as e:
            logger.error(f"发现钱包代币失败: {e}")
            raise

    async def batch_add_tokens(
        self,
        address: str,
        chain_name: str,
        token_symbols: List[str],
        wallet_name: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> Dict[str, Any]:
        """批量添加代币"""
        try:
            added_assets = []
            failed_tokens = []

            for token_symbol in token_symbols:
                try:
                    asset_input = AssetInput(
                        address=address,
                        chain_name=chain_name,
                        token_symbol=token_symbol,
                        token_contract_address=None,
                        wallet_name=wallet_name,
                        notes=None,
                        tag=tag,
                    )

                    asset_data = await self.add_asset(asset_input)
                    added_assets.append(asset_data)

                except Exception as e:
                    failed_tokens.append(
                        {"token_symbol": token_symbol, "error": str(e)}
                    )

            return {
                "success": True,
                "added_assets": added_assets,
                "failed_tokens": failed_tokens,
                "total_added": len(added_assets),
                "total_failed": len(failed_tokens),
                "message": f"成功添加 {len(added_assets)} 个代币，失败 {len(failed_tokens)} 个",
            }

        except Exception as e:
            logger.error(f"批量添加代币失败: {e}")
            raise

    async def auto_add_discovered_tokens(
        self, address: str, chain_name: str, min_value_usdc: float = 0.01
    ) -> Dict[str, Any]:
        """自动添加发现的代币"""
        try:
            # 发现代币
            discovered_tokens = await self.discover_wallet_tokens(
                address, chain_name, False, min_value_usdc
            )

            # 提取代币符号
            token_symbols = [token["symbol"] for token in discovered_tokens]

            # 批量添加
            return await self.batch_add_tokens(address, chain_name, token_symbols)

        except Exception as e:
            logger.error(f"自动添加发现的代币失败: {e}")
            raise

    # 私有辅助方法

    async def _get_blockchain_id(self, conn, chain_name: str) -> Optional[int]:
        """获取区块链ID"""
        async with conn.execute(
            """
            SELECT id FROM blockchains WHERE name = ? AND is_active = 1
        """,
            (chain_name,),
        ) as cursor:
            row = await cursor.fetchone()
            return row["id"] if row else None

    async def _get_or_create_wallet(
        self, conn, address: str, blockchain_id: int, wallet_name: Optional[str] = None
    ) -> int:
        """获取或创建钱包记录"""
        # 先尝试查找现有钱包
        async with conn.execute(
            """
            SELECT id FROM wallets WHERE address = ? AND blockchain_id = ?
        """,
            (address, blockchain_id),
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                # 如果有钱包名称，更新它
                if wallet_name:
                    await conn.execute(
                        """
                        UPDATE wallets SET wallet_name = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """,
                        (wallet_name, row["id"]),
                    )
                return row["id"]

        # 创建新钱包，使用try-except处理可能的UNIQUE约束冲突
        try:
            cursor = await conn.execute(
                """
                INSERT INTO wallets (address, blockchain_id, wallet_name)
                VALUES (?, ?, ?)
            """,
                (address, blockchain_id, wallet_name),
            )
            return cursor.lastrowid

        except Exception as insert_error:
            # 检查是否是UNIQUE约束冲突
            if "UNIQUE constraint failed" in str(
                insert_error
            ) and "address, blockchain_id" in str(insert_error):
                logger.info(
                    f"检测到钱包UNIQUE约束冲突，查找现有钱包: address={address}, blockchain_id={blockchain_id}"
                )
                # 重新查询现有钱包（可能是并发创建的）
                async with conn.execute(
                    """
                    SELECT id FROM wallets WHERE address = ? AND blockchain_id = ?
                """,
                    (address, blockchain_id),
                ) as cursor:
                    existing_wallet = await cursor.fetchone()
                    if existing_wallet:
                        logger.info(f"找到并发创建的钱包: {existing_wallet['id']}")
                        # 如果有钱包名称，更新它
                        if wallet_name:
                            await conn.execute(
                                """
                                UPDATE wallets SET wallet_name = ?, updated_at = CURRENT_TIMESTAMP
                                WHERE id = ?
                            """,
                                (wallet_name, existing_wallet["id"]),
                            )
                        return existing_wallet["id"]
                    else:
                        # 如果还是找不到，说明可能是其他问题
                        logger.error(
                            f"钱包UNIQUE约束冲突但未找到现有钱包: {insert_error}"
                        )
                        raise ValueError(
                            f"钱包创建失败，可能已存在但查询不到: {insert_error}"
                        )
            else:
                # 其他类型的插入错误，直接抛出
                raise insert_error

    async def _get_or_create_token(
        self,
        conn,
        symbol: str,
        blockchain_id: int,
        contract_address: Optional[str] = None,
    ) -> int:
        """获取或创建代币记录"""
        # 先尝试查找现有代币
        if contract_address:
            async with conn.execute(
                """
                SELECT id FROM tokens 
                WHERE symbol = ? AND blockchain_id = ? AND contract_address = ? AND is_active = 1
            """,
                (symbol, blockchain_id, contract_address),
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return row["id"]
        else:
            async with conn.execute(
                """
                SELECT id FROM tokens 
                WHERE symbol = ? AND blockchain_id = ? AND contract_address IS NULL AND is_active = 1
            """,
                (symbol, blockchain_id),
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return row["id"]

        # 创建新代币，使用try-except处理可能的UNIQUE约束冲突
        try:
            cursor = await conn.execute(
                """
                INSERT INTO tokens (symbol, name, blockchain_id, contract_address, is_predefined)
                VALUES (?, ?, ?, ?, 0)
            """,
                (symbol, symbol, blockchain_id, contract_address),
            )
            return cursor.lastrowid

        except Exception as insert_error:
            # 检查是否是UNIQUE约束冲突
            if "UNIQUE constraint failed" in str(
                insert_error
            ) and "symbol, blockchain_id, contract_address" in str(insert_error):
                logger.info(
                    f"检测到代币UNIQUE约束冲突，查找现有代币: symbol={symbol}, blockchain_id={blockchain_id}, contract_address={contract_address}"
                )
                # 重新查询现有代币（可能是并发创建的）
                if contract_address:
                    async with conn.execute(
                        """
                        SELECT id FROM tokens 
                        WHERE symbol = ? AND blockchain_id = ? AND contract_address = ? AND is_active = 1
                    """,
                        (symbol, blockchain_id, contract_address),
                    ) as cursor:
                        existing_token = await cursor.fetchone()
                        if existing_token:
                            logger.info(f"找到并发创建的代币: {existing_token['id']}")
                            return existing_token["id"]
                else:
                    async with conn.execute(
                        """
                        SELECT id FROM tokens 
                        WHERE symbol = ? AND blockchain_id = ? AND contract_address IS NULL AND is_active = 1
                    """,
                        (symbol, blockchain_id),
                    ) as cursor:
                        existing_token = await cursor.fetchone()
                        if existing_token:
                            logger.info(f"找到并发创建的代币: {existing_token['id']}")
                            return existing_token["id"]

                # 如果还是找不到，说明可能是其他问题
                logger.error(f"代币UNIQUE约束冲突但未找到现有代币: {insert_error}")
                raise ValueError(f"代币创建失败，可能已存在但查询不到: {insert_error}")
            else:
                # 其他类型的插入错误，直接抛出
                raise insert_error

    async def _get_asset_by_id(self, conn, asset_id: str) -> AssetData:
        """根据ID获取资产数据"""
        query = """
            SELECT 
                a.id, a.tag, a.created_at,
                w.address, w.wallet_name, w.notes,
                t.symbol, t.contract_address,
                b.name as chain_name
            FROM assets a
            JOIN wallets w ON a.wallet_id = w.id
            JOIN tokens t ON a.token_id = t.id
            JOIN blockchains b ON w.blockchain_id = b.id
            WHERE a.id = ? AND a.is_active = 1
        """

        async with conn.execute(query, (asset_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                raise ValueError(f"资产不存在: {asset_id}")

            return AssetData(
                id=row["id"],
                address=row["address"],
                chain_name=row["chain_name"],
                token_symbol=row["symbol"],
                token_contract_address=row["contract_address"],
                wallet_name=row["wallet_name"],
                notes=row["notes"],
                tag=row["tag"],
                created_at=row["created_at"] or "",
            )

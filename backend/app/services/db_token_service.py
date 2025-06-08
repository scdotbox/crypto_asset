"""
基于数据库的代币管理服务
"""

from typing import List, Optional, Dict, Any

# 使用统一日志系统
from app.core.logger import get_logger

logger = get_logger(__name__)

from app.core.database import db_manager
from app.models.asset_models import TokenData, TokenInput, TokenUpdateInput


class DatabaseTokenService:
    """基于数据库的代币服务类"""
    
    async def add_token(self, token_input: TokenInput) -> TokenData:
        """
        添加新代币到数据库
        
        Args:
            token_input: 代币输入信息
            
        Returns:
            创建的代币数据
        """
        try:
            async with db_manager.get_connection() as conn:
                # 获取区块链ID
                blockchain_id = await self._get_blockchain_id(conn, token_input.chain_name)
                if not blockchain_id:
                    raise ValueError(f"不支持的区块链: {token_input.chain_name}")
                
                # 检查代币是否已存在
                existing_token = await self._find_existing_token(
                    conn, token_input.symbol, blockchain_id, token_input.contract_address
                )
                
                if existing_token:
                    # 如果代币已存在但被禁用，重新激活
                    if not existing_token['is_active']:
                        await conn.execute("""
                            UPDATE tokens 
                            SET is_active = 1, updated_at = CURRENT_TIMESTAMP
                            WHERE id = ?
                        """, (existing_token['id'],))
                        await conn.commit()
                    
                    return await self._get_token_by_id(conn, existing_token['id'])
                
                # 创建新代币
                cursor = await conn.execute("""
                    INSERT INTO tokens 
                    (symbol, name, blockchain_id, contract_address, decimals, coingecko_id, is_predefined)
                    VALUES (?, ?, ?, ?, ?, ?, 0)
                """, (
                    token_input.symbol,
                    token_input.name or token_input.symbol,
                    blockchain_id,
                    token_input.contract_address,
                    token_input.decimals or 18,
                    token_input.coingecko_id
                ))
                
                await conn.commit()
                
                # 返回创建的代币
                if cursor.lastrowid is None:
                    raise ValueError("创建代币失败，无法获取新代币ID")
                token_data = await self._get_token_by_id(conn, cursor.lastrowid)
                logger.info(f"成功添加代币: {token_input.symbol} on {token_input.chain_name}")
                return token_data
                
        except Exception as e:
            logger.error(f"添加代币失败: {e}")
            raise
    
    async def list_tokens(
        self,
        chain_name: Optional[str] = None,
        is_predefined: Optional[bool] = None,
        is_active: bool = True
    ) -> List[TokenData]:
        """
        获取代币列表
        
        Args:
            chain_name: 按链名称筛选
            is_predefined: 按是否预定义筛选
            is_active: 按是否激活筛选
            
        Returns:
            代币数据列表
        """
        try:
            async with db_manager.get_connection() as conn:
                # 构建查询条件
                where_conditions = []
                params = []
                
                if is_active is not None:
                    where_conditions.append("t.is_active = ?")
                    params.append(is_active)
                
                if chain_name:
                    where_conditions.append("b.name = ?")
                    params.append(chain_name)
                
                if is_predefined is not None:
                    where_conditions.append("t.is_predefined = ?")
                    params.append(is_predefined)
                
                where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
                
                # 查询代币
                query = f"""
                    SELECT 
                        t.id, t.symbol, t.name, t.contract_address, t.decimals, 
                        t.coingecko_id, t.is_predefined, t.is_active, t.created_at,
                        b.name as chain_name, b.display_name as chain_display_name
                    FROM tokens t
                    JOIN blockchains b ON t.blockchain_id = b.id
                    WHERE {where_clause}
                    ORDER BY t.is_predefined DESC, t.symbol ASC
                """
                
                tokens = []
                async with conn.execute(query, params) as cursor:
                    async for row in cursor:
                        token_data = TokenData(
                            id=row['id'],
                            symbol=row['symbol'],
                            name=row['name'],
                            chain_name=row['chain_name'],
                            contract_address=row['contract_address'],
                            decimals=row['decimals'],
                            coingecko_id=row['coingecko_id'],
                            is_predefined=bool(row['is_predefined']),
                            is_active=bool(row['is_active']),
                            created_at=row['created_at']
                        )
                        tokens.append(token_data)
                
                return tokens
                
        except Exception as e:
            logger.error(f"获取代币列表失败: {e}")
            raise
    
    async def get_token_by_id(self, token_id: int) -> Optional[TokenData]:
        """根据ID获取代币"""
        try:
            async with db_manager.get_connection() as conn:
                return await self._get_token_by_id(conn, token_id)
        except Exception as e:
            logger.error(f"获取代币失败: {e}")
            return None
    
    async def get_token_by_symbol(
        self, 
        symbol: str, 
        chain_name: str, 
        contract_address: Optional[str] = None
    ) -> Optional[TokenData]:
        """根据符号和链名称获取代币"""
        try:
            async with db_manager.get_connection() as conn:
                blockchain_id = await self._get_blockchain_id(conn, chain_name)
                if not blockchain_id:
                    return None
                
                if contract_address:
                    query = """
                        SELECT 
                            t.id, t.symbol, t.name, t.contract_address, t.decimals, 
                            t.coingecko_id, t.is_predefined, t.is_active, t.created_at,
                            b.name as chain_name
                        FROM tokens t
                        JOIN blockchains b ON t.blockchain_id = b.id
                        WHERE t.symbol = ? AND t.blockchain_id = ? AND t.contract_address = ? AND t.is_active = 1
                    """
                    params = (symbol, blockchain_id, contract_address)
                else:
                    query = """
                        SELECT 
                            t.id, t.symbol, t.name, t.contract_address, t.decimals, 
                            t.coingecko_id, t.is_predefined, t.is_active, t.created_at,
                            b.name as chain_name
                        FROM tokens t
                        JOIN blockchains b ON t.blockchain_id = b.id
                        WHERE t.symbol = ? AND t.blockchain_id = ? AND t.contract_address IS NULL AND t.is_active = 1
                    """
                    params = (symbol, blockchain_id)
                
                async with conn.execute(query, params) as cursor:
                    row = await cursor.fetchone()
                    if not row:
                        return None
                    
                    return TokenData(
                        id=row['id'],
                        symbol=row['symbol'],
                        name=row['name'],
                        chain_name=row['chain_name'],
                        contract_address=row['contract_address'],
                        decimals=row['decimals'],
                        coingecko_id=row['coingecko_id'],
                        is_predefined=bool(row['is_predefined']),
                        is_active=bool(row['is_active']),
                        created_at=row['created_at']
                    )
                    
        except Exception as e:
            logger.error(f"根据符号获取代币失败: {e}")
            return None
    
    async def update_token(self, token_id: int, token_update: TokenUpdateInput) -> Optional[TokenData]:
        """
        更新代币信息
        
        Args:
            token_id: 代币ID
            token_update: 更新的代币信息
            
        Returns:
            更新后的代币数据，如果代币不存在则返回None
        """
        try:
            async with db_manager.get_connection() as conn:
                # 构建更新字段
                update_fields = []
                params = []
                
                if token_update.name is not None:
                    update_fields.append("name = ?")
                    params.append(token_update.name)
                
                if token_update.decimals is not None:
                    update_fields.append("decimals = ?")
                    params.append(token_update.decimals)
                
                if token_update.coingecko_id is not None:
                    update_fields.append("coingecko_id = ?")
                    params.append(token_update.coingecko_id)
                
                if not update_fields:
                    # 没有需要更新的字段
                    return await self._get_token_by_id(conn, token_id)
                
                update_fields.append("updated_at = CURRENT_TIMESTAMP")
                update_sql = f"UPDATE tokens SET {', '.join(update_fields)} WHERE id = ? AND is_active = 1"
                params.append(token_id)
                
                cursor = await conn.execute(update_sql, params)
                
                if cursor.rowcount == 0:
                    return None
                
                await conn.commit()
                
                # 返回更新后的代币
                return await self._get_token_by_id(conn, token_id)
                
        except Exception as e:
            logger.error(f"更新代币失败: {e}")
            raise
    
    async def delete_token(self, token_id: int) -> bool:
        """
        删除代币（软删除）
        
        Args:
            token_id: 代币ID
            
        Returns:
            是否删除成功
        """
        try:
            async with db_manager.get_connection() as conn:
                # 检查是否有关联的资产
                async with conn.execute("""
                    SELECT COUNT(*) as count FROM assets a
                    JOIN tokens t ON a.token_id = t.id
                    WHERE t.id = ? AND a.is_active = 1
                """, (token_id,)) as cursor:
                    row = await cursor.fetchone()
                    if row['count'] > 0:
                        raise ValueError("无法删除代币，存在关联的资产")
                
                # 软删除代币
                cursor = await conn.execute("""
                    UPDATE tokens 
                    SET is_active = 0, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND is_active = 1 AND is_predefined = 0
                """, (token_id,))
                
                await conn.commit()
                
                if cursor.rowcount > 0:
                    logger.info(f"成功删除代币: {token_id}")
                    return True
                else:
                    return False
                    
        except Exception as e:
            logger.error(f"删除代币失败: {e}")
            raise
    
    async def search_tokens(
        self,
        keyword: str,
        chain_name: Optional[str] = None,
        limit: int = 20
    ) -> List[TokenData]:
        """
        搜索代币
        
        Args:
            keyword: 搜索关键词（符号或名称）
            chain_name: 按链名称筛选
            limit: 返回结果数量限制
            
        Returns:
            匹配的代币列表
        """
        try:
            async with db_manager.get_connection() as conn:
                # 构建查询条件
                where_conditions = ["t.is_active = 1"]
                params = []
                
                # 添加关键词搜索
                where_conditions.append("(t.symbol LIKE ? OR t.name LIKE ?)")
                keyword_pattern = f"%{keyword}%"
                params.extend([keyword_pattern, keyword_pattern])
                
                if chain_name:
                    where_conditions.append("b.name = ?")
                    params.append(chain_name)
                
                where_clause = " AND ".join(where_conditions)
                
                # 查询代币
                query = f"""
                    SELECT 
                        t.id, t.symbol, t.name, t.contract_address, t.decimals, 
                        t.coingecko_id, t.is_predefined, t.is_active, t.created_at,
                        b.name as chain_name
                    FROM tokens t
                    JOIN blockchains b ON t.blockchain_id = b.id
                    WHERE {where_clause}
                    ORDER BY t.is_predefined DESC, t.symbol ASC
                    LIMIT ?
                """
                params.append(limit)
                
                tokens = []
                async with conn.execute(query, params) as cursor:
                    async for row in cursor:
                        token_data = TokenData(
                            id=row['id'],
                            symbol=row['symbol'],
                            name=row['name'],
                            chain_name=row['chain_name'],
                            contract_address=row['contract_address'],
                            decimals=row['decimals'],
                            coingecko_id=row['coingecko_id'],
                            is_predefined=bool(row['is_predefined']),
                            is_active=bool(row['is_active']),
                            created_at=row['created_at']
                        )
                        tokens.append(token_data)
                
                return tokens
                
        except Exception as e:
            logger.error(f"搜索代币失败: {e}")
            raise
    
    async def get_tokens_by_chain(self, chain_name: str) -> List[TokenData]:
        """获取指定链上的所有代币"""
        return await self.list_tokens(chain_name=chain_name, is_active=True)
    
    async def get_predefined_tokens(self, chain_name: Optional[str] = None) -> List[TokenData]:
        """获取预定义代币"""
        return await self.list_tokens(chain_name=chain_name, is_predefined=True, is_active=True)
    
    async def get_custom_tokens(self, chain_name: Optional[str] = None) -> List[TokenData]:
        """获取自定义代币"""
        return await self.list_tokens(chain_name=chain_name, is_predefined=False, is_active=True)
    
    async def get_token_statistics(self) -> Dict[str, Any]:
        """获取代币统计信息"""
        try:
            async with db_manager.get_connection() as conn:
                # 总代币数
                async with conn.execute("SELECT COUNT(*) as count FROM tokens WHERE is_active = 1") as cursor:
                    row = await cursor.fetchone()
                    total_tokens = row['count'] if row else 0
                
                # 预定义代币数
                async with conn.execute("SELECT COUNT(*) as count FROM tokens WHERE is_predefined = 1 AND is_active = 1") as cursor:
                    row = await cursor.fetchone()
                    predefined_tokens = row['count'] if row else 0
                
                # 自定义代币数
                custom_tokens = total_tokens - predefined_tokens
                
                # 按链统计
                chain_stats = []
                async with conn.execute("""
                    SELECT 
                        b.name as chain_name,
                        b.display_name,
                        COUNT(*) as token_count
                    FROM tokens t
                    JOIN blockchains b ON t.blockchain_id = b.id
                    WHERE t.is_active = 1
                    GROUP BY b.id, b.name, b.display_name
                    ORDER BY token_count DESC
                """) as cursor:
                    async for row in cursor:
                        chain_stats.append({
                            "chain_name": row['chain_name'],
                            "chain_display_name": row['display_name'],
                            "token_count": row['token_count']
                        })
                
                return {
                    "total_tokens": total_tokens,
                    "predefined_tokens": predefined_tokens,
                    "custom_tokens": custom_tokens,
                    "chain_statistics": chain_stats
                }
                
        except Exception as e:
            logger.error(f"获取代币统计失败: {e}")
            raise
    
    # 私有辅助方法
    
    async def _get_blockchain_id(self, conn, chain_name: str) -> Optional[int]:
        """获取区块链ID"""
        async with conn.execute("""
            SELECT id FROM blockchains WHERE name = ? AND is_active = 1
        """, (chain_name,)) as cursor:
            row = await cursor.fetchone()
            return row['id'] if row else None
    
    async def _find_existing_token(
        self, 
        conn, 
        symbol: str, 
        blockchain_id: int, 
        contract_address: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """查找现有代币"""
        # 首先检查完全匹配的代币
        if contract_address:
            query = """
                SELECT id, is_active FROM tokens 
                WHERE symbol = ? AND blockchain_id = ? AND contract_address = ?
            """
            params = (symbol, blockchain_id, contract_address)
        else:
            query = """
                SELECT id, is_active FROM tokens 
                WHERE symbol = ? AND blockchain_id = ? AND contract_address IS NULL
            """
            params = (symbol, blockchain_id)
        
        async with conn.execute(query, params) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    "id": row['id'],
                    "is_active": bool(row['is_active'])
                }
        
        # 检查是否存在相同符号的其他代币（用于警告）
        similar_tokens_query = """
            SELECT id, name, contract_address, is_predefined 
            FROM tokens 
            WHERE symbol = ? AND blockchain_id = ? AND is_active = 1
        """
        similar_tokens = []
        async with conn.execute(similar_tokens_query, (symbol, blockchain_id)) as cursor:
            async for row in cursor:
                similar_tokens.append({
                    "id": row['id'],
                    "name": row['name'],
                    "contract_address": row['contract_address'],
                    "is_predefined": bool(row['is_predefined'])
                })
        
        if similar_tokens:
            logger.warning(f"发现 {len(similar_tokens)} 个相同符号的代币 {symbol}:")
            for token in similar_tokens:
                logger.warning(f"  ID: {token['id']}, 名称: {token['name']}, 合约: {token['contract_address'] or '无'}, 预定义: {token['is_predefined']}")
        
        return None
    
    async def _get_token_by_id(self, conn, token_id: int) -> TokenData:
        """根据ID获取代币数据"""
        query = """
            SELECT 
                t.id, t.symbol, t.name, t.contract_address, t.decimals, 
                t.coingecko_id, t.is_predefined, t.is_active, t.created_at,
                b.name as chain_name
            FROM tokens t
            JOIN blockchains b ON t.blockchain_id = b.id
            WHERE t.id = ?
        """
        
        async with conn.execute(query, (token_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                raise ValueError(f"代币不存在: {token_id}")
            
            return TokenData(
                id=row['id'],
                symbol=row['symbol'],
                name=row['name'],
                chain_name=row['chain_name'],
                contract_address=row['contract_address'],
                decimals=row['decimals'],
                coingecko_id=row['coingecko_id'],
                is_predefined=bool(row['is_predefined']),
                is_active=bool(row['is_active']),
                created_at=row['created_at']
            ) 
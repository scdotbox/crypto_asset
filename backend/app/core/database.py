"""
数据库配置和连接管理
"""

import aiosqlite
import os
from contextlib import asynccontextmanager

# 使用统一日志系统
from app.core.logger import get_logger

logger = get_logger(__name__)


class DatabaseManager:
    """数据库管理器"""

    def __init__(self):
        current_file = os.path.abspath(__file__)
        backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
        project_root = os.path.dirname(backend_dir)

        data_dir = os.path.join(project_root, "data")

        self.db_path = os.path.join(data_dir, "crypto_manager.db")
        self._ensure_data_directory()

    def _ensure_data_directory(self):
        """确保数据目录存在"""
        data_dir = os.path.dirname(self.db_path)
        if data_dir and not os.path.exists(data_dir):
            os.makedirs(data_dir, exist_ok=True)

    @asynccontextmanager
    async def get_connection(self):
        """获取数据库连接的上下文管理器"""
        conn = None
        try:
            conn = await aiosqlite.connect(self.db_path, timeout=30.0)
            conn.row_factory = aiosqlite.Row  # 启用字典式访问

            # 设置WAL模式以提高并发性能
            await conn.execute("PRAGMA journal_mode=WAL")

            # 设置同步模式为NORMAL以提高性能
            await conn.execute("PRAGMA synchronous=NORMAL")

            # 设置忙等待超时
            await conn.execute("PRAGMA busy_timeout=30000")

            yield conn
        except Exception as e:
            logger.error(f"数据库连接错误: {e}")
            raise
        finally:
            if conn:
                await conn.close()

    async def init_database(self):
        """初始化数据库表结构"""
        try:
            async with self.get_connection() as conn:
                # 创建区块链表（移除native_token字段，统一使用预定义代币库管理）
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS blockchains (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT UNIQUE NOT NULL,
                        display_name TEXT NOT NULL,
                        rpc_url TEXT NOT NULL,
                        explorer_url TEXT,
                        chain_type TEXT DEFAULT 'evm',
                        is_active BOOLEAN DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # 创建钱包表
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS wallets (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        address TEXT NOT NULL,
                        blockchain_id INTEGER NOT NULL,
                        wallet_name TEXT,
                        notes TEXT,
                        creation_timestamp INTEGER,
                        creation_date TEXT,
                        first_transaction_hash TEXT,
                        block_number INTEGER,
                        is_estimated BOOLEAN DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (blockchain_id) REFERENCES blockchains (id),
                        UNIQUE(address, blockchain_id)
                    )
                """)

                # 创建代币表
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS tokens (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol TEXT NOT NULL,
                        name TEXT NOT NULL,
                        blockchain_id INTEGER NOT NULL,
                        contract_address TEXT,
                        decimals INTEGER DEFAULT 18,
                        coingecko_id TEXT,
                        is_predefined BOOLEAN DEFAULT 0,
                        is_active BOOLEAN DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (blockchain_id) REFERENCES blockchains (id),
                        UNIQUE(symbol, blockchain_id, contract_address)
                    )
                """)

                # 创建资产表（用户管理的资产）
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS assets (
                        id TEXT PRIMARY KEY,
                        wallet_id INTEGER NOT NULL,
                        token_id INTEGER NOT NULL,
                        tag TEXT,
                        is_active BOOLEAN DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (wallet_id) REFERENCES wallets (id),
                        FOREIGN KEY (token_id) REFERENCES tokens (id),
                        UNIQUE(wallet_id, token_id)
                    )
                """)

                # 创建价格历史表
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS price_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        token_id INTEGER NOT NULL,
                        timestamp INTEGER NOT NULL,
                        date TEXT NOT NULL,
                        price_usdc REAL NOT NULL,
                        source TEXT DEFAULT 'coingecko',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (token_id) REFERENCES tokens (id),
                        UNIQUE(token_id, timestamp)
                    )
                """)

                # 创建余额历史表
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS balance_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        asset_id TEXT NOT NULL,
                        timestamp INTEGER NOT NULL,
                        date TEXT NOT NULL,
                        balance REAL NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (asset_id) REFERENCES assets (id),
                        UNIQUE(asset_id, timestamp)
                    )
                """)

                # 创建资产快照表（用于历史数据）
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS asset_snapshots (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        asset_id TEXT NOT NULL,
                        timestamp INTEGER NOT NULL,
                        date TEXT NOT NULL,
                        quantity REAL NOT NULL,
                        price_usdc REAL NOT NULL,
                        value_usdc REAL NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (asset_id) REFERENCES assets (id),
                        UNIQUE(asset_id, timestamp)
                    )
                """)

                # 创建价格缓存表（优化价格服务性能）
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS price_cache (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        token_symbol TEXT NOT NULL,
                        chain_name TEXT,
                        coingecko_id TEXT,
                        price_usdc REAL NOT NULL,
                        timestamp INTEGER NOT NULL,
                        expires_at INTEGER NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(token_symbol, chain_name, coingecko_id)
                    )
                """)

                # 创建余额缓存表（优化余额查询性能）
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS balance_cache (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        address TEXT NOT NULL,
                        chain_name TEXT NOT NULL,
                        token_symbol TEXT NOT NULL,
                        token_contract_address TEXT,
                        balance REAL NOT NULL,
                        timestamp INTEGER NOT NULL,
                        expires_at INTEGER NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(address, chain_name, token_symbol, token_contract_address)
                    )
                """)

                # 创建系统配置表（存储系统设置）
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS system_config (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        config_key TEXT UNIQUE NOT NULL,
                        config_value TEXT NOT NULL,
                        description TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # 创建索引
                await self._create_indexes(conn)

                # 初始化系统配置
                await self._init_system_config(conn)

                # 初始化基础数据（区块链和预定义代币）
                await self._init_base_data(conn)

                await conn.commit()
                logger.info("数据库初始化完成")

        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")
            raise

    async def _create_indexes(self, conn):
        """创建数据库索引"""
        indexes = [
            # 钱包表索引
            "CREATE INDEX IF NOT EXISTS idx_wallets_address ON wallets(address)",
            "CREATE INDEX IF NOT EXISTS idx_wallets_blockchain ON wallets(blockchain_id)",
            "CREATE INDEX IF NOT EXISTS idx_wallets_name ON wallets(wallet_name)",
            # 代币表索引
            "CREATE INDEX IF NOT EXISTS idx_tokens_symbol ON tokens(symbol)",
            "CREATE INDEX IF NOT EXISTS idx_tokens_blockchain ON tokens(blockchain_id)",
            "CREATE INDEX IF NOT EXISTS idx_tokens_contract ON tokens(contract_address)",
            "CREATE INDEX IF NOT EXISTS idx_tokens_coingecko ON tokens(coingecko_id)",
            "CREATE INDEX IF NOT EXISTS idx_tokens_active ON tokens(is_active)",
            # 资产表索引
            "CREATE INDEX IF NOT EXISTS idx_assets_wallet ON assets(wallet_id)",
            "CREATE INDEX IF NOT EXISTS idx_assets_token ON assets(token_id)",
            "CREATE INDEX IF NOT EXISTS idx_assets_tag ON assets(tag)",
            "CREATE INDEX IF NOT EXISTS idx_assets_active ON assets(is_active)",
            # 价格历史表索引
            "CREATE INDEX IF NOT EXISTS idx_price_history_token ON price_history(token_id)",
            "CREATE INDEX IF NOT EXISTS idx_price_history_timestamp ON price_history(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_price_history_date ON price_history(date)",
            "CREATE INDEX IF NOT EXISTS idx_price_history_source ON price_history(source)",
            # 余额历史表索引
            "CREATE INDEX IF NOT EXISTS idx_balance_history_asset ON balance_history(asset_id)",
            "CREATE INDEX IF NOT EXISTS idx_balance_history_timestamp ON balance_history(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_balance_history_date ON balance_history(date)",
            # 资产快照表索引
            "CREATE INDEX IF NOT EXISTS idx_asset_snapshots_asset ON asset_snapshots(asset_id)",
            "CREATE INDEX IF NOT EXISTS idx_asset_snapshots_timestamp ON asset_snapshots(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_asset_snapshots_date ON asset_snapshots(date)",
            # 价格缓存表索引
            "CREATE INDEX IF NOT EXISTS idx_price_cache_token ON price_cache(token_symbol, chain_name)",
            "CREATE INDEX IF NOT EXISTS idx_price_cache_expires ON price_cache(expires_at)",
            "CREATE INDEX IF NOT EXISTS idx_price_cache_coingecko ON price_cache(coingecko_id)",
            # 余额缓存表索引
            "CREATE INDEX IF NOT EXISTS idx_balance_cache_address ON balance_cache(address, chain_name)",
            "CREATE INDEX IF NOT EXISTS idx_balance_cache_token ON balance_cache(token_symbol)",
            "CREATE INDEX IF NOT EXISTS idx_balance_cache_expires ON balance_cache(expires_at)",
            # 系统配置表索引
            "CREATE INDEX IF NOT EXISTS idx_system_config_key ON system_config(config_key)",
        ]

        for index_sql in indexes:
            await conn.execute(index_sql)

    async def _init_system_config(self, conn):
        """初始化系统配置"""
        default_configs = [
            ("db_version", "2.0", "数据库版本"),
            ("last_migration", "2024-01-01", "最后迁移时间"),
            ("price_cache_enabled", "true", "是否启用价格缓存"),
            ("balance_cache_enabled", "true", "是否启用余额缓存"),
            ("auto_cleanup_enabled", "true", "是否启用自动清理"),
            ("cleanup_retention_days", "90", "缓存数据保留天数"),
        ]

        for key, value, description in default_configs:
            await conn.execute(
                """
                INSERT OR IGNORE INTO system_config (config_key, config_value, description)
                VALUES (?, ?, ?)
            """,
                (key, value, description),
            )

    async def _init_base_data(self, conn):
        """初始化基础数据（区块链和预定义代币）"""
        # 从配置中导入区块链信息
        from app.core.config import SUPPORTED_CHAINS, PREDEFINED_TOKENS

        logger.info("开始初始化区块链配置...")

        # 初始化区块链配置
        for chain_name, chain_config in SUPPORTED_CHAINS.items():
            # 检查区块链是否已存在
            async with conn.execute(
                "SELECT id FROM blockchains WHERE name = ?", (chain_name,)
            ) as cursor:
                existing = await cursor.fetchone()

            if not existing:
                # 插入新的区块链配置
                await conn.execute(
                    """
                    INSERT INTO blockchains (
                        name, display_name, rpc_url, 
                        explorer_url, chain_type, is_active
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        chain_config["name"],
                        chain_config["display_name"],
                        chain_config["rpc_url"],
                        chain_config.get("explorer_url", ""),
                        chain_config.get("chain_type", "evm"),
                        1,  # is_active = True
                    ),
                )
                logger.info(f"添加区块链配置: {chain_config['display_name']}")
            else:
                # 更新现有配置
                await conn.execute(
                    """
                    UPDATE blockchains SET 
                        display_name = ?, rpc_url = ?,
                        explorer_url = ?, chain_type = ?, is_active = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE name = ?
                """,
                    (
                        chain_config["display_name"],
                        chain_config["rpc_url"],
                        chain_config.get("explorer_url", ""),
                        chain_config.get("chain_type", "evm"),
                        1,  # is_active = True
                        chain_name,
                    ),
                )
                logger.info(f"更新区块链配置: {chain_config['display_name']}")

        # 获取区块链ID映射
        blockchain_map = {}
        async with conn.execute("SELECT id, name FROM blockchains") as cursor:
            async for row in cursor:
                blockchain_map[row["name"]] = row["id"]

        # 初始化预定义代币
        total_tokens_added = 0
        logger.info("开始初始化预定义代币...")

        for chain_name, tokens in PREDEFINED_TOKENS.items():
            blockchain_id = blockchain_map.get(chain_name)
            if not blockchain_id:
                logger.warning(f"跳过区块链 {chain_name}，未找到对应的区块链ID")
                continue

            for symbol, token_data in tokens.items():
                try:
                    await conn.execute(
                        """
                        INSERT OR REPLACE INTO tokens 
                        (symbol, name, blockchain_id, contract_address, decimals, coingecko_id, is_predefined)
                        VALUES (?, ?, ?, ?, ?, ?, 1)
                    """,
                        (
                            token_data["symbol"],
                            token_data["name"],
                            blockchain_id,
                            token_data.get("contract_address"),
                            token_data.get("decimals", 18),
                            token_data.get("coingecko_id"),
                        ),
                    )
                    total_tokens_added += 1

                    # 记录原生代币信息
                    if token_data.get("is_native", False):
                        logger.info(
                            f"添加原生代币: {token_data['symbol']} on {chain_name}"
                        )
                    else:
                        logger.debug(
                            f"添加代币: {token_data['symbol']} on {chain_name}"
                        )

                except Exception as e:
                    logger.error(
                        f"添加代币失败 {token_data['symbol']} on {chain_name}: {e}"
                    )

        await conn.commit()


# 全局数据库管理器实例
db_manager = DatabaseManager()

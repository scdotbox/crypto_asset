"""
应用配置文件
"""

import os
from typing import Optional, Dict, Any


class Settings:
    """应用设置类"""

    # 基础配置
    api_title: str = "加密货币资产管理 API"
    api_version: str = "1.0.0"
    api_description: str = "一个用于管理加密货币资产的 RESTful API"

    # 服务器配置
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8010"))
    debug: bool = os.getenv("DEBUG", "False").lower() == "true"

    # 数据存储配置
    data_dir: str = os.getenv("DATA_DIR", "../../data")

    # 传统方案配置
    traditional_mode_enabled: bool = True
    coingecko_api_url: str = "https://api.coingecko.com/api/v3"
    coingecko_api_key: str = os.getenv("COINGECKO_API_KEY", "")

    # 价格服务配置
    price_cache_ttl: int = 300  # 价格缓存TTL（秒），默认5分钟
    price_batch_size: int = 10  # 批量查询代币数量
    price_rate_limit_delay: float = 2.0  # API请求间隔（秒），减少对CoinGecko API的压力
    price_max_retries: int = 3  # 最大重试次数
    price_retry_base_delay: float = 1.0  # 重试基础延迟（秒）

    # 通用请求配置
    request_timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0

    # 通用缓存配置
    cache_enabled: bool = True
    cache_ttl: int = 300  # 5分钟

    history_cache_enabled: bool = True
    history_retention_years: int = int(
        os.getenv("HISTORY_RETENTION_YEARS", "3")
    )  # 历史数据保留年数，默认3年
    history_interval_hours: int = int(
        os.getenv("HISTORY_INTERVAL_HOURS", "1")
    )  # 历史数据采集间隔（小时），默认1小时
    history_auto_update_enabled: bool = (
        os.getenv("HISTORY_AUTO_UPDATE", "True").lower() == "true"
    )  # 是否启用自动更新
    history_batch_size: int = int(
        os.getenv("HISTORY_BATCH_SIZE", "100")
    )  # 历史数据批量处理大小
    history_max_gap_hours: int = int(
        os.getenv("HISTORY_MAX_GAP_HOURS", "24")
    )  # 允许的最大数据缺口（小时）
    history_data_dir: str = os.path.join(data_dir, "history")  # 历史数据目录

    # 日志配置
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    log_file: str = os.getenv("LOG_FILE", "app.log")

    # 数据聚合层配置
    # 多链数据提供商API密钥
    covalent_api_key: str = os.getenv("COVALENT_API_KEY", "")
    zerion_api_key: str = os.getenv("ZERION_API_KEY", "")
    zapper_api_key: str = os.getenv("ZAPPER_API_KEY", "")
    alchemy_api_key: str = os.getenv("ALCHEMY_API_KEY", "")
    debank_api_key: str = os.getenv("DEBANK_API_KEY", "")
    bitquery_api_key: str = os.getenv("BITQUERY_API_KEY", "")
    mobula_api_key: str = os.getenv("MOBULA_API_KEY", "")
    moralis_api_key: str = os.getenv("MORALIS_API_KEY", "")
    blockvision_api_key: str = os.getenv("BLOCKVISION_API_KEY", "")

    # 数据聚合策略配置
    data_aggregator_enabled: bool = (
        os.getenv("DATA_AGGREGATOR_ENABLED", "True").lower() == "true"
    )
    fallback_to_blockchain_service: bool = (
        os.getenv("FALLBACK_TO_BLOCKCHAIN_SERVICE", "True").lower() == "true"
    )
    # 使用通用配置，避免重复
    provider_timeout_seconds: int = int(
        os.getenv("PROVIDER_TIMEOUT_SECONDS", str(request_timeout))
    )

    # 代币发现机制配置
    token_discovery_enabled: bool = (
        os.getenv("TOKEN_DISCOVERY_ENABLED", "True").lower() == "true"
    )
    token_discovery_min_value_usd: float = float(
        os.getenv("TOKEN_DISCOVERY_MIN_VALUE_USD", "0.01")
    )
    token_discovery_include_zero_balance: bool = (
        os.getenv("TOKEN_DISCOVERY_INCLUDE_ZERO_BALANCE", "False").lower() == "true"
    )
    manual_token_addition_enabled: bool = (
        os.getenv("MANUAL_TOKEN_ADDITION_ENABLED", "True").lower() == "true"
    )

    # 数据提供商优先级配置
    primary_providers: list = os.getenv("PRIMARY_PROVIDERS", "covalent,mobula").split(
        ","
    )
    secondary_providers: list = os.getenv(
        "SECONDARY_PROVIDERS", "zerion,zapper,alchemy,debank"
    ).split(",")
    fallback_providers: list = os.getenv(
        "FALLBACK_PROVIDERS", "bitquery,moralis"
    ).split(",")


SUPPORTED_CHAINS = {
    "ethereum": {
        "name": "ethereum",
        "display_name": "Ethereum",
        "explorer_url": "https://etherscan.io",
        "rpc_url": os.getenv("ETHEREUM_RPC_URL", "https://eth.llamarpc.com"),
        "chain_type": "evm",
    },
    "arbitrum": {
        "name": "arbitrum",
        "display_name": "Arbitrum One",
        "explorer_url": "https://arbiscan.io",
        "rpc_url": os.getenv("ARBITRUM_RPC_URL", "https://arb1.arbitrum.io/rpc"),
        "chain_type": "evm",
    },
    "base": {
        "name": "base",
        "display_name": "Base",
        "explorer_url": "https://basescan.org",
        "rpc_url": os.getenv("BASE_RPC_URL", "https://mainnet.base.org"),
        "chain_type": "evm",
    },
    "polygon": {
        "name": "polygon",
        "display_name": "Polygon",
        "explorer_url": "https://polygonscan.com",
        "rpc_url": os.getenv("POLYGON_RPC_URL", "https://polygon-rpc.com"),
        "chain_type": "evm",
    },
    "bsc": {
        "name": "bsc",
        "display_name": "BNB Smart Chain",
        "explorer_url": "https://bscscan.com",
        "rpc_url": os.getenv("BSC_RPC_URL", "https://bsc-dataseed.binance.org"),
        "chain_type": "evm",
        "backup_rpc_urls": [
            "https://bsc-dataseed1.defibit.io",
            "https://bsc-dataseed1.ninicoin.io",
            "https://bsc-dataseed2.defibit.io",
            "https://bsc-dataseed3.defibit.io",
            "https://bsc-dataseed4.defibit.io",
            "https://bsc-dataseed2.ninicoin.io",
            "https://bsc-dataseed3.ninicoin.io",
            "https://bsc-dataseed4.ninicoin.io",
            "https://bsc-dataseed1.binance.org",
            "https://bsc-dataseed2.binance.org",
            "https://bsc-dataseed3.binance.org",
            "https://bsc-dataseed4.binance.org",
        ],
        "max_retries": 3,
        "base_delay": 1,
        "rate_limit_delay": 10,
        "chain_id": 56,
    },
    "solana": {
        "name": "solana",
        "display_name": "Solana",
        "explorer_url": "https://solscan.io",
        "rpc_url": os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com"),
        "chain_type": "solana",
        "backup_rpc_urls": [
            "https://solana-api.projectserum.com",
            "https://rpc.ankr.com/solana",
            "https://solana-mainnet.g.alchemy.com/v2/demo",
            "https://api.mainnet-beta.solana.com",
            "https://mainnet.helius-rpc.com/?api-key=demo",
        ],
        "max_retries": 3,
        "base_delay": 2,
        "rate_limit_delay": 30,
    },
    "sui": {
        "name": "sui",
        "display_name": "Sui",
        "explorer_url": "https://suiscan.xyz",
        "rpc_url": "https://fullnode.mainnet.sui.io",
        "chain_type": "sui",
    },
    "bitcoin": {
        "name": "bitcoin",
        "display_name": "Bitcoin",
        "explorer_url": "https://blockstream.info",
        "rpc_url": "https://blockstream.info/api",
        "chain_type": "bitcoin",
    },
}

# 统一的代币库配置（包含原生代币和其他代币）
PREDEFINED_TOKENS = {
    "ethereum": {
        # 原生代币
        "ETH": {
            "symbol": "ETH",
            "name": "Ethereum",
            "contract_address": None,  # 原生代币无合约地址
            "decimals": 18,
            "coingecko_id": "ethereum",
            "is_native": True,
        },
        # 其他代币可以在这里添加
    },
    "arbitrum": {
        # 原生代币（Arbitrum使用ETH作为原生代币）
        "ETH": {
            "symbol": "ETH",
            "name": "Ethereum",
            "contract_address": None,
            "decimals": 18,
            "coingecko_id": "ethereum",
            "is_native": True,
        },
        "USDC": {
            "symbol": "USDC",
            "name": "USD Coin",
            "contract_address": "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
            "decimals": 6,
            "coingecko_id": "usd-coin",
            "is_native": False,
        },
        "USDT": {
            "symbol": "USDT",
            "name": "Tether USD",
            "contract_address": "0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9",
            "decimals": 6,
            "coingecko_id": "tether",
            "is_native": False,
        },
    },
    "base": {
        # 原生代币（Base使用ETH作为原生代币）
        "ETH": {
            "symbol": "ETH",
            "name": "Ethereum",
            "contract_address": None,
            "decimals": 18,
            "coingecko_id": "ethereum",
            "is_native": True,
        },
        "USDC": {
            "symbol": "USDC",
            "name": "USD Coin",
            "contract_address": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
            "decimals": 6,
            "coingecko_id": "usd-coin",
            "is_native": False,
        },
        "USDT": {
            "symbol": "USDT",
            "name": "Tether USD",
            "contract_address": "0xfde4C96c8593536E31F229EA8f37b2ADa2699bb2",
            "decimals": 6,
            "coingecko_id": "tether",
            "is_native": False,
        },
    },
    "polygon": {
        # 原生代币
        "MATIC": {
            "symbol": "MATIC",
            "name": "Polygon",
            "contract_address": None,
            "decimals": 18,
            "coingecko_id": "matic-network",
            "is_native": True,
        },
    },
    "bsc": {
        # 原生代币
        "BNB": {
            "symbol": "BNB",
            "name": "BNB",
            "contract_address": None,
            "decimals": 18,
            "coingecko_id": "binancecoin",
            "is_native": True,
        },
        # 稳定币
        "USDT": {
            "symbol": "USDT",
            "name": "Tether USD",
            "contract_address": "0x55d398326f99059fF775485246999027B3197955",
            "decimals": 18,
            "coingecko_id": "tether",
            "is_native": False,
        },
        "USDC": {
            "symbol": "USDC",
            "name": "USD Coin",
            "contract_address": "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
            "decimals": 18,
            "coingecko_id": "usd-coin",
            "is_native": False,
        },
        "BUSD": {
            "symbol": "BUSD",
            "name": "Binance USD",
            "contract_address": "0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56",
            "decimals": 18,
            "coingecko_id": "binance-usd",
            "is_native": False,
        },
        "USDF": {
            "symbol": "USDF",
            "name": "USD Fiat",
            "contract_address": "0x05faf555522Fa3F93959F86B41A3808666093210",
            "decimals": 18,
            "coingecko_id": "usd-fiat",
            "is_native": False,
        },
        # 流动性质押代币
        "ASBNB": {
            "symbol": "ASBNB",
            "name": "Ankr Staked BNB",
            "contract_address": "0x52F24a5e03aee338Da5fd9Df68D2b6FAe1178827",
            "decimals": 18,
            "coingecko_id": "ankr-staked-bnb",
            "is_native": False,
        },
        "STKBNB": {
            "symbol": "STKBNB",
            "name": "Staked BNB",
            "contract_address": "0xc2E9d07F66A89c44062459A47a0D2Dc038E4fb16",
            "decimals": 18,
            "coingecko_id": "staked-bnb",
            "is_native": False,
        },
        # DeFi 代币
        "CAKE": {
            "symbol": "CAKE",
            "name": "PancakeSwap Token",
            "contract_address": "0x0E09FaBB73Bd3Ade0a17ECC321fD13a19e81cE82",
            "decimals": 18,
            "coingecko_id": "pancakeswap-token",
            "is_native": False,
        },
        "VENUS": {
            "symbol": "XVS",
            "name": "Venus",
            "contract_address": "0xcF6BB5389c92Bdda8a3747Ddb454cB7a64626C63",
            "decimals": 18,
            "coingecko_id": "venus",
            "is_native": False,
        },
        "ALPACA": {
            "symbol": "ALPACA",
            "name": "Alpaca Finance",
            "contract_address": "0x8F0528cE5eF7B51152A59745bEfDD91D97091d2F",
            "decimals": 18,
            "coingecko_id": "alpaca-finance",
            "is_native": False,
        },
        # 跨链代币
        "ETH": {
            "symbol": "ETH",
            "name": "Ethereum Token",
            "contract_address": "0x2170Ed0880ac9A755fd29B2688956BD959F933F8",
            "decimals": 18,
            "coingecko_id": "ethereum",
            "is_native": False,
        },
        "BTC": {
            "symbol": "BTCB",
            "name": "Bitcoin BEP2",
            "contract_address": "0x7130d2A12B9BCbFAe4f2634d864A1Ee1Ce3Ead9c",
            "decimals": 18,
            "coingecko_id": "bitcoin",
            "is_native": False,
        },
        "ADA": {
            "symbol": "ADA",
            "name": "Cardano Token",
            "contract_address": "0x3EE2200Efb3400fAbB9AacF31297cBdD1d435D47",
            "decimals": 18,
            "coingecko_id": "cardano",
            "is_native": False,
        },
        "DOT": {
            "symbol": "DOT",
            "name": "Polkadot Token",
            "contract_address": "0x7083609fCE4d1d8Dc0C979AAb8c869Ea2C873402",
            "decimals": 18,
            "coingecko_id": "polkadot",
            "is_native": False,
        },
        # Meme 代币
        "DOGE": {
            "symbol": "DOGE",
            "name": "Dogecoin",
            "contract_address": "0xbA2aE424d960c26247Dd6c32edC70B295c744C43",
            "decimals": 8,
            "coingecko_id": "dogecoin",
            "is_native": False,
        },
        "SHIB": {
            "symbol": "SHIB",
            "name": "SHIBA INU",
            "contract_address": "0x2859e4544C4bB03966803b044A93563Bd2D0DD4D",
            "decimals": 18,
            "coingecko_id": "shiba-inu",
            "is_native": False,
        },
        # 游戏代币
        "AXS": {
            "symbol": "AXS",
            "name": "Axie Infinity Shard",
            "contract_address": "0x715D400F88537b51125F2cc33B5b1b8b6b5b8c3",
            "decimals": 18,
            "coingecko_id": "axie-infinity",
            "is_native": False,
        },
        "SLP": {
            "symbol": "SLP",
            "name": "Smooth Love Potion",
            "contract_address": "0x070a08BeEF8d36734dD67A491202fF35a6A16d97",
            "decimals": 0,
            "coingecko_id": "smooth-love-potion",
            "is_native": False,
        },
    },
    "solana": {
        # 原生代币
        "SOL": {
            "symbol": "SOL",
            "name": "Solana",
            "contract_address": None,
            "decimals": 9,
            "coingecko_id": "solana",
            "is_native": True,
        },
        "USDC": {
            "symbol": "USDC",
            "name": "USD Coin",
            "contract_address": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            "decimals": 6,
            "coingecko_id": "usd-coin",
            "is_native": False,
        },
        "USDT": {
            "symbol": "USDT",
            "name": "Tether USD",
            "contract_address": "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
            "decimals": 6,
            "coingecko_id": "tether",
            "is_native": False,
        },
        "JUP": {
            "symbol": "JUP",
            "name": "Jupiter",
            "contract_address": "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
            "decimals": 6,
            "coingecko_id": "jupiter-exchange-solana",
            "is_native": False,
        },
        "RAY": {
            "symbol": "RAY",
            "name": "Raydium",
            "contract_address": "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R",
            "decimals": 6,
            "coingecko_id": "raydium",
            "is_native": False,
        },
        "BONK": {
            "symbol": "BONK",
            "name": "Bonk",
            "contract_address": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
            "decimals": 5,
            "coingecko_id": "bonk",
            "is_native": False,
        },
        "WIF": {
            "symbol": "WIF",
            "name": "dogwifhat",
            "contract_address": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
            "decimals": 6,
            "coingecko_id": "dogwifhat",
            "is_native": False,
        },
        "PYTH": {
            "symbol": "PYTH",
            "name": "Pyth Network",
            "contract_address": "HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3",
            "decimals": 6,
            "coingecko_id": "pyth-network",
            "is_native": False,
        },
        "JTO": {
            "symbol": "JTO",
            "name": "Jito",
            "contract_address": "jtojtomepa8beP8AuQc6eXt5FriJwfFMwQx2v2f9mCL",
            "decimals": 9,
            "coingecko_id": "jito-governance-token",
            "is_native": False,
        },
        "ORCA": {
            "symbol": "ORCA",
            "name": "Orca",
            "contract_address": "orcaEKTdK7LKz57vaAYr9QeNsVEPfiu6QeMU1kektZE",
            "decimals": 6,
            "coingecko_id": "orca",
            "is_native": False,
        },
        "SLAYER": {
            "symbol": "SLAYER",
            "name": "Solayer",
            "contract_address": "LAYER4xPpTCb3QL8S9u41EAhAX7mhBn8Q6xMTwY2Yzc",
            "decimals": 9,
            "coingecko_id": "solayer",
            "is_native": False,
        },
        "POPCAT": {
            "symbol": "POPCAT",
            "name": "Popcat",
            "contract_address": "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr",
            "decimals": 9,
            "coingecko_id": "popcat",
            "is_native": False,
        },
        "MEW": {
            "symbol": "MEW",
            "name": "cat in a dogs world",
            "contract_address": "MEW1gQWJ3nEXg2qgERiKu7FAFj79PHvQVREQUzScPP5",
            "decimals": 5,
            "coingecko_id": "cat-in-a-dogs-world",
            "is_native": False,
        },
        "GRASS": {
            "symbol": "GRASS",
            "name": "Grass",
            "contract_address": "Grass7B4RdKfBCjTKgSqnXkqjwiGvQyFbuSCUJr3XXjs",
            "decimals": 9,
            "coingecko_id": "grass",
            "is_native": False,
        },
        "HONEY": {
            "symbol": "HONEY",
            "name": "Hivemapper",
            "contract_address": "4vMsoUT2BWatFweudnQM1xedRLfJgJ7hswhcpz4xgBTy",
            "decimals": 9,
            "coingecko_id": "hivemapper",
            "is_native": False,
        },
        "PENGU": {
            "symbol": "PENGU",
            "name": "Pudgy Penguins",
            "contract_address": "2zMMhcVQEXDtdE6vsFS7S7D5oUodfJHE8vd1gnBouauv",
            "decimals": 6,
            "coingecko_id": "pudgy-penguins",
            "is_native": False,
        },
    },
    "sui": {
        "SUI": {
            "symbol": "SUI",
            "name": "Sui",
            "contract_address": None,
            "decimals": 9,
            "coingecko_id": "sui",
            "is_native": True,
        },
        "USDC": {
            "symbol": "USDC",
            "name": "USD Coin",
            "contract_address": "0xdba34672e30cb065b1f93e3ab55318768fd6fef66c15942c9f7cb846e2f900e7::usdc::USDC",
            "decimals": 6,
            "coingecko_id": "usd-coin",
            "is_native": False,
        },
        "USDT": {
            "symbol": "USDT",
            "name": "Tether USD",
            "contract_address": "0xc060006111016b8a020ad5b33834984a437aaa7d3c74c18e09a95d48aceab08c::coin::COIN",
            "decimals": 6,
            "coingecko_id": "tether",
            "is_native": False,
        },
    },
    "bitcoin": {
        "BTC": {
            "symbol": "BTC",
            "name": "Bitcoin",
            "contract_address": None,
            "decimals": 8,
            "coingecko_id": "bitcoin",
            "is_native": True,
        },
    },
}

# 创建设置实例
settings = Settings()

# 确保数据目录存在
os.makedirs(settings.data_dir, exist_ok=True)

# 确保历史数据目录存在
os.makedirs(settings.history_data_dir, exist_ok=True)


def get_native_token(chain_name: str) -> Optional[Dict[str, Any]]:
    """
    获取指定链的原生代币信息

    Args:
        chain_name: 链名称

    Returns:
        Optional[Dict[str, Any]]: 原生代币信息，如果未找到则返回None
    """
    if chain_name not in PREDEFINED_TOKENS:
        return None

    for token_symbol, token_info in PREDEFINED_TOKENS[chain_name].items():
        if token_info.get("is_native", False):
            return token_info

    return None


def get_native_token_symbol(chain_name: str) -> Optional[str]:
    """
    获取指定链的原生代币符号

    Args:
        chain_name: 链名称

    Returns:
        Optional[str]: 原生代币符号，如果未找到则返回None
    """
    native_token = get_native_token(chain_name)
    return native_token["symbol"] if native_token else None


def get_all_tokens_for_chain(chain_name: str) -> Dict[str, Any]:
    """
    获取指定链的所有代币信息

    Args:
        chain_name: 链名称

    Returns:
        Dict[str, Any]: 该链的所有代币信息
    """
    return PREDEFINED_TOKENS.get(chain_name, {})


def get_token_info(chain_name: str, token_symbol: str) -> Optional[Dict[str, Any]]:
    """
    获取指定链上指定代币的信息

    Args:
        chain_name: 链名称
        token_symbol: 代币符号

    Returns:
        Optional[Dict[str, Any]]: 代币信息，如果未找到则返回None
    """
    chain_tokens = PREDEFINED_TOKENS.get(chain_name, {})
    return chain_tokens.get(token_symbol)

"""
具体的数据提供商实现

包含各种多链和特定链的数据提供商，如Zerion、Zapper、DeBank、Bitquery、Alchemy、Moralis等
"""

from typing import Dict, List, Optional, Any

from app.core.logger import get_logger
from app.core.config import settings
from app.models.asset_models import DiscoveredToken
from app.services.data_aggregator import (
    BaseDataProvider,
    DataProviderType,
    DataProviderPriority,
)

logger = get_logger(__name__)


class ZerionProvider(BaseDataProvider):
    """Zerion API 提供商 - 专注于钱包和DeFi数据"""

    def __init__(self):
        super().__init__(
            "Zerion", DataProviderType.MULTI_CHAIN, DataProviderPriority.SECONDARY
        )
        self.api_key = getattr(settings, "zerion_api_key", "")
        self.base_url = "https://api.zerion.io/v1"
        self.supported_chains = {
            "ethereum": "ethereum",
            "polygon": "polygon",
            "bsc": "binance-smart-chain",
            "arbitrum": "arbitrum",
            "base": "base",
            "solana": "solana",
        }
        self.rate_limit_delay = 1.0

    def supports_chain(self, chain_name: str) -> bool:
        return chain_name.lower() in self.supported_chains

    async def get_wallet_assets(
        self, address: str, chain_name: str, include_zero_balance: bool = False
    ) -> List[DiscoveredToken]:
        """获取钱包资产"""
        if not self.supports_chain(chain_name) or not self.api_key:
            return []

        try:
            await self._rate_limit()

            headers = {
                "Authorization": f"Basic {self.api_key}",
                "Content-Type": "application/json",
            }

            url = f"{self.base_url}/wallets/{address}/positions"
            params = {
                "filter[chain_ids]": self.supported_chains[chain_name.lower()],
                "currency": "usd",
            }

            response = await self.http_client.get(url, headers=headers, params=params)
            response.raise_for_status()

            data = response.json()
            tokens = []

            if data.get("data"):
                for position in data["data"]:
                    if position.get("type") == "wallet":
                        attributes = position.get("attributes", {})
                        fungible_info = attributes.get("fungible_info", {})

                        for implementation in fungible_info.get("implementations", []):
                            balance = float(
                                implementation.get("quantity", {}).get("float", 0)
                            )

                            if not include_zero_balance and balance == 0:
                                continue

                            token_info = implementation.get("fungible_info", {})
                            token = DiscoveredToken(
                                symbol=token_info.get("symbol", "UNKNOWN"),
                                name=token_info.get("name", ""),
                                contract_address=implementation.get("address"),
                                balance=balance,
                                decimals=token_info.get("decimals", 18),
                                is_native=implementation.get("address") is None,
                                price_usdc=implementation.get("price"),
                                value_usdc=implementation.get("value"),
                            )
                            tokens.append(token)

            self.reset_errors()
            return tokens

        except Exception as e:
            self.record_error()
            logger.error(f"Zerion获取钱包资产失败 {address} on {chain_name}: {e}")
            return []

    async def get_token_balance(
        self, address: str, token_contract: Optional[str], chain_name: str
    ) -> float:
        """获取代币余额"""
        assets = await self.get_wallet_assets(
            address, chain_name, include_zero_balance=True
        )

        for asset in assets:
            if token_contract is None and asset.is_native:
                return asset.balance
            elif (
                token_contract
                and asset.contract_address
                and asset.contract_address.lower() == token_contract.lower()
            ):
                return asset.balance

        return 0.0

    async def get_token_price(
        self, token_symbol: str, chain_name: str
    ) -> Optional[float]:
        """获取代币价格"""
        return None


class ZapperProvider(BaseDataProvider):
    """Zapper API 提供商 - 专注于DeFi协议数据聚合"""

    def __init__(self):
        super().__init__(
            "Zapper", DataProviderType.MULTI_CHAIN, DataProviderPriority.SECONDARY
        )
        self.api_key = getattr(settings, "zapper_api_key", "")
        self.base_url = "https://api.zapper.fi/v2"
        self.supported_chains = {
            "ethereum": "ethereum",
            "polygon": "polygon",
            "bsc": "binance-smart-chain",
            "arbitrum": "arbitrum",
            "base": "base",
        }
        self.rate_limit_delay = 1.0

    def supports_chain(self, chain_name: str) -> bool:
        return chain_name.lower() in self.supported_chains

    async def get_wallet_assets(
        self, address: str, chain_name: str, include_zero_balance: bool = False
    ) -> List[DiscoveredToken]:
        """获取钱包资产"""
        if not self.supports_chain(chain_name) or not self.api_key:
            return []

        try:
            await self._rate_limit()

            headers = {
                "Authorization": f"Basic {self.api_key}",
                "Content-Type": "application/json",
            }

            url = f"{self.base_url}/balances"
            params = {
                "addresses[]": address,
                "networks[]": self.supported_chains[chain_name.lower()],
            }

            response = await self.http_client.get(url, headers=headers, params=params)
            response.raise_for_status()

            data = response.json()
            tokens = []

            if data.get(address):
                for product in data[address]:
                    for asset in product.get("assets", []):
                        balance = float(asset.get("balance", 0))

                        if not include_zero_balance and balance == 0:
                            continue

                        token = DiscoveredToken(
                            symbol=asset.get("symbol", "UNKNOWN"),
                            name=asset.get("name", ""),
                            contract_address=asset.get("address"),
                            balance=balance,
                            decimals=asset.get("decimals", 18),
                            is_native=asset.get("address") is None,
                            price_usdc=asset.get("price"),
                            value_usdc=asset.get("balanceUSD"),
                        )
                        tokens.append(token)

            self.reset_errors()
            return tokens

        except Exception as e:
            self.record_error()
            logger.error(f"Zapper获取钱包资产失败 {address} on {chain_name}: {e}")
            return []

    async def get_token_balance(
        self, address: str, token_contract: Optional[str], chain_name: str
    ) -> float:
        """获取代币余额"""
        assets = await self.get_wallet_assets(
            address, chain_name, include_zero_balance=True
        )

        for asset in assets:
            if token_contract is None and asset.is_native:
                return asset.balance
            elif (
                token_contract
                and asset.contract_address
                and asset.contract_address.lower() == token_contract.lower()
            ):
                return asset.balance

        return 0.0

    async def get_token_price(
        self, token_symbol: str, chain_name: str
    ) -> Optional[float]:
        """获取代币价格"""
        return None


class AlchemyProvider(BaseDataProvider):
    """Alchemy API 提供商 - 高性能区块链基础设施"""

    def __init__(self):
        super().__init__(
            "Alchemy", DataProviderType.MULTI_CHAIN, DataProviderPriority.SECONDARY
        )
        self.api_key = getattr(settings, "alchemy_api_key", "")
        self.supported_chains = {
            "ethereum": "eth-mainnet",
            "polygon": "polygon-mainnet",
            "arbitrum": "arb-mainnet",
            "base": "base-mainnet",
        }
        self.rate_limit_delay = 0.5

    def supports_chain(self, chain_name: str) -> bool:
        return chain_name.lower() in self.supported_chains

    async def get_wallet_assets(
        self, address: str, chain_name: str, include_zero_balance: bool = False
    ) -> List[DiscoveredToken]:
        """获取钱包资产"""
        if not self.supports_chain(chain_name) or not self.api_key:
            return []

        try:
            await self._rate_limit()

            chain_id = self.supported_chains[chain_name.lower()]
            url = f"https://{chain_id}.g.alchemy.com/v2/{self.api_key}"

            # 获取代币余额
            payload = {
                "id": 1,
                "jsonrpc": "2.0",
                "method": "alchemy_getTokenBalances",
                "params": [address],
            }

            headers = {"Content-Type": "application/json"}
            response = await self.http_client.post(url, json=payload, headers=headers)
            response.raise_for_status()

            data = response.json()
            tokens = []

            if data.get("result") and data["result"].get("tokenBalances"):
                for token_balance in data["result"]["tokenBalances"]:
                    balance_hex = token_balance.get("tokenBalance", "0x0")
                    if balance_hex == "0x0" and not include_zero_balance:
                        continue

                    balance = int(balance_hex, 16) if balance_hex != "0x0" else 0

                    # 获取代币元数据
                    metadata_payload = {
                        "id": 1,
                        "jsonrpc": "2.0",
                        "method": "alchemy_getTokenMetadata",
                        "params": [token_balance["contractAddress"]],
                    }

                    metadata_response = await self.http_client.post(
                        url, json=metadata_payload, headers=headers
                    )
                    metadata = metadata_response.json().get("result", {})

                    decimals = metadata.get("decimals", 18)
                    balance_float = balance / (10**decimals) if balance > 0 else 0

                    if not include_zero_balance and balance_float == 0:
                        continue

                    token = DiscoveredToken(
                        symbol=metadata.get("symbol", "UNKNOWN"),
                        name=metadata.get("name", ""),
                        contract_address=token_balance["contractAddress"],
                        balance=balance_float,
                        decimals=decimals,
                        is_native=False,
                        price_usdc=None,
                        value_usdc=None,
                    )
                    tokens.append(token)

            self.reset_errors()
            return tokens

        except Exception as e:
            self.record_error()
            logger.error(f"Alchemy获取钱包资产失败 {address} on {chain_name}: {e}")
            return []

    async def get_token_balance(
        self, address: str, token_contract: Optional[str], chain_name: str
    ) -> float:
        """获取代币余额"""
        if not self.supports_chain(chain_name) or not self.api_key:
            return 0.0

        try:
            await self._rate_limit()

            chain_id = self.supported_chains[chain_name.lower()]
            url = f"https://{chain_id}.g.alchemy.com/v2/{self.api_key}"

            if token_contract is None:
                # 获取原生代币余额
                payload = {
                    "id": 1,
                    "jsonrpc": "2.0",
                    "method": "eth_getBalance",
                    "params": [address, "latest"],
                }
            else:
                # 获取ERC20代币余额
                payload = {
                    "id": 1,
                    "jsonrpc": "2.0",
                    "method": "alchemy_getTokenBalances",
                    "params": [address, [token_contract]],
                }

            headers = {"Content-Type": "application/json"}
            response = await self.http_client.post(url, json=payload, headers=headers)
            response.raise_for_status()

            data = response.json()

            if token_contract is None:
                # 原生代币余额
                balance_hex = data.get("result", "0x0")
                balance = int(balance_hex, 16) / (10**18)
                return balance
            else:
                # ERC20代币余额
                if data.get("result") and data["result"].get("tokenBalances"):
                    token_balance = data["result"]["tokenBalances"][0]
                    balance_hex = token_balance.get("tokenBalance", "0x0")

                    # 获取代币精度
                    metadata_payload = {
                        "id": 1,
                        "jsonrpc": "2.0",
                        "method": "alchemy_getTokenMetadata",
                        "params": [token_contract],
                    }

                    metadata_response = await self.http_client.post(
                        url, json=metadata_payload, headers=headers
                    )
                    metadata = metadata_response.json().get("result", {})
                    decimals = metadata.get("decimals", 18)

                    balance = (
                        int(balance_hex, 16) / (10**decimals)
                        if balance_hex != "0x0"
                        else 0
                    )
                    return balance

            return 0.0

        except Exception as e:
            self.record_error()
            logger.error(f"Alchemy获取代币余额失败 {address} on {chain_name}: {e}")
            return 0.0

    async def get_token_price(
        self, token_symbol: str, chain_name: str
    ) -> Optional[float]:
        """获取代币价格 - Alchemy主要提供基础设施服务，不提供价格数据"""
        return None


class MobulaProvider(BaseDataProvider):
    """Mobula API 提供商 - 专门针对Sui链的数据提供商"""

    def __init__(self):
        super().__init__(
            "Mobula", DataProviderType.CHAIN_SPECIFIC, DataProviderPriority.PRIMARY
        )
        self.api_key = getattr(settings, "mobula_api_key", "")
        self.base_url = "https://api.mobula.io/api/1"
        self.rate_limit_delay = 1.0

    def supports_chain(self, chain_name: str) -> bool:
        return chain_name.lower() == "sui"

    async def get_wallet_assets(
        self, address: str, chain_name: str, include_zero_balance: bool = False
    ) -> List[DiscoveredToken]:
        """获取Sui钱包资产"""
        if not self.supports_chain(chain_name) or not self.api_key:
            return []

        try:
            await self._rate_limit()

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            url = f"{self.base_url}/wallet/portfolio"
            params = {"wallet": address, "blockchains": "Sui"}

            response = await self.http_client.get(url, headers=headers, params=params)
            response.raise_for_status()

            data = response.json()
            tokens = []

            if data.get("data") and data["data"].get("assets"):
                for asset in data["data"]["assets"]:
                    balance = float(asset.get("balance", 0))

                    if not include_zero_balance and balance == 0:
                        continue

                    token = DiscoveredToken(
                        symbol=asset.get("symbol", "UNKNOWN"),
                        name=asset.get("name", ""),
                        contract_address=asset.get("contract"),
                        balance=balance,
                        decimals=asset.get("decimals", 9),
                        is_native=asset.get("symbol") == "SUI",
                        price_usdc=asset.get("price"),
                        value_usdc=asset.get("value"),
                    )
                    tokens.append(token)

            self.reset_errors()
            return tokens

        except Exception as e:
            self.record_error()
            logger.error(f"Mobula获取Sui钱包资产失败 {address}: {e}")
            return []

    async def get_token_balance(
        self, address: str, token_contract: Optional[str], chain_name: str
    ) -> float:
        """获取代币余额"""
        assets = await self.get_wallet_assets(
            address, chain_name, include_zero_balance=True
        )

        for asset in assets:
            if token_contract is None and asset.is_native:
                return asset.balance
            elif (
                token_contract
                and asset.contract_address
                and asset.contract_address.lower() == token_contract.lower()
            ):
                return asset.balance

        return 0.0

    async def get_token_price(
        self, token_symbol: str, chain_name: str
    ) -> Optional[float]:
        """获取代币价格"""
        if not self.supports_chain(chain_name) or not self.api_key:
            return None

        try:
            await self._rate_limit()

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            url = f"{self.base_url}/market/data"
            params = {"symbol": token_symbol, "blockchain": "Sui"}

            response = await self.http_client.get(url, headers=headers, params=params)
            response.raise_for_status()

            data = response.json()

            if data.get("data") and data["data"].get("price"):
                return float(data["data"]["price"])

            return None

        except Exception as e:
            self.record_error()
            logger.error(f"Mobula获取代币价格失败 {token_symbol}: {e}")
            return None


class DeBankProvider(BaseDataProvider):
    """DeBank API 提供商 - 专注于DeFi数据聚合"""

    def __init__(self):
        super().__init__(
            "DeBank", DataProviderType.MULTI_CHAIN, DataProviderPriority.SECONDARY
        )
        self.api_key = getattr(settings, "debank_api_key", "")
        self.base_url = "https://pro-openapi.debank.com/v1"
        self.supported_chains = {
            "ethereum": "eth",
            "polygon": "matic",
            "bsc": "bsc",
            "arbitrum": "arb",
            "base": "base",
        }
        self.rate_limit_delay = 1.0

    def supports_chain(self, chain_name: str) -> bool:
        return chain_name.lower() in self.supported_chains

    async def get_wallet_assets(
        self, address: str, chain_name: str, include_zero_balance: bool = False
    ) -> List[DiscoveredToken]:
        """获取钱包资产"""
        if not self.supports_chain(chain_name) or not self.api_key:
            return []

        try:
            await self._rate_limit()

            headers = {"AccessKey": self.api_key, "Content-Type": "application/json"}

            chain_id = self.supported_chains[chain_name.lower()]
            url = f"{self.base_url}/user/token_list"
            params = {"id": address, "chain_id": chain_id, "is_all": "true"}

            response = await self.http_client.get(url, headers=headers, params=params)
            response.raise_for_status()

            data = response.json()
            tokens = []

            for token_data in data:
                balance = float(token_data.get("amount", 0))

                if not include_zero_balance and balance == 0:
                    continue

                token = DiscoveredToken(
                    symbol=token_data.get("symbol", "UNKNOWN"),
                    name=token_data.get("name", ""),
                    contract_address=token_data.get("id"),
                    balance=balance,
                    decimals=token_data.get("decimals", 18),
                    is_native=token_data.get("id") == chain_id,
                    price_usdc=token_data.get("price"),
                    value_usdc=balance * token_data.get("price", 0)
                    if token_data.get("price")
                    else None,
                )
                tokens.append(token)

            self.reset_errors()
            return tokens

        except Exception as e:
            self.record_error()
            logger.error(f"DeBank获取钱包资产失败 {address} on {chain_name}: {e}")
            return []

    async def get_token_balance(
        self, address: str, token_contract: Optional[str], chain_name: str
    ) -> float:
        """获取代币余额"""
        assets = await self.get_wallet_assets(
            address, chain_name, include_zero_balance=True
        )

        for asset in assets:
            if token_contract is None and asset.is_native:
                return asset.balance
            elif (
                token_contract
                and asset.contract_address
                and asset.contract_address.lower() == token_contract.lower()
            ):
                return asset.balance

        return 0.0

    async def get_token_price(
        self, token_symbol: str, chain_name: str
    ) -> Optional[float]:
        """获取代币价格"""
        return None


class BitqueryProvider(BaseDataProvider):
    """Bitquery API 提供商 - 区块链数据分析平台"""

    def __init__(self):
        super().__init__(
            "Bitquery", DataProviderType.MULTI_CHAIN, DataProviderPriority.FALLBACK
        )
        self.api_key = getattr(settings, "bitquery_api_key", "")
        self.base_url = "https://graphql.bitquery.io"
        self.supported_chains = {
            "ethereum": "ethereum",
            "polygon": "matic",
            "bsc": "bsc",
            "arbitrum": "arbitrum",
            "solana": "solana",
        }
        self.rate_limit_delay = 2.0

    def supports_chain(self, chain_name: str) -> bool:
        return chain_name.lower() in self.supported_chains

    async def get_wallet_assets(
        self, address: str, chain_name: str, include_zero_balance: bool = False
    ) -> List[DiscoveredToken]:
        """获取钱包资产"""
        if not self.supports_chain(chain_name) or not self.api_key:
            return []

        try:
            await self._rate_limit()

            headers = {"X-API-KEY": self.api_key, "Content-Type": "application/json"}

            # 构建GraphQL查询
            if chain_name.lower() == "solana":
                query = self._build_solana_balance_query(address)
            else:
                query = self._build_evm_balance_query(address, chain_name)

            response = await self.http_client.post(
                self.base_url, json={"query": query}, headers=headers
            )
            response.raise_for_status()

            data = response.json()
            tokens = self._parse_bitquery_response(
                data, chain_name, include_zero_balance
            )

            self.reset_errors()
            return tokens

        except Exception as e:
            self.record_error()
            logger.error(f"Bitquery获取钱包资产失败 {address} on {chain_name}: {e}")
            return []

    def _build_evm_balance_query(self, address: str, chain_name: str) -> str:
        """构建EVM链的余额查询"""
        network = self.supported_chains[chain_name.lower()]
        return f"""
        {{
          {network}(network: {network}) {{
            address(address: {{is: "{address}"}}) {{
              balances {{
                currency {{
                  symbol
                  name
                  address
                  decimals
                }}
                value
              }}
            }}
          }}
        }}
        """

    def _build_solana_balance_query(self, address: str) -> str:
        """构建Solana链的余额查询"""
        return f"""
        {{
          solana(network: solana) {{
            address(address: {{is: "{address}"}}) {{
              balances {{
                currency {{
                  symbol
                  name
                  address
                  decimals
                }}
                value
              }}
            }}
          }}
        }}
        """

    def _parse_bitquery_response(
        self, data: dict, chain_name: str, include_zero_balance: bool
    ) -> List[DiscoveredToken]:
        """解析Bitquery响应数据"""
        tokens = []

        try:
            network = self.supported_chains[chain_name.lower()]
            balances = data.get("data", {}).get(network, {}).get("address", [])

            if balances:
                for balance_data in balances[0].get("balances", []):
                    currency = balance_data.get("currency", {})
                    balance = float(balance_data.get("value", 0))

                    if not include_zero_balance and balance == 0:
                        continue

                    token = DiscoveredToken(
                        symbol=currency.get("symbol", "UNKNOWN"),
                        name=currency.get("name", ""),
                        contract_address=currency.get("address"),
                        balance=balance,
                        decimals=currency.get("decimals", 18),
                        is_native=currency.get("address") is None,
                        price_usdc=None,
                        value_usdc=None,
                    )
                    tokens.append(token)

        except Exception as e:
            logger.error(f"解析Bitquery响应失败: {e}")

        return tokens

    async def get_token_balance(
        self, address: str, token_contract: Optional[str], chain_name: str
    ) -> float:
        """获取代币余额"""
        assets = await self.get_wallet_assets(
            address, chain_name, include_zero_balance=True
        )

        for asset in assets:
            if token_contract is None and asset.is_native:
                return asset.balance
            elif (
                token_contract
                and asset.contract_address
                and asset.contract_address.lower() == token_contract.lower()
            ):
                return asset.balance

        return 0.0

    async def get_token_price(
        self, token_symbol: str, chain_name: str
    ) -> Optional[float]:
        """获取代币价格"""
        return None


class MoralisProvider(BaseDataProvider):
    """Moralis API 提供商 - Web3开发平台"""

    def __init__(self):
        super().__init__(
            "Moralis", DataProviderType.MULTI_CHAIN, DataProviderPriority.FALLBACK
        )
        self.api_key = getattr(settings, "moralis_api_key", "")
        self.base_url = "https://deep-index.moralis.io/api/v2.2"
        self.supported_chains = {
            "ethereum": "0x1",
            "polygon": "0x89",
            "bsc": "0x38",
            "arbitrum": "0xa4b1",
            "base": "0x2105",
            "solana": "mainnet",
        }
        self.rate_limit_delay = 1.0

    def supports_chain(self, chain_name: str) -> bool:
        return chain_name.lower() in self.supported_chains

    async def get_wallet_assets(
        self, address: str, chain_name: str, include_zero_balance: bool = False
    ) -> List[DiscoveredToken]:
        """获取钱包资产"""
        if not self.supports_chain(chain_name) or not self.api_key:
            return []

        try:
            await self._rate_limit()

            headers = {"X-API-Key": self.api_key, "Content-Type": "application/json"}

            chain_id = self.supported_chains[chain_name.lower()]

            if chain_name.lower() == "solana":
                url = f"{self.base_url}/wallets/{address}/tokens"
                params = {"network": "mainnet"}
            else:
                url = f"{self.base_url}/{address}/erc20"
                params = {"chain": chain_id}

            response = await self.http_client.get(url, headers=headers, params=params)
            response.raise_for_status()

            data = response.json()

            if chain_name.lower() == "solana":
                tokens = self._parse_solana_response(data, include_zero_balance)
            else:
                tokens = self._parse_evm_response(data, include_zero_balance)

            self.reset_errors()
            return tokens

        except Exception as e:
            self.record_error()
            logger.error(f"Moralis获取钱包资产失败 {address} on {chain_name}: {e}")
            return []

    def _parse_evm_response(
        self, data: dict, include_zero_balance: bool
    ) -> List[DiscoveredToken]:
        """解析EVM链响应"""
        tokens = []

        for token_data in data:
            balance_raw = int(token_data.get("balance", 0))
            decimals = int(token_data.get("decimals", 18))
            balance = balance_raw / (10**decimals)

            if not include_zero_balance and balance == 0:
                continue

            token = DiscoveredToken(
                symbol=token_data.get("symbol", "UNKNOWN"),
                name=token_data.get("name", ""),
                contract_address=token_data.get("token_address"),
                balance=balance,
                decimals=decimals,
                is_native=False,
                price_usdc=None,
                value_usdc=None,
            )
            tokens.append(token)

        return tokens

    def _parse_solana_response(
        self, data: dict, include_zero_balance: bool
    ) -> List[DiscoveredToken]:
        """解析Solana链响应"""
        tokens = []

        for token_data in data:
            balance = float(token_data.get("amount", 0))

            if not include_zero_balance and balance == 0:
                continue

            token = DiscoveredToken(
                symbol=token_data.get("symbol", "UNKNOWN"),
                name=token_data.get("name", ""),
                contract_address=token_data.get("mint"),
                balance=balance,
                decimals=token_data.get("decimals", 9),
                is_native=token_data.get("symbol") == "SOL",
                price_usdc=None,
                value_usdc=None,
            )
            tokens.append(token)

        return tokens

    async def get_token_balance(
        self, address: str, token_contract: Optional[str], chain_name: str
    ) -> float:
        """获取代币余额"""
        assets = await self.get_wallet_assets(
            address, chain_name, include_zero_balance=True
        )

        for asset in assets:
            if token_contract is None and asset.is_native:
                return asset.balance
            elif (
                token_contract
                and asset.contract_address
                and asset.contract_address.lower() == token_contract.lower()
            ):
                return asset.balance

        return 0.0

    async def get_token_price(
        self, token_symbol: str, chain_name: str
    ) -> Optional[float]:
        """获取代币价格"""
        return None


class BlockVisionSuiProvider(BaseDataProvider):
    """BlockVision Sui Indexing API 提供商 - 专门针对Sui链的高精度数据提供商"""

    def __init__(self):
        super().__init__(
            "BlockVision", DataProviderType.CHAIN_SPECIFIC, DataProviderPriority.PRIMARY
        )
        self.api_key = getattr(settings, "blockvision_api_key", "")
        self.base_url = "https://api.blockvision.org/v2"
        self.rate_limit_delay = 2.0  # 增加速率限制延迟以避免429错误

    def supports_chain(self, chain_name: str) -> bool:
        return chain_name.lower() == "sui"

    async def get_wallet_assets(
        self, address: str, chain_name: str, include_zero_balance: bool = False
    ) -> List[DiscoveredToken]:
        """获取Sui钱包资产 - 使用BlockVision Indexing API"""
        if not self.supports_chain(chain_name):
            return []

        try:
            await self._rate_limit()

            headers = {"Content-Type": "application/json"}

            # 如果有API密钥，添加到请求头
            if self.api_key:
                headers["x-api-key"] = self.api_key  # 注意：BlockVision使用小写的x-api-key

            # 使用BlockVision的Account Coins API
            url = f"{self.base_url}/sui/account/coins"
            params = {"account": address}

            response = await self.http_client.get(url, headers=headers, params=params)
            response.raise_for_status()

            data = response.json()
            tokens = []

            # 根据实际API响应结构解析数据
            if data.get("code") == 200 and data.get("result") and data["result"].get("coins"):
                for coin_data in data["result"]["coins"]:
                    try:
                        # 解析代币信息
                        coin_type = coin_data.get("coinType", "")
                        balance_raw = int(coin_data.get("balance", 0))
                        
                        # 直接从API响应获取代币元数据
                        symbol = coin_data.get("symbol", "")
                        name = coin_data.get("name", "")
                        decimals = int(coin_data.get("decimals", 9))
                        verified = coin_data.get("verified", False)
                        scam = coin_data.get("scam", False)
                        
                        # 跳过诈骗代币（除非明确要求包含）
                        if scam and not include_zero_balance:
                            logger.debug(f"跳过诈骗代币: {symbol} ({coin_type})")
                            continue

                        # 计算实际余额
                        balance = balance_raw / (10**decimals)

                        if balance > 0 or include_zero_balance:
                            # 判断是否为原生代币 - 检查完整的SUI coin type
                            is_native = coin_type in [
                                "0x2::sui::SUI", 
                                "0x0000000000000000000000000000000000000000000000000000000000000002::sui::SUI"
                            ]
                            
                            # 获取价格信息（如果可用）
                            price_usdc = None
                            value_usdc = None
                            try:
                                if coin_data.get("price") and coin_data.get("price") != "":
                                    price_usdc = float(coin_data.get("price", 0))
                                if coin_data.get("usdValue") and coin_data.get("usdValue") != "":
                                    value_usdc = float(coin_data.get("usdValue", 0))
                            except (ValueError, TypeError):
                                pass

                            token = DiscoveredToken(
                                symbol=symbol or self._extract_symbol_from_coin_type(coin_type),
                                name=name or symbol or "Unknown",
                                contract_address=None if is_native else coin_type,
                                balance=balance,
                                decimals=decimals,
                                is_native=is_native,
                                price_usdc=price_usdc,
                                value_usdc=value_usdc,
                            )
                            tokens.append(token)
                            
                            logger.debug(f"解析代币: {symbol} ({coin_type}), 余额: {balance}, 验证: {verified}, 诈骗: {scam}")

                    except Exception as e:
                        logger.warning(f"解析Sui代币数据失败: {e}, 数据: {coin_data}")
                        continue

            self.reset_errors()
            logger.info(
                f"BlockVision成功获取Sui钱包资产: {address}, 发现 {len(tokens)} 个代币"
            )
            return tokens

        except Exception as e:
            self.record_error()
            logger.error(f"BlockVision获取Sui钱包资产失败 {address}: {e}")
            return []

    async def get_token_balance(
        self, address: str, token_contract: Optional[str], chain_name: str
    ) -> float:
        """获取特定代币余额"""
        if not self.supports_chain(chain_name):
            return 0.0

        try:
            # 获取所有代币，然后筛选目标代币
            assets = await self.get_wallet_assets(
                address, chain_name, include_zero_balance=True
            )

            for asset in assets:
                # 原生代币匹配
                if token_contract is None and asset.is_native:
                    return asset.balance
                # 合约代币匹配
                elif (
                    token_contract
                    and asset.contract_address
                    and asset.contract_address.lower() == token_contract.lower()
                ):
                    return asset.balance

            return 0.0

        except Exception as e:
            logger.error(f"BlockVision获取Sui代币余额失败: {e}")
            return 0.0

    async def get_token_price(
        self, token_symbol: str, chain_name: str
    ) -> Optional[float]:
        """获取代币价格 - BlockVision可能不提供价格数据，返回None让价格服务处理"""
        return None

    async def _get_coin_metadata(self, coin_type: str) -> Dict[str, Any]:
        """获取代币元数据 - 备用方法，主要数据已从账户API获取"""
        try:
            await self._rate_limit()

            headers = {"Content-Type": "application/json"}

            if self.api_key:
                headers["x-api-key"] = self.api_key

            # 使用BlockVision的Coin Detail API
            url = f"{self.base_url}/sui/coin/detail"
            params = {"coin_type": coin_type}

            response = await self.http_client.get(url, headers=headers, params=params)
            response.raise_for_status()

            data = response.json()

            if data.get("code") == 200 and data.get("result") and data["result"].get("data"):
                coin_info = data["result"]["data"]
                return {
                    "symbol": coin_info.get("symbol", ""),
                    "name": coin_info.get("name", ""),
                    "decimals": int(coin_info.get("decimals", 9)),
                    "description": coin_info.get("description", ""),
                    "icon_url": coin_info.get("iconUrl", ""),
                }

            # 如果API没有返回数据，使用默认值
            return self._get_default_coin_metadata(coin_type)

        except Exception as e:
            logger.warning(f"获取Sui代币元数据失败: {e}, coin_type: {coin_type}")
            return self._get_default_coin_metadata(coin_type)

    def _get_default_coin_metadata(self, coin_type: str) -> Dict[str, Any]:
        """获取默认代币元数据"""
        # 已知代币的元数据 - 包含常见的Sui代币
        known_tokens = {
            # SUI原生代币
            "0x2::sui::SUI": {"symbol": "SUI", "name": "Sui", "decimals": 9},
            "0x0000000000000000000000000000000000000000000000000000000000000002::sui::SUI": {
                "symbol": "SUI", "name": "Sui", "decimals": 9
            },
            
            # USDC代币
            "0xdba34672e30cb065b1f93e3ab55318768fd6fef66c15942c9f7cb846e2f900e7::usdc::USDC": {
                "symbol": "USDC", "name": "USD Coin", "decimals": 6,
            },
            
            # USDT代币
            "0xc060006111016b8a020ad5b33834984a437aaa7d3c74c18e09a95d48aceab08c::coin::COIN": {
                "symbol": "USDT", "name": "Tether USD", "decimals": 6,
            },
            "0x7926cdedd3053cffe30d21933d78ed4a60d6d05f470985371d20e3135d93b1eb::usdt::USDT": {
                "symbol": "USDT", "name": "Tether USD", "decimals": 6,
            },
            
            # WETH代币
            "0xaf8cd5edc19c4512f4259f0bee101a40d41ebed738ade5874359610ef8eeced5::coin::COIN": {
                "symbol": "WETH", "name": "Wrapped Ether", "decimals": 8,
            },
            
            # 其他常见代币
            "0x83556891f4a0f233ce7b05cfe7f957d4020492a34f5405b2cb9377d060bef4bf::spring_sui::SPRING_SUI": {
                "symbol": "sSUI", "name": "Spring Staked SUI", "decimals": 9,
            },
            "0xbde4ba4c2e274a60ce15c1cfff9e5c42e41654ac8b6d906a57efa4bd3c29f47d::hasui::HASUI": {
                "symbol": "haSUI", "name": "haSUI", "decimals": 9,
            },
        }

        if coin_type in known_tokens:
            return known_tokens[coin_type]

        # 默认值
        return {
            "symbol": self._extract_symbol_from_coin_type(coin_type),
            "name": self._extract_symbol_from_coin_type(coin_type),
            "decimals": 9,  # Sui默认小数位数
        }

    def _extract_symbol_from_coin_type(self, coin_type: str) -> str:
        """从coin_type中提取代币符号"""
        try:
            # coin_type 格式: 0x...::module::TokenName
            if "::" in coin_type:
                parts = coin_type.split("::")
                if len(parts) >= 3:
                    return parts[-1].upper()

            # 如果格式不标准，返回地址的前8位
            return coin_type[:8].upper()

        except Exception:
            return "UNKNOWN"

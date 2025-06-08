"""
区块链服务模块

提供与各种区块链网络的交互功能，包括：
- 获取代币余额
- 查询钱包创建时间
- 发现钱包中的代币
"""

import asyncio
from typing import Dict, List, Optional
from datetime import datetime
from web3 import Web3
from web3.exceptions import ContractLogicError
import httpx

# 使用统一日志系统
from app.core.logger import get_logger
from app.core.config import SUPPORTED_CHAINS
from app.models.asset_models import WalletCreationInfo, DiscoveredToken

logger = get_logger(__name__)


class BlockchainService:
    """区块链服务类，用于获取代币余额和钱包信息"""

    def __init__(self):
        """初始化区块链服务"""
        self.web3_instances = {}
        self.connection_status = {}
        self.http_client = httpx.AsyncClient(timeout=30.0)
        self._initialization_lock = asyncio.Lock()
        self._chain_locks = {}  # 每个链的独立锁

        # 初始化每个链的锁
        for chain_name in SUPPORTED_CHAINS.keys():
            self._chain_locks[chain_name] = asyncio.Lock()

    async def ensure_chain_initialized(self, chain_name: str) -> bool:
        """确保指定链已初始化（按需初始化）"""
        chain_name = chain_name.lower()

        # 检查链是否支持
        if chain_name not in SUPPORTED_CHAINS:
            logger.error(f"不支持的区块链: {chain_name}")
            return False

        # 检查是否已经连接且健康
        if chain_name in self.web3_instances and self._is_connection_healthy(
            chain_name
        ):
            return True

        # 使用链特定的锁来避免重复初始化
        async with self._chain_locks[chain_name]:
            # 再次检查（双重检查锁定模式）
            if chain_name in self.web3_instances and self._is_connection_healthy(
                chain_name
            ):
                return True

            # 初始化指定链
            return await self._initialize_single_chain(chain_name)

    async def _initialize_single_chain(self, chain_name: str) -> bool:
        """初始化单个链的连接"""
        try:
            chain_config = SUPPORTED_CHAINS[chain_name]

            # 只为 EVM 兼容链初始化 Web3 实例
            if chain_config.get("chain_type") in ["solana", "sui", "bitcoin"]:
                self.connection_status[chain_name] = {
                    "status": "skipped",
                    "reason": f"非EVM链 ({chain_config.get('chain_type')})",
                    "connected_at": None,
                }
                logger.info(f"{chain_name} 是非EVM链，跳过Web3初始化")
                return True  # 非EVM链也算成功，因为它们不需要Web3实例

            # 获取备用 RPC URLs
            rpc_urls = self._get_rpc_urls_for_chain(chain_name, chain_config)

            for i, rpc_url in enumerate(rpc_urls):
                try:
                    logger.info(
                        f"尝试连接到 {chain_name} 网络 (RPC {i + 1}/{len(rpc_urls)}): {rpc_url}"
                    )

                    # 设置超时时间
                    w3 = Web3(
                        Web3.HTTPProvider(
                            rpc_url,
                            request_kwargs={"timeout": 10},  # 10秒超时
                        )
                    )

                    # 测试连接
                    if w3.is_connected():
                        # 进一步验证连接（尝试获取最新区块号）
                        try:
                            latest_block = w3.eth.block_number
                            self.web3_instances[chain_name] = w3
                            self.connection_status[chain_name] = {
                                "status": "connected",
                                "rpc_url": rpc_url,
                                "latest_block": latest_block,
                                "connected_at": datetime.now().isoformat(),
                            }
                            logger.info(
                                f"成功连接到 {chain_name} 网络，当前区块: {latest_block}"
                            )
                            return True
                        except Exception as e:
                            logger.warning(f"{chain_name} 连接测试失败: {e}")
                            continue
                    else:
                        logger.warning(f"无法连接到 {chain_name} 网络: {rpc_url}")

                except Exception as e:
                    logger.warning(
                        f"初始化 {chain_name} Web3 实例失败 (RPC {i + 1}): {e}"
                    )
                    continue

            # 所有RPC都失败
            self.connection_status[chain_name] = {
                "status": "failed",
                "reason": "所有RPC节点连接失败",
                "connected_at": None,
            }
            logger.error(
                f"所有 {chain_name} RPC 节点连接失败，请检查网络连接或更新 RPC 配置"
            )
            return False

        except Exception as e:
            logger.error(f"初始化 {chain_name} 失败: {e}")
            self.connection_status[chain_name] = {
                "status": "failed",
                "reason": str(e),
                "connected_at": None,
            }
            return False

    async def _async_initialize(self):
        """异步初始化Web3实例（已废弃，改为按需初始化）"""
        # 保留此方法以兼容现有代码，但不执行任何操作
        logger.info("使用按需初始化模式，跳过全量初始化")

    async def _initialize_web3_instances(self):
        """初始化各链的 Web3 实例（已废弃，改为按需初始化）"""
        # 保留此方法以兼容现有代码，但不执行任何操作
        logger.info("使用按需初始化模式，跳过全量初始化")

    def _is_connection_healthy(self, chain_name: str) -> bool:
        """检查连接是否健康"""
        if chain_name not in self.web3_instances:
            return False

        try:
            w3 = self.web3_instances[chain_name]
            # 简单的健康检查
            w3.eth.block_number
            return True
        except Exception:
            return False

    async def ensure_initialized(self):
        """确保服务已初始化（兼容性方法，现在不执行任何操作）"""
        # 改为按需初始化，不再预先初始化所有链
        logger.debug("使用按需初始化模式，无需预先初始化")

    async def reconnect_chain(self, chain_name: str) -> Optional[bool]:
        """重新连接指定链"""
        async with self._chain_locks.get(chain_name, asyncio.Lock()):
            chain_config = SUPPORTED_CHAINS.get(chain_name)
            if not chain_config:
                logger.error(f"不支持的区块链: {chain_name}")
                return False

            # 检查是否为非EVM链
            if chain_config.get("chain_type") in ["solana", "sui", "bitcoin"]:
                logger.info(f"{chain_name} 是非EVM链，跳过重连")
                return None

            # 移除旧连接
            if chain_name in self.web3_instances:
                del self.web3_instances[chain_name]

            # 重新连接
            return await self._initialize_single_chain(chain_name)

    async def reconnect_all_chains(self) -> Dict[str, bool]:
        """重新连接所有链（智能重连，跳过已连接的链）"""
        results = {}

        for chain_name in SUPPORTED_CHAINS.keys():
            chain_config = SUPPORTED_CHAINS[chain_name]
            if chain_config.get("chain_type") not in ["solana", "sui", "bitcoin"]:
                # 检查是否已经连接且健康
                if chain_name in self.web3_instances and self._is_connection_healthy(
                    chain_name
                ):
                    logger.info(f"{chain_name} 连接健康，跳过重连")
                    results[chain_name] = True
                else:
                    results[chain_name] = await self.reconnect_chain(chain_name)
            else:
                results[chain_name] = None  # 非EVM链跳过

        return results

    def get_connection_status(self) -> Dict[str, Dict]:
        """获取所有链的连接状态"""
        return self.connection_status.copy()

    def _get_rpc_urls_for_chain(self, chain_name: str, chain_config: dict) -> List[str]:
        """获取指定链的备用 RPC URLs"""
        # 备用 RPC 节点配置
        backup_rpcs = {
            "arbitrum": [
                "https://arb1.arbitrum.io/rpc",  # 官方节点
                "https://arbitrum-one.publicnode.com",  # PublicNode
                "https://arbitrum.llamarpc.com",  # LlamaRPC
                "https://rpc.ankr.com/arbitrum",  # Ankr
                "https://arbitrum-one.public.blastapi.io",  # Blast API
            ],
            "ethereum": [
                "https://eth.llamarpc.com",  # 当前配置
                "https://ethereum.publicnode.com",
                "https://rpc.ankr.com/eth",
                "https://eth.public-rpc.com",
                "https://ethereum-rpc.publicnode.com",
            ],
            "base": [
                "https://mainnet.base.org",  # 当前配置
                "https://base.llamarpc.com",
                "https://base.publicnode.com",
                "https://rpc.ankr.com/base",
            ],
            "polygon": [
                "https://polygon-rpc.com",  # 当前配置
                "https://polygon.llamarpc.com",
                "https://polygon.publicnode.com",
                "https://rpc.ankr.com/polygon",
            ],
            "bsc": [
                "https://bsc-dataseed.binance.org",  # 当前配置
                "https://bsc.publicnode.com",
                "https://rpc.ankr.com/bsc",
                "https://bsc-dataseed1.defibit.io",
            ],
        }

        # 返回备用节点列表，如果没有配置则使用原始配置
        return backup_rpcs.get(chain_name, [chain_config["rpc_url"]])

    async def get_token_balance(
        self, address: str, token_contract_address: Optional[str], chain_name: str
    ) -> float:
        """
        获取指定地址的代币余额

        Args:
            address: 钱包地址
            token_contract_address: 代币合约地址，None 表示原生代币
            chain_name: 区块链名称

        Returns:
            代币余额
        """
        try:
            chain_name = chain_name.lower()
            chain_config = SUPPORTED_CHAINS.get(chain_name)
            if not chain_config:
                logger.error(f"不支持的区块链: {chain_name}")
                return 0.0

            chain_type = chain_config.get("chain_type", "evm")

            # 根据链类型调用不同的方法
            if chain_type == "solana":
                return await self._get_solana_balance(
                    address, token_contract_address, chain_config
                )
            elif chain_type == "sui":
                return await self._get_sui_balance(
                    address, token_contract_address, chain_config
                )
            elif chain_type == "bitcoin":
                return await self._get_bitcoin_balance(address, chain_config)
            else:
                # EVM 兼容链
                return await self._get_evm_balance(
                    address, token_contract_address, chain_name
                )

        except Exception as e:
            logger.error(f"获取余额失败 - 地址: {address}, 链: {chain_name}, 错误: {e}")
            return 0.0

    async def _get_evm_balance(
        self, address: str, token_contract_address: Optional[str], chain_name: str
    ) -> float:
        """获取 EVM 兼容链的代币余额"""
        try:
            # 确保链已初始化
            if not await self.ensure_chain_initialized(chain_name):
                logger.error(f"无法初始化 {chain_name} 链")
                return 0.0

            w3 = self.web3_instances[chain_name]

            if token_contract_address:
                # ERC20 代币
                return await self._get_erc20_balance(
                    w3, address, token_contract_address
                )
            else:
                # 原生代币
                return await self._get_native_balance(w3, address)

        except Exception as e:
            logger.error(f"获取 EVM 余额失败: {e}")
            return 0.0

    async def _get_solana_balance(
        self, address: str, token_mint: Optional[str], chain_config: dict
    ) -> float:
        """获取 Solana 代币余额（带重试机制）"""
        max_retries = 3
        base_delay = 2

        # 备用 Solana RPC 节点
        rpc_urls = [
            chain_config["rpc_url"],  # 主节点
            "https://solana-api.projectserum.com",  # Serum
            "https://rpc.ankr.com/solana",  # Ankr
            "https://solana-mainnet.g.alchemy.com/v2/demo",  # Alchemy Demo
            "https://api.mainnet-beta.solana.com",  # 官方备用
        ]

        for rpc_url in rpc_urls:
            for attempt in range(max_retries):
                try:
                    if not token_mint or token_mint.lower() == "native":
                        # 获取 SOL 余额
                        payload = {
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "getBalance",
                            "params": [address],
                        }
                    else:
                        # 获取 SPL 代币余额
                        payload = {
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "getTokenAccountsByOwner",
                            "params": [
                                address,
                                {"mint": token_mint},
                                {"encoding": "jsonParsed"},
                            ],
                        }

                    # 添加超时设置
                    timeout = httpx.Timeout(30.0, connect=10.0)
                    async with httpx.AsyncClient(timeout=timeout) as client:
                        response = await client.post(rpc_url, json=payload)

                        # 检查HTTP状态码
                        if response.status_code == 429:
                            # 429 Too Many Requests - 等待后重试
                            wait_time = (
                                base_delay * (2**attempt) + 30
                            )  # 指数退避 + 额外等待
                            logger.warning(
                                f"Solana RPC 速率限制 (尝试 {attempt + 1}/{max_retries}，RPC: {rpc_url})，等待 {wait_time} 秒"
                            )
                            if attempt < max_retries - 1:
                                await asyncio.sleep(wait_time)
                                continue
                            else:
                                # 当前RPC节点重试次数用完，尝试下一个节点
                                logger.warning(
                                    f"RPC节点 {rpc_url} 重试次数用完，尝试下一个节点"
                                )
                                break

                        response.raise_for_status()
                        data = response.json()

                        if "error" in data:
                            error_code = data["error"].get("code", 0)
                            error_message = data["error"].get("message", "未知错误")

                            # 如果是速率限制错误，等待后重试
                            if (
                                error_code == 429
                                or "too many requests" in error_message.lower()
                            ):
                                wait_time = base_delay * (2**attempt) + 30
                                logger.warning(
                                    f"Solana RPC 速率限制错误 (尝试 {attempt + 1}/{max_retries}，RPC: {rpc_url})，等待 {wait_time} 秒"
                                )
                                if attempt < max_retries - 1:
                                    await asyncio.sleep(wait_time)
                                    continue
                                else:
                                    break
                            else:
                                logger.error(f"Solana RPC 错误: {data['error']}")
                                return 0.0

                        # 处理成功响应
                        if not token_mint or token_mint.lower() == "native":
                            # SOL 余额（单位：lamports，1 SOL = 10^9 lamports）
                            lamports = data["result"]["value"]
                            balance = lamports / 1_000_000_000
                            logger.debug(
                                f"成功获取 SOL 余额: {balance} (RPC: {rpc_url})"
                            )
                            return balance
                        else:
                            # SPL 代币余额
                            accounts = data["result"]["value"]
                            if not accounts:
                                return 0.0

                            total_balance = 0
                            for account in accounts:
                                token_amount = account["account"]["data"]["parsed"][
                                    "info"
                                ]["tokenAmount"]
                                balance = float(token_amount["uiAmount"] or 0)
                                total_balance += balance

                            logger.debug(
                                f"成功获取 SPL 代币余额: {total_balance} (RPC: {rpc_url})"
                            )
                            return total_balance

                except httpx.TimeoutException as e:
                    logger.warning(
                        f"Solana RPC 超时 (尝试 {attempt + 1}/{max_retries}，RPC: {rpc_url}): {e}"
                    )
                    if attempt < max_retries - 1:
                        await asyncio.sleep(base_delay * (attempt + 1))
                        continue
                    else:
                        break

                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 429:
                        wait_time = base_delay * (2**attempt) + 30
                        logger.warning(
                            f"Solana RPC HTTP 429 (尝试 {attempt + 1}/{max_retries}，RPC: {rpc_url})，等待 {wait_time} 秒"
                        )
                        if attempt < max_retries - 1:
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            break
                    else:
                        logger.error(f"Solana RPC HTTP 错误 (RPC: {rpc_url}): {e}")
                        break

                except Exception as e:
                    logger.warning(
                        f"Solana RPC 请求失败 (尝试 {attempt + 1}/{max_retries}，RPC: {rpc_url}): {e}"
                    )
                    if attempt < max_retries - 1:
                        await asyncio.sleep(base_delay * (attempt + 1))
                        continue
                    else:
                        break

        logger.error("所有 Solana RPC 节点都失败，无法获取余额")
        return 0.0

    async def _get_sui_balance(
        self, address: str, coin_type: Optional[str], chain_config: dict
    ) -> float:
        """获取 Sui 代币余额 - 优先使用BlockVision API"""
        try:
            # 首先尝试使用数据聚合器（包含BlockVision）
            from app.services.data_aggregator import data_aggregator

            balance = await data_aggregator.get_token_balance(address, coin_type, "sui")

            if balance > 0:
                logger.info(f"使用数据聚合器获取Sui余额成功: {balance}")
                return balance

            # 如果数据聚合器失败，回退到原生RPC
            logger.info("数据聚合器未获取到余额，回退到原生Sui RPC")
            return await self._get_sui_balance_rpc(address, coin_type, chain_config)

        except Exception as e:
            logger.error(f"获取 Sui 余额失败: {e}")
            # 回退到原生RPC
            return await self._get_sui_balance_rpc(address, coin_type, chain_config)

    async def _get_sui_balance_rpc(
        self, address: str, coin_type: Optional[str], chain_config: dict
    ) -> float:
        """使用原生Sui RPC获取代币余额"""
        try:
            rpc_url = chain_config["rpc_url"]

            if not coin_type or coin_type.lower() == "native":
                coin_type = "0x2::sui::SUI"

            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "suix_getBalance",
                "params": [address, coin_type],
            }

            response = await self.http_client.post(rpc_url, json=payload)
            data = response.json()

            if "error" in data:
                logger.error(f"Sui RPC 错误: {data['error']}")
                return 0.0

            # 获取原始余额
            total_balance = int(data["result"]["totalBalance"])

            # 根据代币类型确定小数位数
            decimals = self._get_sui_token_decimals(coin_type)
            balance = total_balance / (10**decimals)

            return balance

        except Exception as e:
            logger.error(f"获取 Sui 余额失败: {e}")
            return 0.0

    def _get_sui_token_decimals(self, coin_type: str) -> int:
        """获取Sui代币的小数位数"""
        # 已知代币的小数位数映射
        known_decimals = {
            "0x2::sui::SUI": 9,
            "0xdba34672e30cb065b1f93e3ab55318768fd6fef66c15942c9f7cb846e2f900e7::usdc::USDC": 6,
            "0xc060006111016b8a020ad5b33834984a437aaa7d3c74c18e09a95d48aceab08c::coin::COIN": 6,
        }

        # 检查已知代币
        if coin_type in known_decimals:
            return known_decimals[coin_type]

        # 根据代币符号推断
        if "usdc" in coin_type.lower() or "usdt" in coin_type.lower():
            return 6

        # 默认使用9位小数（Sui标准）
        return 9

    async def _get_bitcoin_balance(self, address: str, chain_config: dict) -> float:
        """获取 Bitcoin 余额"""
        try:
            # 使用 Blockstream API
            api_url = f"{chain_config['rpc_url']}/address/{address}"

            response = await self.http_client.get(api_url)
            data = response.json()

            # Bitcoin 余额（单位：satoshi，1 BTC = 10^8 satoshi）
            balance_satoshi = data.get("chain_stats", {}).get("funded_txo_sum", 0)
            spent_satoshi = data.get("chain_stats", {}).get("spent_txo_sum", 0)
            current_balance = balance_satoshi - spent_satoshi

            return current_balance / 100_000_000  # 转换为 BTC

        except Exception as e:
            logger.error(f"获取 Bitcoin 余额失败: {e}")
            return 0.0

    async def _get_native_balance(self, w3: Web3, address: str) -> float:
        """获取原生代币余额"""
        try:
            # 验证地址格式并转换为checksum格式
            if not self._is_valid_eth_address(address):
                logger.error(f"无效的以太坊地址格式: {address}")
                return 0.0

            checksum_address = w3.to_checksum_address(address)
            balance_wei = w3.eth.get_balance(checksum_address)
            balance_eth = w3.from_wei(balance_wei, "ether")
            return float(balance_eth)
        except Exception as e:
            logger.error(f"获取原生代币余额失败: {e}")
            return 0.0

    async def _get_erc20_balance(
        self, w3: Web3, address: str, contract_address: str
    ) -> float:
        """获取 ERC20 代币余额"""
        try:
            # 验证地址格式
            if not self._is_valid_eth_address(address):
                logger.error(f"无效的钱包地址格式: {address}")
                return 0.0

            if not self._is_valid_eth_address(contract_address):
                logger.error(f"无效的合约地址格式: {contract_address}")
                return 0.0

            # ERC20 标准 ABI（只包含必要的函数）
            erc20_abi = [
                {
                    "constant": True,
                    "inputs": [{"name": "_owner", "type": "address"}],
                    "name": "balanceOf",
                    "outputs": [{"name": "balance", "type": "uint256"}],
                    "type": "function",
                },
                {
                    "constant": True,
                    "inputs": [],
                    "name": "decimals",
                    "outputs": [{"name": "", "type": "uint8"}],
                    "type": "function",
                },
            ]

            contract = w3.eth.contract(
                address=w3.to_checksum_address(contract_address), abi=erc20_abi
            )

            # 获取余额和精度
            balance = contract.functions.balanceOf(
                w3.to_checksum_address(address)
            ).call()
            decimals = contract.functions.decimals().call()

            # 转换为可读格式
            return float(balance) / (10**decimals)

        except ContractLogicError as e:
            logger.error(f"合约调用失败: {e}")
            return 0.0
        except Exception as e:
            logger.error(f"获取 ERC20 余额失败: {e}")
            return 0.0

    def _is_valid_eth_address(self, address: str) -> bool:
        """验证以太坊地址格式"""
        try:
            if not address or not isinstance(address, str):
                return False

            # 移除空格
            address = address.strip()

            # 检查基本格式
            if not address.startswith("0x") or len(address) != 42:
                return False

            # 检查是否为有效的十六进制
            try:
                int(address[2:], 16)
                return True
            except ValueError:
                return False

        except Exception:
            return False

    def get_chain_info(self, chain_name: str) -> Optional[dict]:
        """获取链信息"""
        return SUPPORTED_CHAINS.get(chain_name.lower())

    async def get_wallet_creation_time(
        self, address: str, chain_name: str
    ) -> WalletCreationInfo:
        """
        获取钱包创建时间

        Args:
            address: 钱包地址
            chain_name: 区块链名称

        Returns:
            WalletCreationInfo: 钱包创建时间信息
        """
        try:
            chain_config = SUPPORTED_CHAINS.get(chain_name.lower())
            if not chain_config:
                return WalletCreationInfo(
                    address=address,
                    chain_name=chain_name,
                    creation_timestamp=None,
                    creation_date=None,
                    first_transaction_hash=None,
                    block_number=None,
                    is_estimated=False,
                    error_message=f"不支持的区块链: {chain_name}",
                )

            chain_type = chain_config.get("chain_type", "evm")

            # 根据链类型调用不同的方法
            if chain_type == "solana":
                return await self._get_solana_wallet_creation_time(
                    address, chain_config
                )
            elif chain_type == "sui":
                return await self._get_sui_wallet_creation_time(address, chain_config)
            elif chain_type == "bitcoin":
                return await self._get_bitcoin_wallet_creation_time(
                    address, chain_config
                )
            else:
                # EVM 兼容链
                return await self._get_evm_wallet_creation_time(
                    address, chain_name, chain_config
                )

        except Exception as e:
            logger.error(
                f"获取钱包创建时间失败 - 地址: {address}, 链: {chain_name}, 错误: {e}"
            )
            return WalletCreationInfo(
                address=address,
                chain_name=chain_name,
                creation_timestamp=None,
                creation_date=None,
                first_transaction_hash=None,
                block_number=None,
                is_estimated=False,
                error_message=str(e),
            )

    async def _get_evm_wallet_creation_time(
        self, address: str, chain_name: str, chain_config: dict
    ) -> WalletCreationInfo:
        """获取 EVM 兼容链的钱包创建时间"""
        try:
            # 确保链已初始化
            if not await self.ensure_chain_initialized(chain_name):
                return WalletCreationInfo(
                    address=address,
                    chain_name=chain_name,
                    creation_timestamp=None,
                    creation_date=None,
                    first_transaction_hash=None,
                    block_number=None,
                    is_estimated=False,
                    error_message=f"无法初始化 {chain_name} 链",
                )

            w3 = self.web3_instances[chain_name]

            # 使用区块浏览器 API 获取第一笔交易
            explorer_api_url = self._get_explorer_api_url(chain_name, address)
            if not explorer_api_url:
                # 如果没有浏览器API，使用估算方法
                return await self._estimate_wallet_creation_time(address, chain_name)

            response = await self.http_client.get(explorer_api_url)
            if response.status_code != 200:
                return await self._estimate_wallet_creation_time(address, chain_name)

            data = response.json()

            # 解析不同浏览器的响应格式
            first_tx = self._parse_explorer_response(data, chain_name)
            if not first_tx:
                return await self._estimate_wallet_creation_time(address, chain_name)

            # 获取交易详情
            tx_hash = first_tx.get("hash")
            block_number = first_tx.get("blockNumber")

            if block_number:
                try:
                    block = w3.eth.get_block(int(block_number))
                    timestamp = block["timestamp"]
                    creation_date = datetime.fromtimestamp(timestamp).isoformat()

                    return WalletCreationInfo(
                        address=address,
                        chain_name=chain_name,
                        creation_timestamp=timestamp,
                        creation_date=creation_date,
                        first_transaction_hash=tx_hash,
                        block_number=int(block_number),
                        is_estimated=False,
                        error_message=None,
                    )
                except Exception as e:
                    logger.error(f"获取区块信息失败: {e}")

            return await self._estimate_wallet_creation_time(address, chain_name)

        except Exception as e:
            logger.error(f"获取 EVM 钱包创建时间失败: {e}")
            return WalletCreationInfo(
                address=address,
                chain_name=chain_name,
                creation_timestamp=None,
                creation_date=None,
                first_transaction_hash=None,
                block_number=None,
                is_estimated=False,
                error_message=str(e),
            )

    async def _get_solana_wallet_creation_time(
        self, address: str, chain_config: dict
    ) -> WalletCreationInfo:
        """获取 Solana 钱包创建时间（带重试机制）"""
        max_retries = 3
        base_delay = 2

        # 备用 Solana RPC 节点
        rpc_urls = [
            chain_config["rpc_url"],  # 主节点
            "https://solana-api.projectserum.com",  # Serum
            "https://rpc.ankr.com/solana",  # Ankr
            "https://solana-mainnet.g.alchemy.com/v2/demo",  # Alchemy Demo
            "https://api.mainnet-beta.solana.com",  # 官方备用
        ]

        for rpc_url in rpc_urls:
            for attempt in range(max_retries):
                try:
                    # 获取账户的第一笔交易
                    payload = {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "getSignaturesForAddress",
                        "params": [
                            address,
                            {
                                "limit": 1000,  # 获取最多1000笔交易
                                "before": None,  # 从最新开始
                            },
                        ],
                    }

                    # 添加超时设置
                    timeout = httpx.Timeout(30.0, connect=10.0)
                    async with httpx.AsyncClient(timeout=timeout) as client:
                        response = await client.post(rpc_url, json=payload)

                        # 检查HTTP状态码
                        if response.status_code == 429:
                            wait_time = base_delay * (2**attempt) + 30
                            logger.warning(
                                f"Solana RPC 速率限制 (钱包创建时间查询，尝试 {attempt + 1}/{max_retries}，RPC: {rpc_url})，等待 {wait_time} 秒"
                            )
                            if attempt < max_retries - 1:
                                await asyncio.sleep(wait_time)
                                continue
                            else:
                                break

                        response.raise_for_status()
                        data = response.json()

                        if "error" in data:
                            error_code = data["error"].get("code", 0)
                            error_message = data["error"].get("message", "未知错误")

                            if (
                                error_code == 429
                                or "too many requests" in error_message.lower()
                            ):
                                wait_time = base_delay * (2**attempt) + 30
                                logger.warning(
                                    f"Solana RPC 速率限制错误 (钱包创建时间查询，尝试 {attempt + 1}/{max_retries}，RPC: {rpc_url})，等待 {wait_time} 秒"
                                )
                                if attempt < max_retries - 1:
                                    await asyncio.sleep(wait_time)
                                    continue
                                else:
                                    break
                            else:
                                logger.error(
                                    f"Solana RPC 错误 (钱包创建时间查询): {data['error']}"
                                )
                                return WalletCreationInfo(
                                    address=address,
                                    chain_name="solana",
                                    creation_timestamp=None,
                                    creation_date=None,
                                    first_transaction_hash=None,
                                    block_number=None,
                                    is_estimated=False,
                                    error_message=f"RPC错误: {data['error']}",
                                )

                        if not data.get("result"):
                            return WalletCreationInfo(
                                address=address,
                                chain_name="solana",
                                creation_timestamp=None,
                                creation_date=None,
                                first_transaction_hash=None,
                                block_number=None,
                                is_estimated=False,
                                error_message="无法获取交易历史",
                            )

                        signatures = data["result"]
                        if not signatures:
                            return WalletCreationInfo(
                                address=address,
                                chain_name="solana",
                                creation_timestamp=None,
                                creation_date=None,
                                first_transaction_hash=None,
                                block_number=None,
                                is_estimated=False,
                                error_message="该地址没有交易历史",
                            )

                        # 获取最早的交易（列表末尾）
                        first_signature = signatures[-1]
                        signature = first_signature["signature"]
                        block_time = first_signature.get("blockTime")

                        if block_time:
                            creation_date = datetime.fromtimestamp(
                                block_time
                            ).isoformat()
                            logger.debug(
                                f"成功获取 Solana 钱包创建时间: {creation_date} (RPC: {rpc_url})"
                            )
                            return WalletCreationInfo(
                                address=address,
                                chain_name="solana",
                                creation_timestamp=block_time,
                                creation_date=creation_date,
                                first_transaction_hash=signature,
                                block_number=None,
                                is_estimated=False,
                                error_message=None,
                            )

                        # 如果没有时间戳，使用估算方法
                        return await self._estimate_wallet_creation_time(
                            address, "solana"
                        )

                except httpx.TimeoutException as e:
                    logger.warning(
                        f"Solana RPC 超时 (钱包创建时间查询，尝试 {attempt + 1}/{max_retries}，RPC: {rpc_url}): {e}"
                    )
                    if attempt < max_retries - 1:
                        await asyncio.sleep(base_delay * (attempt + 1))
                        continue
                    else:
                        break

                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 429:
                        wait_time = base_delay * (2**attempt) + 30
                        logger.warning(
                            f"Solana RPC HTTP 429 (钱包创建时间查询，尝试 {attempt + 1}/{max_retries}，RPC: {rpc_url})，等待 {wait_time} 秒"
                        )
                        if attempt < max_retries - 1:
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            break
                    else:
                        logger.error(
                            f"Solana RPC HTTP 错误 (钱包创建时间查询，RPC: {rpc_url}): {e}"
                        )
                        break

                except Exception as e:
                    logger.warning(
                        f"Solana RPC 请求失败 (钱包创建时间查询，尝试 {attempt + 1}/{max_retries}，RPC: {rpc_url}): {e}"
                    )
                    if attempt < max_retries - 1:
                        await asyncio.sleep(base_delay * (attempt + 1))
                        continue
                    else:
                        break

        logger.error("所有 Solana RPC 节点都失败，无法获取钱包创建时间")
        return WalletCreationInfo(
            address=address,
            chain_name="solana",
            creation_timestamp=None,
            creation_date=None,
            first_transaction_hash=None,
            block_number=None,
            is_estimated=False,
            error_message="所有RPC节点都失败",
        )

    async def _get_sui_wallet_creation_time(
        self, address: str, chain_config: dict
    ) -> WalletCreationInfo:
        """获取 Sui 钱包创建时间"""
        try:
            # Sui 的钱包创建时间查询比较复杂，这里提供一个简化的实现
            # 实际应用中可能需要更复杂的逻辑
            return await self._estimate_wallet_creation_time(address, "sui")

        except Exception as e:
            logger.error(f"获取 Sui 钱包创建时间失败: {e}")
            return WalletCreationInfo(
                address=address,
                chain_name="sui",
                creation_timestamp=None,
                creation_date=None,
                first_transaction_hash=None,
                block_number=None,
                is_estimated=False,
                error_message=str(e),
            )

    async def _get_bitcoin_wallet_creation_time(
        self, address: str, chain_config: dict
    ) -> WalletCreationInfo:
        """获取 Bitcoin 钱包创建时间"""
        try:
            # 使用 Blockstream API 获取地址的第一笔交易
            api_url = f"{chain_config['rpc_url']}/address/{address}/txs"

            response = await self.http_client.get(api_url)
            if response.status_code != 200:
                return WalletCreationInfo(
                    address=address,
                    chain_name="bitcoin",
                    creation_timestamp=None,
                    creation_date=None,
                    first_transaction_hash=None,
                    block_number=None,
                    is_estimated=False,
                    error_message="无法获取交易历史",
                )

            transactions = response.json()
            if not transactions:
                return WalletCreationInfo(
                    address=address,
                    chain_name="bitcoin",
                    creation_timestamp=None,
                    creation_date=None,
                    first_transaction_hash=None,
                    block_number=None,
                    is_estimated=False,
                    error_message="该地址没有交易历史",
                )

            # 获取最早的交易（通常是列表的最后一个）
            first_tx = transactions[-1]
            tx_hash = first_tx.get("txid")

            # 获取区块信息
            if "status" in first_tx and "block_time" in first_tx["status"]:
                block_time = first_tx["status"]["block_time"]
                creation_date = datetime.fromtimestamp(block_time).isoformat()

                return WalletCreationInfo(
                    address=address,
                    chain_name="bitcoin",
                    creation_timestamp=block_time,
                    creation_date=creation_date,
                    first_transaction_hash=tx_hash,
                    block_number=None,
                    is_estimated=False,
                    error_message=None,
                )

            return await self._estimate_wallet_creation_time(address, "bitcoin")

        except Exception as e:
            logger.error(f"获取 Bitcoin 钱包创建时间失败: {e}")
            return WalletCreationInfo(
                address=address,
                chain_name="bitcoin",
                creation_timestamp=None,
                creation_date=None,
                first_transaction_hash=None,
                block_number=None,
                is_estimated=False,
                error_message=str(e),
            )

    def _get_explorer_api_url(self, chain_name: str, address: str) -> Optional[str]:
        """获取区块浏览器 API URL"""
        explorer_apis = {
            "ethereum": f"https://api.etherscan.io/api?module=account&action=txlist&address={address}&startblock=0&endblock=99999999&page=1&offset=1&sort=asc&apikey=YourApiKeyToken",
            "arbitrum": f"https://api.arbiscan.io/api?module=account&action=txlist&address={address}&startblock=0&endblock=99999999&page=1&offset=1&sort=asc&apikey=YourApiKeyToken",
            "base": f"https://api.basescan.org/api?module=account&action=txlist&address={address}&startblock=0&endblock=99999999&page=1&offset=1&sort=asc&apikey=YourApiKeyToken",
            "polygon": f"https://api.polygonscan.com/api?module=account&action=txlist&address={address}&startblock=0&endblock=99999999&page=1&offset=1&sort=asc&apikey=YourApiKeyToken",
            "bsc": f"https://api.bscscan.com/api?module=account&action=txlist&address={address}&startblock=0&endblock=99999999&page=1&offset=1&sort=asc&apikey=YourApiKeyToken",
        }
        return explorer_apis.get(chain_name)

    def _parse_explorer_response(self, data: dict, chain_name: str) -> Optional[dict]:
        """解析区块浏览器响应"""
        try:
            if data.get("status") == "1" and data.get("result"):
                transactions = data["result"]
                if transactions and len(transactions) > 0:
                    return transactions[0]  # 第一笔交易
        except Exception as e:
            logger.error(f"解析浏览器响应失败: {e}")
        return None

    async def _estimate_wallet_creation_time(
        self, address: str, chain_name: str
    ) -> WalletCreationInfo:
        """估算钱包创建时间（当无法获取准确时间时的备选方案）"""
        try:
            # 这里可以实现一些估算逻辑，比如基于当前时间减去一个合理的时间范围
            # 或者基于链的创建时间等
            logger.info(f"使用估算方法获取钱包创建时间: {address} on {chain_name}")

            return WalletCreationInfo(
                address=address,
                chain_name=chain_name,
                creation_timestamp=None,
                creation_date=None,
                first_transaction_hash=None,
                block_number=None,
                is_estimated=True,
                error_message="无法获取准确的创建时间，建议手动查询",
            )

        except Exception as e:
            logger.error(f"估算钱包创建时间失败: {e}")
            return WalletCreationInfo(
                address=address,
                chain_name=chain_name,
                creation_timestamp=None,
                creation_date=None,
                first_transaction_hash=None,
                block_number=None,
                is_estimated=False,
                error_message=str(e),
            )

    async def discover_wallet_tokens(
        self,
        address: str,
        chain_name: str,
        include_zero_balance: bool = False,
        min_value_usdc: float = 0.01,
    ) -> List[DiscoveredToken]:
        """
        自动发现钱包中的代币

        Args:
            address: 钱包地址
            chain_name: 区块链名称
            include_zero_balance: 是否包含零余额代币
            min_value_usdc: 最小价值阈值（USDC）

        Returns:
            发现的代币列表
        """
        try:
            chain_name = chain_name.lower()
            chain_config = SUPPORTED_CHAINS.get(chain_name)
            if not chain_config:
                logger.error(f"不支持的区块链: {chain_name}")
                return []

            chain_type = chain_config.get("chain_type", "evm")
            discovered_tokens = []

            # 根据链类型调用不同的发现方法
            if chain_type == "solana":
                discovered_tokens = await self._discover_solana_tokens(
                    address, chain_config, include_zero_balance
                )
            elif chain_type == "sui":
                discovered_tokens = await self._discover_sui_tokens(
                    address, chain_config, include_zero_balance
                )
            elif chain_type == "bitcoin":
                discovered_tokens = await self._discover_bitcoin_tokens(
                    address, chain_config
                )
            else:
                # EVM 兼容链
                discovered_tokens = await self._discover_evm_tokens(
                    address, chain_name, chain_config, include_zero_balance
                )

            # 过滤掉价值过低的代币（如果设置了阈值）
            if min_value_usdc > 0:
                discovered_tokens = [
                    token
                    for token in discovered_tokens
                    if token.value_usdc is None or token.value_usdc >= min_value_usdc
                ]

            logger.info(f"在 {chain_name} 链上发现 {len(discovered_tokens)} 个代币")
            return discovered_tokens

        except Exception as e:
            logger.error(
                f"发现钱包代币失败 - 地址: {address}, 链: {chain_name}, 错误: {e}"
            )
            return []

    async def _discover_evm_tokens(
        self,
        address: str,
        chain_name: str,
        chain_config: dict,
        include_zero_balance: bool,
    ) -> List[DiscoveredToken]:
        """发现 EVM 兼容链的代币"""
        discovered_tokens = []

        try:
            # 确保链已初始化
            if not await self.ensure_chain_initialized(chain_name):
                logger.error(f"无法初始化 {chain_name} 链")
                return []

            w3 = self.web3_instances[chain_name]

            # 1. 首先获取原生代币余额
            native_balance = await self._get_native_balance(w3, address)
            if native_balance > 0 or include_zero_balance:
                native_info = self._get_native_token_info(chain_name)
                native_token = DiscoveredToken(
                    symbol=native_info["symbol"],
                    name=native_info["name"],
                    contract_address=None,
                    balance=native_balance,
                    decimals=native_info["decimals"],
                    is_native=True,
                    price_usdc=0.0,
                    value_usdc=0.0,
                )
                discovered_tokens.append(native_token)

            # 2. 使用区块浏览器API获取ERC20代币
            erc20_tokens = await self._get_erc20_tokens_from_explorer(
                address, chain_name, include_zero_balance
            )
            discovered_tokens.extend(erc20_tokens)

            return discovered_tokens

        except Exception as e:
            logger.error(f"发现 EVM 代币失败: {e}")
            return discovered_tokens

    async def _discover_solana_tokens(
        self, address: str, chain_config: dict, include_zero_balance: bool
    ) -> List[DiscoveredToken]:
        """发现 Solana 代币（带重试机制）"""
        discovered_tokens = []
        max_retries = 3
        base_delay = 2

        # 备用 Solana RPC 节点
        rpc_urls = [
            chain_config["rpc_url"],  # 主节点
            "https://solana-api.projectserum.com",  # Serum
            "https://rpc.ankr.com/solana",  # Ankr
            "https://solana-mainnet.g.alchemy.com/v2/demo",  # Alchemy Demo
            "https://api.mainnet-beta.solana.com",  # 官方备用
        ]

        for rpc_url in rpc_urls:
            for attempt in range(max_retries):
                try:
                    # 添加超时设置
                    timeout = httpx.Timeout(30.0, connect=10.0)
                    async with httpx.AsyncClient(timeout=timeout) as client:
                        # 1. 获取 SOL 余额
                        sol_payload = {
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "getBalance",
                            "params": [address],
                        }

                        response = await client.post(rpc_url, json=sol_payload)

                        # 检查HTTP状态码
                        if response.status_code == 429:
                            wait_time = base_delay * (2**attempt) + 30
                            logger.warning(
                                f"Solana RPC 速率限制 (代币发现，尝试 {attempt + 1}/{max_retries}，RPC: {rpc_url})，等待 {wait_time} 秒"
                            )
                            if attempt < max_retries - 1:
                                await asyncio.sleep(wait_time)
                                continue
                            else:
                                break

                        response.raise_for_status()
                        data = response.json()

                        if "error" in data:
                            error_code = data["error"].get("code", 0)
                            error_message = data["error"].get("message", "未知错误")

                            if (
                                error_code == 429
                                or "too many requests" in error_message.lower()
                            ):
                                wait_time = base_delay * (2**attempt) + 30
                                logger.warning(
                                    f"Solana RPC 速率限制错误 (代币发现，尝试 {attempt + 1}/{max_retries}，RPC: {rpc_url})，等待 {wait_time} 秒"
                                )
                                if attempt < max_retries - 1:
                                    await asyncio.sleep(wait_time)
                                    continue
                                else:
                                    break
                            else:
                                logger.error(
                                    f"Solana RPC 错误 (代币发现): {data['error']}"
                                )
                                break

                        if "result" in data:
                            lamports = data["result"]["value"]
                            sol_balance = lamports / 1_000_000_000

                            if sol_balance > 0 or include_zero_balance:
                                sol_token = DiscoveredToken(
                                    symbol="SOL",
                                    name="Solana",
                                    contract_address=None,
                                    balance=sol_balance,
                                    decimals=9,
                                    is_native=True,
                                    price_usdc=0.0,
                                    value_usdc=0.0,
                                )
                                discovered_tokens.append(sol_token)

                        # 2. 获取所有 SPL 代币账户
                        spl_payload = {
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "getTokenAccountsByOwner",
                            "params": [
                                address,
                                {
                                    "programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
                                },
                                {"encoding": "jsonParsed"},
                            ],
                        }

                        response = await client.post(rpc_url, json=spl_payload)

                        # 再次检查HTTP状态码
                        if response.status_code == 429:
                            wait_time = base_delay * (2**attempt) + 30
                            logger.warning(
                                f"Solana RPC 速率限制 (SPL代币查询，尝试 {attempt + 1}/{max_retries}，RPC: {rpc_url})，等待 {wait_time} 秒"
                            )
                            if attempt < max_retries - 1:
                                await asyncio.sleep(wait_time)
                                continue
                            else:
                                break

                        response.raise_for_status()
                        data = response.json()

                        if "error" in data:
                            error_code = data["error"].get("code", 0)
                            error_message = data["error"].get("message", "未知错误")

                            if (
                                error_code == 429
                                or "too many requests" in error_message.lower()
                            ):
                                wait_time = base_delay * (2**attempt) + 30
                                logger.warning(
                                    f"Solana RPC 速率限制错误 (SPL代币查询，尝试 {attempt + 1}/{max_retries}，RPC: {rpc_url})，等待 {wait_time} 秒"
                                )
                                if attempt < max_retries - 1:
                                    await asyncio.sleep(wait_time)
                                    continue
                                else:
                                    break
                            else:
                                logger.error(
                                    f"Solana RPC 错误 (SPL代币查询): {data['error']}"
                                )
                                break

                        if "result" in data:
                            accounts = data["result"]["value"]

                            for account in accounts:
                                try:
                                    token_info = account["account"]["data"]["parsed"][
                                        "info"
                                    ]
                                    token_amount = token_info["tokenAmount"]
                                    mint = token_info["mint"]

                                    balance = float(token_amount["uiAmount"] or 0)
                                    decimals = token_amount["decimals"]

                                    if balance > 0 or include_zero_balance:
                                        # 获取代币元数据
                                        (
                                            symbol,
                                            name,
                                        ) = await self._get_solana_token_metadata(
                                            mint, rpc_url
                                        )

                                        solana_token = DiscoveredToken(
                                            symbol=symbol or mint[:8].upper(),
                                            name=name or f"Token {mint[:8]}",
                                            contract_address=mint,
                                            balance=balance,
                                            decimals=decimals,
                                            is_native=False,
                                            price_usdc=0.0,
                                            value_usdc=0.0,
                                        )
                                        discovered_tokens.append(solana_token)

                                except Exception as e:
                                    logger.warning(f"解析 Solana 代币账户失败: {e}")
                                    continue

                        logger.debug(
                            f"成功发现 {len(discovered_tokens)} 个 Solana 代币 (RPC: {rpc_url})"
                        )
                        return discovered_tokens

                except httpx.TimeoutException as e:
                    logger.warning(
                        f"Solana RPC 超时 (代币发现，尝试 {attempt + 1}/{max_retries}，RPC: {rpc_url}): {e}"
                    )
                    if attempt < max_retries - 1:
                        await asyncio.sleep(base_delay * (attempt + 1))
                        continue
                    else:
                        break

                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 429:
                        wait_time = base_delay * (2**attempt) + 30
                        logger.warning(
                            f"Solana RPC HTTP 429 (代币发现，尝试 {attempt + 1}/{max_retries}，RPC: {rpc_url})，等待 {wait_time} 秒"
                        )
                        if attempt < max_retries - 1:
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            break
                    else:
                        logger.error(
                            f"Solana RPC HTTP 错误 (代币发现，RPC: {rpc_url}): {e}"
                        )
                        break

                except Exception as e:
                    logger.warning(
                        f"Solana RPC 请求失败 (代币发现，尝试 {attempt + 1}/{max_retries}，RPC: {rpc_url}): {e}"
                    )
                    if attempt < max_retries - 1:
                        await asyncio.sleep(base_delay * (attempt + 1))
                        continue
                    else:
                        break

        logger.error("所有 Solana RPC 节点都失败，无法发现代币")
        return discovered_tokens

    async def _discover_sui_tokens(
        self, address: str, chain_config: dict, include_zero_balance: bool
    ) -> List[DiscoveredToken]:
        """发现 Sui 代币 - 优先使用BlockVision API"""
        try:
            # 首先尝试使用数据聚合器（包含BlockVision）
            from app.services.data_aggregator import data_aggregator

            discovered_tokens = await data_aggregator.get_wallet_assets(
                address, "sui", include_zero_balance
            )

            if discovered_tokens:
                logger.info(
                    f"使用数据聚合器发现Sui代币成功: {len(discovered_tokens)} 个代币"
                )
                return discovered_tokens

            # 如果数据聚合器失败，回退到原生RPC
            logger.info("数据聚合器未发现代币，回退到原生Sui RPC")
            return await self._discover_sui_tokens_rpc(
                address, chain_config, include_zero_balance
            )

        except Exception as e:
            logger.error(f"发现 Sui 代币失败: {e}")
            # 回退到原生RPC
            return await self._discover_sui_tokens_rpc(
                address, chain_config, include_zero_balance
            )

    async def _discover_sui_tokens_rpc(
        self, address: str, chain_config: dict, include_zero_balance: bool
    ) -> List[DiscoveredToken]:
        """使用原生Sui RPC发现代币"""
        discovered_tokens = []

        try:
            rpc_url = chain_config["rpc_url"]

            # 1. 获取 SUI 余额
            sui_payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "suix_getBalance",
                "params": [address, "0x2::sui::SUI"],
            }

            response = await self.http_client.post(rpc_url, json=sui_payload)
            data = response.json()

            if "result" in data:
                total_balance = int(data["result"]["totalBalance"])
                sui_balance = total_balance / 1_000_000_000  # SUI是9位小数

                if sui_balance > 0 or include_zero_balance:
                    sui_token = DiscoveredToken(
                        symbol="SUI",
                        name="Sui",
                        contract_address=None,
                        balance=sui_balance,
                        decimals=9,
                        is_native=True,
                        price_usdc=0.0,
                        value_usdc=0.0,
                    )
                    discovered_tokens.append(sui_token)

            # 2. 获取所有代币余额
            all_balances_payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "suix_getAllBalances",
                "params": [address],
            }

            response = await self.http_client.post(rpc_url, json=all_balances_payload)
            data = response.json()

            if "result" in data:
                balances = data["result"]

                for balance_info in balances:
                    coin_type = balance_info["coinType"]
                    total_balance = int(balance_info["totalBalance"])

                    # 跳过已经处理的 SUI
                    if coin_type == "0x2::sui::SUI":
                        continue

                    # 使用正确的小数位数
                    decimals = self._get_sui_token_decimals(coin_type)
                    balance = total_balance / (10**decimals)

                    if balance > 0 or include_zero_balance:
                        # 从coin_type中提取代币信息
                        token_symbol = self._extract_sui_token_symbol(coin_type)

                        sui_token = DiscoveredToken(
                            symbol=token_symbol,
                            name=token_symbol,
                            contract_address=coin_type,
                            balance=balance,
                            decimals=decimals,
                            is_native=False,
                            price_usdc=0.0,
                            value_usdc=0.0,
                        )
                        discovered_tokens.append(sui_token)

            logger.info(f"Sui RPC发现代币: {len(discovered_tokens)} 个")
            return discovered_tokens

        except Exception as e:
            logger.error(f"发现 Sui 代币失败: {e}")
            return discovered_tokens

    async def _discover_bitcoin_tokens(
        self, address: str, chain_config: dict
    ) -> List[DiscoveredToken]:
        """发现 Bitcoin 代币（只有 BTC）"""
        discovered_tokens = []

        try:
            # Bitcoin 只有原生代币 BTC
            btc_balance = await self._get_bitcoin_balance(address, chain_config)

            if btc_balance > 0:
                btc_token = DiscoveredToken(
                    symbol="BTC",
                    name="Bitcoin",
                    contract_address=None,
                    balance=btc_balance,
                    decimals=8,
                    is_native=True,
                    price_usdc=0.0,
                    value_usdc=0.0,
                )
                discovered_tokens.append(btc_token)

            return discovered_tokens

        except Exception as e:
            logger.error(f"发现 Bitcoin 代币失败: {e}")
            return discovered_tokens

    async def _get_erc20_tokens_from_explorer(
        self, address: str, chain_name: str, include_zero_balance: bool
    ) -> List[DiscoveredToken]:
        """从区块浏览器API获取ERC20代币列表"""
        tokens = []

        try:
            # 这里可以集成各种区块浏览器的API
            # 由于API限制，我们先返回一个基本的实现
            # 在实际应用中，可以使用 Moralis、Alchemy 等服务的API

            # 示例：使用一些常见的代币合约地址进行检查
            common_tokens = await self._get_common_tokens_for_chain(chain_name)

            # 确保链已初始化
            if await self.ensure_chain_initialized(chain_name):
                w3 = self.web3_instances[chain_name]

                for token_info in common_tokens:
                    try:
                        balance = await self._get_erc20_balance(
                            w3, address, token_info["contract_address"]
                        )

                        if balance > 0 or include_zero_balance:
                            token = DiscoveredToken(
                                symbol=token_info["symbol"],
                                name=token_info["name"],
                                contract_address=token_info["contract_address"],
                                balance=balance,
                                decimals=token_info.get("decimals", 18),
                                is_native=False,
                                price_usdc=0.0,
                                value_usdc=0.0,
                            )
                            tokens.append(token)

                    except Exception as e:
                        logger.warning(f"检查代币 {token_info['symbol']} 余额失败: {e}")
                        continue

            return tokens

        except Exception as e:
            logger.error(f"从浏览器获取 ERC20 代币失败: {e}")
            return tokens

    async def _get_common_tokens_for_chain(self, chain_name: str) -> List[Dict]:
        """获取指定链上的常见代币列表"""
        # 这里返回一些常见的代币，实际应用中可以从配置文件或数据库中获取
        common_tokens = {
            "ethereum": [
                {
                    "symbol": "USDC",
                    "name": "USD Coin",
                    "contract_address": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                    "decimals": 6,
                },
                {
                    "symbol": "USDT",
                    "name": "Tether USD",
                    "contract_address": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
                    "decimals": 6,
                },
                {
                    "symbol": "DAI",
                    "name": "Dai Stablecoin",
                    "contract_address": "0x6B175474E89094C44Da98b954EedeAC495271d0F",
                    "decimals": 18,
                },
                {
                    "symbol": "WETH",
                    "name": "Wrapped Ether",
                    "contract_address": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
                    "decimals": 18,
                },
            ],
            "arbitrum": [
                {
                    "symbol": "USDC",
                    "name": "USD Coin",
                    "contract_address": "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
                    "decimals": 6,
                },
                {
                    "symbol": "USDT",
                    "name": "Tether USD",
                    "contract_address": "0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9",
                    "decimals": 6,
                },
            ],
            "base": [
                {
                    "symbol": "USDC",
                    "name": "USD Coin",
                    "contract_address": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
                    "decimals": 6,
                },
                {
                    "symbol": "USDT",
                    "name": "Tether USD",
                    "contract_address": "0xfde4C96c8593536E31F229EA8f37b2ADa2699bb2",
                    "decimals": 6,
                },
            ],
            "polygon": [
                {
                    "symbol": "USDC",
                    "name": "USD Coin",
                    "contract_address": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
                    "decimals": 6,
                },
                {
                    "symbol": "USDT",
                    "name": "Tether USD",
                    "contract_address": "0xc2132D05D31c914a87C6611C10748AEb04B58e8F",
                    "decimals": 6,
                },
            ],
            "bsc": [
                {
                    "symbol": "USDC",
                    "name": "USD Coin",
                    "contract_address": "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
                    "decimals": 18,
                },
                {
                    "symbol": "USDT",
                    "name": "Tether USD",
                    "contract_address": "0x55d398326f99059fF775485246999027B3197955",
                    "decimals": 18,
                },
            ],
        }

        return common_tokens.get(chain_name, [])

    async def _get_solana_token_metadata(self, mint: str, rpc_url: str) -> tuple:
        """获取 Solana 代币的元数据（符号和名称）"""
        try:
            # 1. 首先尝试从 Metaplex 元数据账户获取
            symbol, name = await self._get_metaplex_metadata(mint, rpc_url)
            if symbol and name:
                return symbol, name

            # 2. 如果 Metaplex 失败，尝试从 Solana Token Registry 获取
            symbol, name = await self._get_token_registry_metadata(mint)
            if symbol and name:
                return symbol, name

            # 3. 如果都失败，返回简化的地址作为符号
            return mint[:8].upper(), f"Token {mint[:8]}"

        except Exception as e:
            logger.warning(f"获取 Solana 代币元数据失败: {e}")
            return mint[:8].upper(), f"Token {mint[:8]}"

    async def _get_metaplex_metadata(self, mint: str, rpc_url: str) -> tuple:
        """从 Metaplex 元数据账户获取代币信息（带重试机制）"""
        max_retries = 3
        base_delay = 2

        for attempt in range(max_retries):
            try:
                # 计算 Metaplex 元数据账户地址
                # PDA seeds: ["metadata", metaplex_program_id, mint_address]
                metaplex_program_id = "metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s"

                # 使用 Solana RPC 的 getProgramAccounts 方法查找元数据账户
                metadata_payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getProgramAccounts",
                    "params": [
                        metaplex_program_id,
                        {
                            "encoding": "base64",
                            "filters": [
                                {
                                    "memcmp": {
                                        "offset": 33,  # mint address offset in metadata account
                                        "bytes": mint,
                                    }
                                }
                            ],
                        },
                    ],
                }

                # 添加超时设置
                timeout = httpx.Timeout(30.0, connect=10.0)
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(rpc_url, json=metadata_payload)

                    # 检查HTTP状态码
                    if response.status_code == 429:
                        wait_time = base_delay * (2**attempt) + 30
                        logger.warning(
                            f"Solana RPC 速率限制 (Metaplex元数据，尝试 {attempt + 1}/{max_retries})，等待 {wait_time} 秒"
                        )
                        if attempt < max_retries - 1:
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            return None, None

                    response.raise_for_status()
                    data = response.json()

                    if "error" in data:
                        error_code = data["error"].get("code", 0)
                        error_message = data["error"].get("message", "未知错误")

                        if (
                            error_code == 429
                            or "too many requests" in error_message.lower()
                        ):
                            wait_time = base_delay * (2**attempt) + 30
                            logger.warning(
                                f"Solana RPC 速率限制错误 (Metaplex元数据，尝试 {attempt + 1}/{max_retries})，等待 {wait_time} 秒"
                            )
                            if attempt < max_retries - 1:
                                await asyncio.sleep(wait_time)
                                continue
                            else:
                                return None, None
                        else:
                            logger.warning(
                                f"Solana RPC 错误 (Metaplex元数据): {data['error']}"
                            )
                            return None, None

                    if "result" in data and data["result"]:
                        # 解析元数据账户数据
                        for account in data["result"]:
                            try:
                                # 这里需要解析 Metaplex 元数据格式
                                # 由于格式复杂，我们先尝试简单的方法
                                account_data = account["account"]["data"][0]
                                return account_data, None
                            except Exception:
                                continue

                    return None, None

            except httpx.TimeoutException as e:
                logger.warning(
                    f"Solana RPC 超时 (Metaplex元数据，尝试 {attempt + 1}/{max_retries}): {e}"
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(base_delay * (attempt + 1))
                    continue
                else:
                    return None, None

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    wait_time = base_delay * (2**attempt) + 30
                    logger.warning(
                        f"Solana RPC HTTP 429 (Metaplex元数据，尝试 {attempt + 1}/{max_retries})，等待 {wait_time} 秒"
                    )
                    if attempt < max_retries - 1:
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        return None, None
                else:
                    logger.warning(f"Solana RPC HTTP 错误 (Metaplex元数据): {e}")
                    return None, None

            except Exception as e:
                logger.warning(
                    f"从 Metaplex 获取元数据失败 (尝试 {attempt + 1}/{max_retries}): {e}"
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(base_delay * (attempt + 1))
                    continue
                else:
                    return None, None

        return None, None

    async def _get_token_registry_metadata(self, mint: str) -> tuple:
        """从 Solana Token Registry 获取代币信息（带重试机制）"""
        max_retries = 3
        base_delay = 2

        for attempt in range(max_retries):
            try:
                # 使用 Solana Labs Token List
                token_list_url = "https://raw.githubusercontent.com/solana-labs/token-list/main/src/tokens/solana.tokenlist.json"

                # 添加超时设置
                timeout = httpx.Timeout(30.0, connect=10.0)
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.get(token_list_url)
                    response.raise_for_status()
                    data = response.json()

                    if "tokens" in data:
                        for token in data["tokens"]:
                            if token.get("address") == mint:
                                symbol = token.get("symbol", mint[:8].upper())
                                name = token.get("name", f"Token {mint[:8]}")
                                logger.debug(
                                    f"从 Token Registry 获取到代币信息: {symbol} - {name}"
                                )
                                return symbol, name

                    # 如果在主列表中没找到，尝试一些知名的代币注册表
                    known_tokens = await self._get_known_solana_tokens()
                    if mint in known_tokens:
                        token_info = known_tokens[mint]
                        symbol = token_info.get("symbol", mint[:8].upper())
                        name = token_info.get("name", f"Token {mint[:8]}")
                        logger.debug(f"从已知代币列表获取到代币信息: {symbol} - {name}")
                        return symbol, name

                    return None, None

            except httpx.TimeoutException as e:
                logger.warning(
                    f"Token Registry 请求超时 (尝试 {attempt + 1}/{max_retries}): {e}"
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(base_delay * (attempt + 1))
                    continue
                else:
                    return None, None

            except httpx.HTTPStatusError as e:
                logger.warning(
                    f"Token Registry HTTP 错误 (尝试 {attempt + 1}/{max_retries}): {e}"
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(base_delay * (attempt + 1))
                    continue
                else:
                    return None, None

            except Exception as e:
                logger.warning(
                    f"从 Token Registry 获取元数据失败 (尝试 {attempt + 1}/{max_retries}): {e}"
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(base_delay * (attempt + 1))
                    continue
                else:
                    return None, None

        return None, None

    async def _get_known_solana_tokens(self) -> dict:
        """获取已知的 Solana 代币信息"""
        return {
            # 主要稳定币
            "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": {
                "symbol": "USDC",
                "name": "USD Coin",
                "decimals": 6,
            },
            "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB": {
                "symbol": "USDT",
                "name": "Tether USD",
                "decimals": 6,
            },
            # SOL 包装代币
            "So11111111111111111111111111111111111111112": {
                "symbol": "SOL",
                "name": "Wrapped SOL",
                "decimals": 9,
            },
            # 其他知名代币
            "mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So": {
                "symbol": "mSOL",
                "name": "Marinade staked SOL",
                "decimals": 9,
            },
            "7dHbWXmci3dT8UFYWYZweBLXgycu7Y3iL6trKn1Y7ARj": {
                "symbol": "stSOL",
                "name": "Lido Staked SOL",
                "decimals": 9,
            },
            # 常见的 DeFi 代币
            "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R": {
                "symbol": "RAY",
                "name": "Raydium",
                "decimals": 6,
            },
            "SRMuApVNdxXokk5GT7XD5cUUgXMBCoAz2LHeuAoKWRt": {
                "symbol": "SRM",
                "name": "Serum",
                "decimals": 6,
            },
            # 添加您提到的代币地址（如果知道的话）
            "A5MpcHnx": {
                "symbol": "UNKNOWN",
                "name": "Unknown Token A5MpcHnx",
                "decimals": 9,
            },
            "sSo14end": {
                "symbol": "UNKNOWN",
                "name": "Unknown Token sSo14end",
                "decimals": 9,
            },
        }

    def _extract_sui_token_symbol(self, coin_type: str) -> str:
        """从 Sui coin_type 中提取代币符号"""
        try:
            # coin_type 格式通常是: 0x...::module::TokenName
            parts = coin_type.split("::")
            if len(parts) >= 3:
                return parts[-1].upper()
            else:
                # 如果格式不标准，返回地址的前8位
                return coin_type[:8].upper()
        except Exception:
            return coin_type[:8].upper()

    def _get_native_token_info(self, chain_name: str) -> dict:
        """获取链的原生代币信息"""
        from app.core.config import get_native_token
        
        native_token = get_native_token(chain_name)
        if native_token:
            return {
                "symbol": native_token["symbol"],
                "name": native_token["name"],
                "decimals": native_token["decimals"]
            }
        
        # 如果没有找到，返回默认值
        return {"symbol": "UNKNOWN", "name": "Unknown", "decimals": 18}

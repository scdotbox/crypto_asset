# 加密货币资产管理

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

中文版本 | [English](README.md)

一个用于管理多链加密货币资产的综合性 Web 应用程序，支持实时价格监控和投资组合管理功能。

## ✨ 功能特性

- 🔗 **多链支持**: Ethereum、Arbitrum、Base、Polygon、BSC、Solana、Sui、Bitcoin
- 💰 **实时价格**: 集成 CoinGecko API 获取实时代币价格
- 📊 **资产管理**: 添加、查看、删除加密货币资产
- 🏷️ **标签系统**: 为资产添加自定义标签进行分类管理
- 📈 **历史数据**: 查看资产的历史价值变化
- 🚀 **性能优化**: 智能缓存和批量查询减少 API 调用
- 📱 **响应式设计**: 移动优先的现代化用户界面
- 🔄 **自动刷新**: 实时投资组合更新

## 🌐 支持的区块链

### EVM 兼容链
- **Ethereum** (ETH) - 以太坊主网
- **Arbitrum One** (ETH) - 以太坊 L2 扩容网络
- **Base** (ETH) - Coinbase 的 L2 网络
- **Polygon** (MATIC) - Polygon 主网
- **BNB Smart Chain** (BNB) - 币安智能链

### 非 EVM 链
- **Solana** (SOL) - Solana 主网
- **Sui** (SUI) - Sui 主网
- **Bitcoin** (BTC) - 比特币主网

## 🏗️ 技术架构

### 后端
- **语言**: Python 3.9+
- **框架**: FastAPI
- **包管理**: uv
- **区块链**: web3.py, httpx (多链支持)
- **价格数据**: CoinGecko API
- **数据库**: SQLite with aiosqlite
- **异步**: asyncio, aiohttp

### 前端
- **技术**: 纯 HTML5, CSS3, JavaScript (ES6+)
- **设计**: 响应式，移动优先
- **交互**: 现代化，直观的用户界面

## 🚀 快速开始

### 环境要求

- Python 3.9 或更高版本
- uv (Python 包管理器)
- 现代浏览器
- 互联网连接（用于价格数据）

### 安装步骤

1. **克隆仓库**
   ```bash
   git clone git@github.com:scdotbox/crypto_asset.git
   cd Cryptocurrency_Asset_Manager
   ```

2. **快速启动（推荐）**
   ```bash
   # 自动清理端口并启动所有服务
   ./start_project.sh
   ```

3. **手动设置**
   ```bash
   # 后端设置
   cd backend
   uv venv
   source .venv/bin/activate  # Linux/Mac
   # 或 .venv\Scripts\activate  # Windows
   uv pip install -e .
   
   # 启动后端
   uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8010
   
   # 前端设置（新终端）
   cd frontend
   python -m http.server 8020
   ```

### 访问应用

- 🎨 **前端界面**: http://localhost:8020
- 📡 **API 文档**: http://localhost:8010/docs
- 📖 **ReDoc 文档**: http://localhost:8010/redoc
- 🔗 **API 根路径**: http://localhost:8010

## 📁 项目结构

```
Cryptocurrency_Asset_Manager/
├── backend/                    # 后端 API 服务
│   ├── app/
│   │   ├── core/              # 核心配置和工具
│   │   ├── models/            # 数据模型和架构
│   │   ├── routers/           # API 路由处理器
│   │   ├── services/          # 业务逻辑服务
│   │   └── main.py           # FastAPI 应用入口点
│   ├── data/                  # 数据库和数据文件
│   ├── pyproject.toml        # Python 项目配置
│   └── requirements.txt      # Python 依赖
├── frontend/                  # 前端 Web 界面
│   ├── css/                  # 样式表
│   ├── js/                   # JavaScript 模块
│   │   └── modules/          # 模块化 JS 组件
│   └── index.html           # 主 HTML 文件
├── data/                     # 应用数据和备份
│   ├── backup_*/            # 数据库备份
│   └── history/             # 历史数据
├── docs/                     # 文档
├── logs/                     # 应用日志
├── tests/                    # 测试文件
├── start_project.sh         # 项目启动脚本
└── README.md               # 项目说明文件
```

## 🔧 配置

### 环境变量

在 backend 目录下创建 `.env` 文件：

```bash
# 价格服务配置
PRICE_CACHE_TTL=300              # 价格缓存生存时间（秒），默认300
PRICE_BATCH_SIZE=50              # 批量查询大小，默认50
PRICE_RATE_LIMIT_DELAY=1.2       # 请求间隔（秒），默认1.2
PRICE_MAX_RETRIES=3              # 最大重试次数，默认3
PRICE_RETRY_BASE_DELAY=2         # 重试基础延迟（秒），默认2

# CoinGecko API（可选，提高速率限制）
COINGECKO_API_KEY=your_api_key_here

# 应用设置
DEBUG=true                       # 启用调试模式
LOG_LEVEL=INFO                   # 日志级别
HOST=0.0.0.0                    # 服务器主机
PORT=8010                       # 服务器端口
```

## 📋 API 端点

### 资产管理
- `POST /api/assets` - 添加新资产
- `GET /api/assets` - 获取资产列表
- `DELETE /api/assets/{asset_id}` - 删除资产
- `GET /api/assets/summary` - 获取资产汇总

### 价格服务管理
- `GET /api/price-service/stats` - 获取缓存和请求统计信息
- `POST /api/price-service/clear-cache` - 清空所有价格缓存
- `POST /api/price-service/clear-expired-cache` - 清理过期缓存

### 代币管理
- `GET /api/tokens/search` - 搜索代币
- `GET /api/tokens/{token_id}` - 获取代币详情

### 区块链服务
- `GET /api/blockchain/balance` - 获取钱包余额
- `GET /api/blockchain/chains` - 获取支持的链

### 历史数据
- `GET /api/history/snapshots` - 获取历史快照
- `POST /api/history/snapshot` - 创建手动快照

## 🚀 性能优化

### 减少 API 调用
- **批量查询**: 将多个单独的价格查询合并为批量请求
- **智能缓存**: 相同代币在缓存有效期内不会重复查询
- **预加载**: 在获取资产列表时批量预加载所有价格

### 提高响应速度
- **并发处理**: 余额查询和价格查询并发执行
- **缓存命中**: 缓存命中时响应时间从秒级降低到毫秒级
- **速率限制处理**: 智能请求间隔避免 API 限制

### 缓存策略
- **时间戳缓存**: 每个价格数据都有时间戳，自动过期清理
- **LRU 缓存**: 代币映射使用 LRU 缓存，提高查询效率
- **可配置 TTL**: 缓存生存时间可通过环境变量配置

## 🛠️ 故障排除

### 端口冲突

如果遇到 "Address already in use" 错误：

```bash
# 查看端口使用情况
lsof -i :8010  # 后端端口
lsof -i :8020  # 前端端口

# 终止占用端口的进程
kill -9 <进程ID>

# 或者批量清理
pkill -f "uvicorn.*8010"
pkill -f "frontend_server.py"
```

### 常见问题

1. **端口被占用**: 使用上述端口清理命令
2. **服务启动失败**: 检查 Python 环境和依赖
3. **API 调用失败**: 检查网络连接和 API 密钥配置
4. **价格数据不加载**: 检查 CoinGecko API 状态和速率限制

## 🧪 测试

```bash
# 运行测试
cd tests
python -m pytest

# 运行覆盖率测试
python -m pytest --cov=app
```

## 📈 监控

应用提供内置监控端点：

- `/health` - 健康检查端点
- `/api/price-service/stats` - 价格服务统计
- 应用日志存储在 `logs/` 目录中

## 🤝 贡献

我们欢迎贡献！请查看我们的[贡献指南](CONTRIBUTING.md)了解详情。

1. Fork 仓库
2. 创建您的功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交您的更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开一个 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🙏 致谢

- [CoinGecko](https://www.coingecko.com/) 提供加密货币价格数据
- [FastAPI](https://fastapi.tiangolo.com/) 提供优秀的 Web 框架
- [web3.py](https://web3py.readthedocs.io/) 提供以太坊区块链集成
- 所有帮助改进此项目的贡献者

## 📞 支持

如果您有任何问题或需要帮助：

- 📧 邮箱: dev@example.com
- 🐛 问题反馈: [GitHub Issues](https://github.com/scdotbox/crypto_asset/issues)
- 💬 讨论: [GitHub Discussions](https://github.com/yourusername/cryptocurrency-asset-manager/discussions)

---

⭐ 如果您觉得这个项目有帮助，请考虑在 GitHub 上给它一个星标！

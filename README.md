# Cryptocurrency Asset Manager

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

[中文版本](README_zh.md) | English

A comprehensive web application for managing multi-chain cryptocurrency assets with real-time price monitoring and portfolio management capabilities.

## ✨ Features

- 🔗 **Multi-Chain Support**: Ethereum, Arbitrum, Base, Polygon, BSC, Solana, Sui, Bitcoin
- 💰 **Real-Time Pricing**: Integrated with CoinGecko API for live token prices
- 📊 **Asset Management**: Add, view, and delete cryptocurrency assets
- 🏷️ **Tagging System**: Custom tags for asset categorization and management
- 📈 **Historical Data**: Track asset value changes over time
- 🚀 **Performance Optimized**: Smart caching and batch queries to reduce API calls
- 📱 **Responsive Design**: Mobile-first, modern user interface
- 🔄 **Auto-Refresh**: Real-time portfolio updates

## 🌐 Supported Blockchains

### EVM Compatible Chains
- **Ethereum** (ETH) - Ethereum Mainnet
- **Arbitrum One** (ETH) - Ethereum L2 Scaling Network
- **Base** (ETH) - Coinbase's L2 Network
- **Polygon** (MATIC) - Polygon Mainnet
- **BNB Smart Chain** (BNB) - Binance Smart Chain

### Non-EVM Chains
- **Solana** (SOL) - Solana Mainnet
- **Sui** (SUI) - Sui Mainnet
- **Bitcoin** (BTC) - Bitcoin Mainnet

## 🏗️ Tech Stack

### Backend
- **Language**: Python 3.9+
- **Framework**: FastAPI
- **Package Manager**: uv
- **Blockchain**: web3.py, httpx (multi-chain support)
- **Price Data**: CoinGecko API
- **Database**: SQLite with aiosqlite
- **Async**: asyncio, aiohttp

### Frontend
- **Technology**: Pure HTML5, CSS3, JavaScript (ES6+)
- **Design**: Responsive, mobile-first approach
- **UI/UX**: Modern, intuitive interface

## 🚀 Quick Start

### Prerequisites

- Python 3.9 or higher
- uv (Python package manager)
- Modern web browser
- Internet connection for price data

### Installation

1. **Clone the repository**
   ```bash
   git clone git@github.com:scdotbox/crypto_asset.git
   cd Cryptocurrency_Asset_Manager
   ```

2. **Quick Start (Recommended)**
   ```bash
   # Automatically clean ports and start all services
   ./start_project.sh
   ```

3. **Manual Setup**
   ```bash
   # Backend setup
   cd backend
   uv venv
   source .venv/bin/activate  # Linux/Mac
   # or .venv\Scripts\activate  # Windows
   uv pip install -e .
   
   # Start backend
   uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8010
   
   # Frontend setup (new terminal)
   cd frontend
   python -m http.server 8020
   ```

### Access the Application

- 🎨 **Frontend Interface**: http://localhost:8020
- 📡 **API Documentation**: http://localhost:8010/docs
- 📖 **ReDoc Documentation**: http://localhost:8010/redoc
- 🔗 **API Root**: http://localhost:8010

## 📁 Project Structure

```
Cryptocurrency_Asset_Manager/
├── backend/                    # Backend API service
│   ├── app/
│   │   ├── core/              # Core configurations and utilities
│   │   ├── models/            # Data models and schemas
│   │   ├── routers/           # API route handlers
│   │   ├── services/          # Business logic services
│   │   └── main.py           # FastAPI application entry point
│   ├── data/                  # Database and data files
│   ├── pyproject.toml        # Python project configuration
│   └── requirements.txt      # Python dependencies
├── frontend/                  # Frontend web interface
│   ├── css/                  # Stylesheets
│   ├── js/                   # JavaScript modules
│   │   └── modules/          # Modular JS components
│   └── index.html           # Main HTML file
├── data/                     # Application data and backups
│   ├── backup_*/            # Database backups
│   └── history/             # Historical data
├── docs/                     # Documentation
├── logs/                     # Application logs
├── tests/                    # Test files
├── start_project.sh         # Project startup script
└── README.md               # This file
```

## 🔧 Configuration

### Environment Variables

Create a `.env` file in the backend directory:

```bash
# Price service configuration
PRICE_CACHE_TTL=300              # Price cache TTL in seconds (default: 300)
PRICE_BATCH_SIZE=50              # Batch query size (default: 50)
PRICE_RATE_LIMIT_DELAY=1.2       # Request interval in seconds (default: 1.2)
PRICE_MAX_RETRIES=3              # Maximum retry attempts (default: 3)
PRICE_RETRY_BASE_DELAY=2         # Retry base delay in seconds (default: 2)

# CoinGecko API (optional, for higher rate limits)
COINGECKO_API_KEY=your_api_key_here

# Application settings
DEBUG=true                       # Enable debug mode
LOG_LEVEL=INFO                   # Logging level
HOST=0.0.0.0                    # Server host
PORT=8010                       # Server port
```

## 📋 API Endpoints

### Asset Management
- `POST /api/assets` - Add new asset
- `GET /api/assets` - Get asset list
- `DELETE /api/assets/{asset_id}` - Delete asset
- `GET /api/assets/summary` - Get asset summary

### Price Service Management
- `GET /api/price-service/stats` - Get cache and request statistics
- `POST /api/price-service/clear-cache` - Clear all price cache
- `POST /api/price-service/clear-expired-cache` - Clear expired cache

### Token Management
- `GET /api/tokens/search` - Search tokens
- `GET /api/tokens/{token_id}` - Get token details

### Blockchain Services
- `GET /api/blockchain/balance` - Get wallet balance
- `GET /api/blockchain/chains` - Get supported chains

### Historical Data
- `GET /api/history/snapshots` - Get historical snapshots
- `POST /api/history/snapshot` - Create manual snapshot

## 🚀 Performance Optimizations

### Reduced API Calls
- **Batch Queries**: Combine multiple individual price queries into batch requests
- **Smart Caching**: Same tokens won't be queried repeatedly within cache validity period
- **Preloading**: Batch preload all prices when fetching asset lists

### Improved Response Speed
- **Concurrent Processing**: Balance queries and price queries execute concurrently
- **Cache Hits**: Response time reduced from seconds to milliseconds on cache hits
- **Rate Limit Handling**: Intelligent request spacing to avoid API limits

### Caching Strategy
- **Timestamp-based Cache**: Each price data has timestamps with automatic expiration
- **LRU Cache**: Token mapping uses LRU cache for improved query efficiency
- **Configurable TTL**: Cache lifetime configurable via environment variables

## 🛠️ Troubleshooting

### Port Conflicts

If you encounter "Address already in use" errors:

```bash
# Check port usage
lsof -i :8010  # Backend port
lsof -i :8020  # Frontend port

# Kill processes using ports
kill -9 <process_id>

# Or use batch cleanup
pkill -f "uvicorn.*8010"
pkill -f "frontend_server.py"
```

### Common Issues

1. **Port occupied**: Use port cleanup commands above
2. **Service startup failure**: Check Python environment and dependencies
3. **API call failures**: Verify network connection and API key configuration
4. **Price data not loading**: Check CoinGecko API status and rate limits

## 🧪 Testing

```bash
# Run tests
cd tests
python -m pytest

# Run with coverage
python -m pytest --cov=app
```

## 📈 Monitoring

The application provides built-in monitoring endpoints:

- `/health` - Health check endpoint
- `/api/price-service/stats` - Price service statistics
- Application logs are stored in the `logs/` directory

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [CoinGecko](https://www.coingecko.com/) for providing cryptocurrency price data
- [FastAPI](https://fastapi.tiangolo.com/) for the excellent web framework
- [web3.py](https://web3py.readthedocs.io/) for Ethereum blockchain integration
- All contributors who have helped improve this project

## 📞 Support

If you have any questions or need help:

- 📧 Email: dev@example.com
- 🐛 Issues: [GitHub Issues](https://github.com/scdotbox/crypto_asset/issues)
- 💬 Discussions: [GitHub Discussions](https://github.com/scdotbox/crypto_asset/discussions)

---

⭐ If you find this project helpful, please consider giving it a star on GitHub!
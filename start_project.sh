#!/bin/bash

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 启动加密货币资产管理...${NC}"

# 定义端口
BACKEND_PORT=8010
FRONTEND_PORT=8020

# 数据源配置变量
BACKEND_SCRIPT="app.main:app"

# 设置环境变量
setup_environment() {
    echo -e "${BLUE}⚙️  配置环境变量...${NC}"
    
    echo -e "${CYAN}🔗 传统模式配置:${NC}"
    echo -e "   • 手动添加资产: 启用"
    echo -e "   • 区块链 RPC: 启用"
    echo -e "   • 价格查询: 启用"
}

# 显示功能说明
show_features() {
    echo -e "\n${PURPLE}📋 可用功能:${NC}"
    echo -e "${GREEN}✅ 手动添加资产${NC}"
    echo -e "${GREEN}✅ 区块链 RPC 查询${NC}"
    echo -e "${GREEN}✅ 价格查询${NC}"
    echo -e "${GREEN}✅ 资产组合管理${NC}"
    echo -e "${GREEN}✅ 实时价格监控${NC}"
}

# 检查并清理端口
check_and_kill_port() {
    local port=$1
    local service_name=$2
    
    echo -e "${CYAN}🔍 检查端口 $port ($service_name)...${NC}"
    
    # 多次尝试清理端口
    for attempt in 1 2 3; do
        if lsof -i :$port > /dev/null 2>&1; then
            echo -e "${YELLOW}⚠️  端口 $port 已被占用，正在清理（尝试 $attempt/3）...${NC}"
            
            # 获取占用端口的进程ID
            local pids=$(lsof -ti :$port)
            if [ -n "$pids" ]; then
                echo -e "${YELLOW}   终止进程: $pids${NC}"
                # 先尝试优雅关闭
                echo "$pids" | xargs kill 2>/dev/null || true
                sleep 2
                
                # 如果还在运行，强制终止
                if lsof -i :$port > /dev/null 2>&1; then
                    echo -e "${YELLOW}   强制终止进程...${NC}"
                    echo "$pids" | xargs kill -9 2>/dev/null || true
                    sleep 2
                fi
            fi
        else
            echo -e "${GREEN}✅ 端口 $port 已释放${NC}"
            return 0
        fi
    done
    
    # 最后检查
    if lsof -i :$port > /dev/null 2>&1; then
        echo -e "${RED}❌ 无法释放端口 $port，请手动检查${NC}"
        echo -e "${YELLOW}💡 您可以运行: lsof -i :$port 查看占用进程${NC}"
        return 1
    else
        echo -e "${GREEN}✅ 端口 $port 已成功释放${NC}"
        return 0
    fi
}

# 启动后端服务
start_backend() {
    echo -e "${BLUE}📡 启动后端服务...${NC}"
    
    # 清理端口
    check_and_kill_port $BACKEND_PORT "后端"
    
    echo -e "${CYAN}🚀 启动 FastAPI 服务${NC}"
    cd backend && uv run uvicorn $BACKEND_SCRIPT --host 0.0.0.0 --port $BACKEND_PORT --reload &
    
    BACKEND_PID=$!
    
    # 等待后端启动
    echo -e "${YELLOW}⏳ 等待后端服务启动...${NC}"
    
    # 增加等待时间，并进行多次检查
    max_attempts=12  # 最多尝试12次
    attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        echo -e "${YELLOW}   尝试 $attempt/$max_attempts...${NC}"
        
        # 等待5秒
        sleep 5
        
        # 检查后端是否启动成功
        if curl -s --max-time 10 http://localhost:$BACKEND_PORT/health > /dev/null 2>&1; then
            echo -e "${GREEN}✅ 后端服务启动成功${NC}"
            return 0
        fi
        
        # 检查进程是否还在运行
        if ! kill -0 $BACKEND_PID 2>/dev/null; then
            echo -e "${RED}❌ 后端进程已退出${NC}"
            return 1
        fi
        
        attempt=$((attempt + 1))
    done
    
    # 如果所有尝试都失败了
    echo -e "${RED}❌ 后端服务启动失败（超时）${NC}"
    echo -e "${YELLOW}💡 这可能是由于API速率限制导致的，请稍后重试${NC}"
    kill $BACKEND_PID 2>/dev/null || true
    return 1
}

# 启动前端服务
start_frontend() {
    echo -e "${BLUE}🎨 启动前端服务...${NC}"
    
    # 清理端口
    check_and_kill_port $FRONTEND_PORT "前端"
    
    # 创建临时的Python HTTP服务器脚本
    cat > /tmp/frontend_server.py << 'EOF'
#!/usr/bin/env python3
"""
简单的HTTP服务器，用于提供前端静态文件
"""
import http.server
import socketserver
import os
import sys
import socket
from urllib.parse import urlparse

class CustomHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()
    
    def do_GET(self):
        # 如果请求根路径，重定向到index.html
        if self.path == '/':
            self.path = '/index.html'
        return super().do_GET()

class ReusableTCPServer(socketserver.TCPServer):
    """允许端口重用的TCP服务器"""
    allow_reuse_address = True
    
    def server_bind(self):
        # 设置 SO_REUSEADDR 选项
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # 在 macOS 上设置 SO_REUSEPORT 选项
        if hasattr(socket, 'SO_REUSEPORT'):
            try:
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except OSError:
                pass  # 如果不支持就忽略
        super().server_bind()

if __name__ == "__main__":
    PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8020
    DIRECTORY = sys.argv[2] if len(sys.argv) > 2 else "."
    
    os.chdir(DIRECTORY)
    
    try:
        with ReusableTCPServer(("", PORT), CustomHTTPRequestHandler) as httpd:
            print(f"🎨 前端服务器启动在端口 {PORT}")
            print(f"📁 服务目录: {os.getcwd()}")
            httpd.serve_forever()
    except OSError as e:
        if e.errno == 48:  # Address already in use
            print(f"❌ 端口 {PORT} 已被占用")
            print(f"💡 请运行 './cleanup_ports.sh' 清理端口")
            sys.exit(1)
        else:
            raise
EOF

    # 启动前端服务器
    cd "$(dirname "$0")/frontend" && python3 /tmp/frontend_server.py $FRONTEND_PORT . &
    FRONTEND_PID=$!
    
    # 等待前端启动
    sleep 2
    echo -e "${GREEN}✅ 前端服务启动成功${NC}"
}

# 显示服务信息
show_service_info() {
    echo -e "\n${GREEN}🎉 服务启动完成!${NC}"
    echo -e "${GREEN}📡 后端服务: http://localhost:$BACKEND_PORT${NC}"
    echo -e "${GREEN}🎨 前端服务: http://localhost:$FRONTEND_PORT${NC}"
    echo -e "${GREEN}📚 API文档: http://localhost:$BACKEND_PORT/docs${NC}"
    echo -e "${GREEN}📖 ReDoc文档: http://localhost:$BACKEND_PORT/redoc${NC}"
    
    echo -e "\n${CYAN}🔗 主要 API 端点:${NC}"
    echo -e "${CYAN}   • 添加资产: POST /api/assets${NC}"
    echo -e "${CYAN}   • 获取资产: GET /api/assets${NC}"
    echo -e "${CYAN}   • 快速添加: POST /api/assets/quick-add${NC}"
    echo -e "${CYAN}   • 支持的链: GET /api/chains${NC}"
    echo -e "${CYAN}   • 代币库: GET /api/tokens${NC}"
    
    echo -e "\n${PURPLE}💡 使用提示:${NC}"
    echo -e "${PURPLE}   • 访问前端界面进行可视化操作${NC}"
    echo -e "${PURPLE}   • 查看 API 文档了解详细接口${NC}"
    echo -e "${PURPLE}   • 使用快速添加功能简化资产管理${NC}"
}

# 停止服务
stop_services() {
    echo -e "${YELLOW}🛑 正在停止服务...${NC}"
    
    # 停止已知的进程ID
    if [ -n "$BACKEND_PID" ] && kill -0 $BACKEND_PID 2>/dev/null; then
        echo -e "${YELLOW}   停止后端进程 $BACKEND_PID...${NC}"
        kill $BACKEND_PID 2>/dev/null || true
        sleep 2
        # 如果还在运行，强制终止
        if kill -0 $BACKEND_PID 2>/dev/null; then
            kill -9 $BACKEND_PID 2>/dev/null || true
        fi
    fi
    
    if [ -n "$FRONTEND_PID" ] && kill -0 $FRONTEND_PID 2>/dev/null; then
        echo -e "${YELLOW}   停止前端进程 $FRONTEND_PID...${NC}"
        kill $FRONTEND_PID 2>/dev/null || true
        sleep 2
        # 如果还在运行，强制终止
        if kill -0 $FRONTEND_PID 2>/dev/null; then
            kill -9 $FRONTEND_PID 2>/dev/null || true
        fi
    fi
    
    # 确保端口被释放
    echo -e "${YELLOW}🧹 清理端口...${NC}"
    check_and_kill_port $BACKEND_PORT "后端"
    check_and_kill_port $FRONTEND_PORT "前端"
    
    # 额外清理：查找并终止可能的残留进程
    echo -e "${YELLOW}🔍 检查残留进程...${NC}"
    
    # 清理可能的uvicorn进程
    pkill -f "uvicorn.*$BACKEND_PORT" 2>/dev/null || true
    
    # 清理可能的Python HTTP服务器进程
    pkill -f "frontend_server.py" 2>/dev/null || true
    pkill -f "python.*$FRONTEND_PORT" 2>/dev/null || true
    
    # 清理临时文件
    rm -f /tmp/frontend_server.py
    
    echo -e "${GREEN}🛑 所有服务已停止${NC}"
}

# 初始清理函数
initial_cleanup() {
    echo -e "${BLUE}🧹 执行启动前清理...${NC}"
    
    # 清理可能残留的进程
    pkill -f "uvicorn.*$BACKEND_PORT" 2>/dev/null || true
    pkill -f "frontend_server.py" 2>/dev/null || true
    pkill -f "python.*$FRONTEND_PORT" 2>/dev/null || true
    
    # 清理端口
    check_and_kill_port $BACKEND_PORT "后端"
    check_and_kill_port $FRONTEND_PORT "前端"
    
    # 清理临时文件
    rm -f /tmp/frontend_server.py
    
    echo -e "${GREEN}✅ 启动前清理完成${NC}"
}

# 主函数
main() {
    # 处理命令行参数
    if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
        echo "用法: $0 [选项]"
        echo "选项:"
        echo "  --help, -h     显示帮助信息"
        echo ""
        echo "功能说明:"
        echo "  • 手动添加和管理加密货币资产"
        echo "  • 实时价格查询和监控"
        echo "  • 支持多种区块链网络"
        echo "  • 资产组合统计和分析"
        exit 0
    fi
    
    # 执行启动前清理
    initial_cleanup
    
    # 设置环境
    setup_environment
    
    # 显示功能说明
    show_features
    
    # 启动服务
    start_backend
    start_frontend
    
    # 显示服务信息
    show_service_info
    
    # 等待用户输入停止服务
    echo -e "\n${YELLOW}按 Enter 键停止所有服务...${NC}"
    read
    
    # 停止服务
    stop_services
}

# 设置信号处理
trap stop_services EXIT INT TERM

# 运行主函数
main "$@"
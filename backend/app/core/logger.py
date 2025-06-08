"""
统一日志配置模块

提供项目级别的统一日志配置，支持：
- 按小时轮转的日志文件
- 不同级别的日志分离
- 统一的日志格式
- 异步日志处理
- 集中化配置管理
"""

import logging
import logging.handlers
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
import asyncio
import queue
import threading
import time

from app.core.config import settings


class ColoredFormatter(logging.Formatter):
    """带颜色的控制台日志格式化器"""
    
    # ANSI颜色代码
    COLORS = {
        'DEBUG': '\033[36m',      # 青色
        'INFO': '\033[32m',       # 绿色
        'WARNING': '\033[33m',    # 黄色
        'ERROR': '\033[31m',      # 红色
        'CRITICAL': '\033[35m',   # 紫色
        'RESET': '\033[0m'        # 重置
    }
    
    def format(self, record):
        """格式化日志记录，添加颜色"""
        # 获取原始格式化结果
        formatted = super().format(record)
        
        # 添加颜色
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']
        
        return f"{color}{formatted}{reset}"


class AsyncFileHandler(logging.Handler):
    """异步文件处理器，避免I/O阻塞"""
    
    def __init__(self, filename: str, mode: str = 'a', encoding: str = 'utf-8'):
        super().__init__()
        self.filename = filename
        self.mode = mode
        self.encoding = encoding
        self.queue = queue.Queue()
        self.thread = None
        self.stop_event = threading.Event()
        self._start_thread()
    
    def _start_thread(self):
        """启动后台写入线程"""
        self.thread = threading.Thread(target=self._write_loop, daemon=True)
        self.thread.start()
    
    def _write_loop(self):
        """后台写入循环"""
        while not self.stop_event.is_set():
            try:
                # 等待日志记录，超时检查停止事件
                record = self.queue.get(timeout=1.0)
                if record is None:  # 停止信号
                    break
                
                # 确保目录存在
                os.makedirs(os.path.dirname(self.filename), exist_ok=True)
                
                # 写入文件
                with open(self.filename, self.mode, encoding=self.encoding) as f:
                    f.write(self.format(record) + '\n')
                    f.flush()
                
                self.queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                # 避免日志处理器本身的错误影响应用
                print(f"AsyncFileHandler error: {e}", file=sys.stderr)
    
    def emit(self, record):
        """发送日志记录到队列"""
        try:
            self.queue.put(record, block=False)
        except queue.Full:
            # 队列满时丢弃日志，避免阻塞
            pass
    
    def close(self):
        """关闭处理器"""
        self.stop_event.set()
        self.queue.put(None)  # 发送停止信号
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5.0)
        super().close()


class HourlyRotatingFileHandler(logging.handlers.TimedRotatingFileHandler):
    """按小时轮转的文件处理器"""
    
    def __init__(self, filename: str, backup_count: int = 24 * 7):  # 默认保留7天
        """
        初始化按小时轮转的文件处理器
        
        Args:
            filename: 日志文件路径
            backup_count: 保留的备份文件数量，默认168个（7天 * 24小时）
        """
        # 确保目录存在
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        super().__init__(
            filename=filename,
            when='H',  # 按小时轮转
            interval=1,  # 每1小时轮转一次
            backupCount=backup_count,
            encoding='utf-8',
            delay=False,
            utc=False
        )
        
        # 自定义文件名格式：app_2024-01-01_14.log
        self.suffix = "%Y-%m-%d_%H"
    
    def getFilesToDelete(self):
        """获取需要删除的过期文件"""
        # 调用父类方法获取基础列表
        files_to_delete = super().getFilesToDelete()
        
        # 可以在这里添加额外的清理逻辑
        return files_to_delete


class LoggerManager:
    """日志管理器 - 统一管理项目中的所有日志"""
    
    _instance: Optional['LoggerManager'] = None
    _initialized: bool = False
    
    def __new__(cls) -> 'LoggerManager':
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """初始化日志管理器"""
        if self._initialized:
            return
        
        # 修改日志目录路径：从backend目录内的logs改为backend所在目录的logs
        # 获取当前文件所在目录（backend/app/core/）
        current_dir = Path(__file__).parent
        # 向上三级到达项目根目录，然后进入logs目录
        self.log_dir = current_dir.parent.parent.parent / "logs"
        self.log_dir.mkdir(exist_ok=True)
        
        # 日志配置
        self.log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
        self.log_format = "%(asctime)s | %(name)-20s | %(levelname)-8s | %(funcName)-15s:%(lineno)-4d | %(message)s"
        self.date_format = "%Y-%m-%d %H:%M:%S"
        
        # 存储已创建的处理器，避免重复创建
        self.handlers: Dict[str, logging.Handler] = {}
        
        # 配置根日志器
        self._setup_root_logger()
        
        self._initialized = True
    
    def _setup_root_logger(self):
        """配置根日志器"""
        root_logger = logging.getLogger()
        root_logger.setLevel(self.log_level)
        
        # 清除现有处理器
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # 添加控制台处理器
        console_handler = self._create_console_handler()
        root_logger.addHandler(console_handler)
        
        # 添加主应用日志文件处理器
        app_handler = self._create_file_handler("app")
        root_logger.addHandler(app_handler)
        
        # 添加错误日志文件处理器
        error_handler = self._create_file_handler("error", level=logging.ERROR)
        root_logger.addHandler(error_handler)
    
    def _create_console_handler(self) -> logging.Handler:
        """创建控制台处理器"""
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(self.log_level)
        
        # 使用带颜色的格式化器
        formatter = ColoredFormatter(
            fmt=self.log_format,
            datefmt=self.date_format
        )
        handler.setFormatter(formatter)
        
        return handler
    
    def _create_file_handler(self, name: str, level: Optional[int] = None) -> logging.Handler:
        """
        创建文件处理器
        
        Args:
            name: 日志文件名前缀
            level: 日志级别，默认使用全局级别
            
        Returns:
            配置好的文件处理器
        """
        actual_level = level if level is not None else self.log_level
        
        # 生成文件路径
        log_file = self.log_dir / f"{name}.log"
        
        # 创建按小时轮转的处理器
        handler = HourlyRotatingFileHandler(
            filename=str(log_file),
            backup_count=24 * 7  # 保留7天的日志
        )
        handler.setLevel(actual_level)
        
        # 设置格式化器
        formatter = logging.Formatter(
            fmt=self.log_format,
            datefmt=self.date_format
        )
        handler.setFormatter(formatter)
        
        # 存储处理器引用
        self.handlers[name] = handler
        
        return handler
    
    def get_logger(self, name: str) -> logging.Logger:
        """
        获取指定名称的日志器
        
        Args:
            name: 日志器名称，通常使用 __name__
            
        Returns:
            配置好的日志器实例
        """
        logger = logging.getLogger(name)
        
        # 如果是新的日志器，确保它使用正确的配置
        if not logger.handlers:
            logger.setLevel(self.log_level)
            # 不添加额外的处理器，使用根日志器的处理器
            logger.propagate = True
        
        return logger
    
    def create_service_logger(self, service_name: str) -> logging.Logger:
        """
        为特定服务创建专用日志器
        
        Args:
            service_name: 服务名称
            
        Returns:
            服务专用的日志器
        """
        logger_name = f"service.{service_name}"
        logger = logging.getLogger(logger_name)
        
        # 如果已经配置过，直接返回
        if logger.handlers:
            return logger
        
        logger.setLevel(self.log_level)
        
        # 创建服务专用的文件处理器
        service_handler = self._create_file_handler(f"service_{service_name}")
        logger.addHandler(service_handler)
        
        # 也输出到主日志
        logger.propagate = True
        
        return logger
    
    def setup_request_logging(self):
        """设置请求日志"""
        # 创建请求日志处理器
        request_handler = self._create_file_handler("requests")
        
        # 配置uvicorn访问日志
        uvicorn_access = logging.getLogger("uvicorn.access")
        uvicorn_access.addHandler(request_handler)
        
        # 配置FastAPI日志
        fastapi_logger = logging.getLogger("fastapi")
        fastapi_logger.addHandler(request_handler)
    
    def log_performance(self, operation: str, duration: float, **kwargs):
        """
        记录性能日志
        
        Args:
            operation: 操作名称
            duration: 执行时间（秒）
            **kwargs: 额外的上下文信息
        """
        perf_logger = logging.getLogger("performance")
        
        # 如果还没有性能日志处理器，创建一个
        if not any(isinstance(h, HourlyRotatingFileHandler) and "performance" in str(h.baseFilename) 
                  for h in perf_logger.handlers):
            perf_handler = self._create_file_handler("performance")
            perf_logger.addHandler(perf_handler)
            perf_logger.propagate = False  # 不传播到根日志器
        
        # 构建日志消息
        context = " | ".join([f"{k}={v}" for k, v in kwargs.items()])
        message = f"PERF | {operation} | {duration:.3f}s"
        if context:
            message += f" | {context}"
        
        perf_logger.info(message)
    
    def cleanup_old_logs(self, days: int = 7):
        """
        清理过期日志文件
        
        Args:
            days: 保留天数
        """
        cutoff_time = time.time() - (days * 24 * 3600)
        
        for log_file in self.log_dir.glob("*.log*"):
            try:
                if log_file.stat().st_mtime < cutoff_time:
                    log_file.unlink()
                    logging.info(f"删除过期日志文件: {log_file}")
            except Exception as e:
                logging.error(f"删除日志文件失败 {log_file}: {e}")
    
    def get_log_stats(self) -> Dict[str, Any]:
        """获取日志统计信息"""
        stats = {
            "log_directory": str(self.log_dir),
            "log_level": logging.getLevelName(self.log_level),
            "handlers_count": len(self.handlers),
            "log_files": []
        }
        
        # 统计日志文件
        for log_file in self.log_dir.glob("*.log*"):
            try:
                stat = log_file.stat()
                stats["log_files"].append({
                    "name": log_file.name,
                    "size_mb": round(stat.st_size / 1024 / 1024, 2),
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
            except Exception:
                pass
        
        return stats


# 全局日志管理器实例
logger_manager = LoggerManager()


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    获取日志器的便捷函数
    
    Args:
        name: 日志器名称，默认使用调用者的模块名
        
    Returns:
        配置好的日志器实例
        
    Example:
        >>> from app.core.logger import get_logger
        >>> logger = get_logger(__name__)
        >>> logger.info("这是一条信息日志")
    """
    actual_name = name
    if actual_name is None:
        # 自动获取调用者的模块名
        import inspect
        frame = inspect.currentframe()
        if frame is not None and frame.f_back is not None:
            actual_name = frame.f_back.f_globals.get('__name__', 'unknown')
        else:
            actual_name = 'unknown'
    
    return logger_manager.get_logger(actual_name)


def setup_logging():
    """初始化项目日志系统"""
    # 确保日志管理器已初始化
    logger_manager._setup_root_logger()
    
    # 设置请求日志
    logger_manager.setup_request_logging()
    
    # 记录初始化完成
    logger = get_logger(__name__)
    logger.info("统一日志系统初始化完成")
    logger.info(f"日志目录: {logger_manager.log_dir}")
    logger.info(f"日志级别: {logging.getLevelName(logger_manager.log_level)}")


def log_performance(operation: str, duration: float, **kwargs):
    """性能日志记录的便捷函数"""
    logger_manager.log_performance(operation, duration, **kwargs)


# 性能监控装饰器
def performance_monitor(operation_name: Optional[str] = None):
    """
    性能监控装饰器
    
    Args:
        operation_name: 操作名称，默认使用函数名
        
    Example:
        >>> @performance_monitor("数据库查询")
        >>> async def query_database():
        >>>     # 数据库操作
        >>>     pass
    """
    def decorator(func):
        import functools
        import time
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                op_name = operation_name or f"{func.__module__}.{func.__name__}"
                log_performance(op_name, duration)
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                op_name = operation_name or f"{func.__module__}.{func.__name__}"
                log_performance(op_name, duration)
        
        # 根据函数类型返回对应的包装器
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator 
# -*- coding: utf-8 -*-
"""
日志工具模块

提供全局 logger，按日期滚动输出，支持超期日志自动清理。
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from backend.config.settings import (
    LOG_DATE_FORMAT,
    LOG_DIR,
    LOG_FORMAT,
    LOG_RETENTION_DAYS,
)

# 全局 logger 缓存
_loggers: dict[str, logging.Logger] = {}

# logs 目录是否已创建标记
_logs_dir_created: bool = False

# 清理是否已执行标记
_cleanup_done: bool = False


def _ensure_logs_dir() -> None:
    """确保日志目录存在，首次调用时自动创建"""
    global _logs_dir_created
    if not _logs_dir_created:
        os.makedirs(LOG_DIR, exist_ok=True)
        _logs_dir_created = True


def _cleanup_old_logs() -> None:
    """清理超过保留期限的日志文件"""
    global _cleanup_done
    if _cleanup_done:
        return

    _cleanup_done = True
    cutoff_time = time.time() - LOG_RETENTION_DAYS * 24 * 3600
    log_dir = Path(LOG_DIR)

    if not log_dir.exists():
        return

    for log_file in log_dir.glob("*.log*"):
        try:
            if log_file.stat().st_mtime < cutoff_time:
                log_file.unlink()
                logging.getLogger(__name__).info(f"已清理超期日志: {log_file.name}")
        except OSError:
            pass  # 忽略删除失败的文件


def get_logger(name: str) -> logging.Logger:
    """
    获取指定名称的 logger 实例。

    Args:
        name: logger 名称，通常使用 __name__

    Returns:
        配置好的 Logger 实例
    """
    if name in _loggers:
        return _loggers[name]

    _ensure_logs_dir()
    _cleanup_old_logs()

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # 避免重复添加 handler
    if logger.handlers:
        _loggers[name] = logger
        return logger

    # 日志格式化器
    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    # 当前日期，用于文件名
    today = datetime.now().strftime("%Y-%m-%d")

    # 主日志文件 handler (INFO 及以上)，按天滚动
    scheduler_log_path = os.path.join(LOG_DIR, f"scheduler-{today}.log")
    scheduler_handler = TimedRotatingFileHandler(
        scheduler_log_path,
        when="midnight",
        interval=1,
        backupCount=LOG_RETENTION_DAYS,
        encoding="utf-8",
    )
    scheduler_handler.setLevel(logging.INFO)
    scheduler_handler.setFormatter(formatter)
    scheduler_handler.suffix = "%Y-%m-%d"
    logger.addHandler(scheduler_handler)

    # 错误日志文件 handler (ERROR 及以上)，按天滚动
    error_log_path = os.path.join(LOG_DIR, f"error-{today}.log")
    error_handler = TimedRotatingFileHandler(
        error_log_path,
        when="midnight",
        interval=1,
        backupCount=LOG_RETENTION_DAYS,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    error_handler.suffix = "%Y-%m-%d"
    logger.addHandler(error_handler)

    # 控制台 handler (DEBUG 及以上)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    _loggers[name] = logger
    return logger

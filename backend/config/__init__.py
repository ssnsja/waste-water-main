# -*- coding: utf-8 -*-
"""配置模块"""

from backend.config.settings import (
    DB_DSN,
    DB_PASSWORD,
    DB_USER,
    LOG_DATE_FORMAT,
    LOG_DIR,
    LOG_FORMAT,
    LOG_RETENTION_DAYS,
    ORACLE_CLIENT_LIB_DIR,
    POOL_INCREMENT,
    POOL_MAX,
    POOL_MIN,
    POOL_PING_INTERVAL,
    PROJECT_ROOT,
)

__all__ = [
    "DB_DSN",
    "DB_PASSWORD",
    "DB_USER",
    "LOG_DATE_FORMAT",
    "LOG_DIR",
    "LOG_FORMAT",
    "LOG_RETENTION_DAYS",
    "ORACLE_CLIENT_LIB_DIR",
    "POOL_INCREMENT",
    "POOL_MAX",
    "POOL_MIN",
    "POOL_PING_INTERVAL",
    "PROJECT_ROOT",
]

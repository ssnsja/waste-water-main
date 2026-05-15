# -*- coding: utf-8 -*-
"""
静态配置模块

集中管理所有静态配置，不含业务逻辑。
"""

from pathlib import Path

# =============================================================================
# Oracle Thick Mode 初始化（程序启动时调用一次）
# =============================================================================
ORACLE_CLIENT_LIB_DIR: str = r"D:\oracle11\product\11.2.0\dbhome_1\bin"

# =============================================================================
# 连接池参数
# =============================================================================
DB_USER: str = "SYSTEM"
DB_PASSWORD: str = "1677903701"
DB_DSN: str = "localhost:1522/FREEPDB1"
POOL_MIN: int = 2
POOL_MAX: int = 5
POOL_INCREMENT: int = 1
POOL_PING_INTERVAL: int = 60

# =============================================================================
# 调度参数（已迁移到数据库 WW_SYSTEM_CONFIG 表）
# 以下配置仅作为默认值参考，实际运行时从数据库读取
# =============================================================================
# SCHEDULE_INTERVAL_MIN: int = 30      # 调度周期（分钟）
# MANUAL_LEVEL_STALE_THRESHOLD: int = 2  # 液位超期阈值（调度周期倍数）

# =============================================================================
# 日志参数
# =============================================================================
# 项目根目录
PROJECT_ROOT: Path = Path(__file__).parent.parent

# 日志目录
LOG_DIR: str = str(PROJECT_ROOT / "logs")

# 日志保留期限（天）
LOG_RETENTION_DAYS: int = 180

# 日志格式
LOG_FORMAT: str = "%(asctime)s [%(levelname)-8s] %(module)s.%(funcName)s - %(message)s"
LOG_DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"

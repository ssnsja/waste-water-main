# -*- coding: utf-8 -*-
"""
配置服务模块

从 DB 读取系统配置，内存缓存（TTL=5分钟），提供强类型解析接口。
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional

from backend.dao.config_dao import ConfigDAO
from backend.model import SolverParams
from backend.utils.exceptions import ConfigLoadError
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class ConfigService:
    """配置服务，带内存缓存"""

    TTL_SECONDS: int = 300  # 缓存有效期 5 分钟
    _cache: Dict[str, str] = {}
    _cache_time: Optional[datetime] = None

    def __init__(self, config_dao: ConfigDAO) -> None:
        """
        初始化配置服务。

        Args:
            config_dao: 配置 DAO 实例
        """
        self._config_dao = config_dao

    def get_all_params(self) -> SolverParams:
        """
        获取所有求解器参数。

        缓存未过期直接返回，过期则查 DB 刷新缓存后返回。

        Returns:
            求解器参数对象

        Raises:
            ConfigLoadError: 配置加载失败
        """
        if self._is_expired():
            logger.info("配置缓存已过期，重新加载...")
            try:
                self._cache = self._config_dao.get_all_configs()
                self._cache_time = datetime.now()
                logger.info(f"配置缓存刷新完成，共 {len(self._cache)} 项")
            except Exception as e:
                raise ConfigLoadError(f"加载系统配置失败: {e}") from e
        return self._parse_params(self._cache)

    def get(self, key: str) -> str:
        """
        获取配置项原始字符串值。

        Args:
            key: 配置项键名

        Returns:
            配置项值
        """
        if self._is_expired():
            self.get_all_params()  # 刷新缓存
        return self._cache.get(key, "")

    def get_float(self, key: str) -> float:
        """
        获取配置项浮点数值。

        Args:
            key: 配置项键名

        Returns:
            配置项浮点数值
        """
        value = self.get(key)
        return float(value) if value else 0.0

    def get_int(self, key: str) -> int:
        """
        获取配置项整数值。

        Args:
            key: 配置项键名

        Returns:
            配置项整数值
        """
        value = self.get(key)
        return int(value) if value else 0

    def refresh(self) -> None:
        """手动清除缓存，下次 get_all_params 会强制重读 DB。"""
        self._cache_time = None
        self._cache = {}
        logger.info("配置缓存已清除")

    def _is_expired(self) -> bool:
        """检查缓存是否过期。"""
        if self._cache_time is None:
            return True
        elapsed = (datetime.now() - self._cache_time).total_seconds()
        return elapsed > self.TTL_SECONDS

    def _parse_params(self, raw: Dict[str, str]) -> SolverParams:
        """
        解析配置字典为 SolverParams 对象。

        Args:
            raw: 配置字典

        Returns:
            求解器参数对象

        Raises:
            ConfigLoadError: 必填配置缺失
        """
        try:
            # 必填项
            tank_capacity = float(raw.get("TANK_CAPACITY"))
            process_capacity = float(raw.get("PROCESS_CAPACITY"))

            # 可选项（带默认值）
            schedule_interval_min = int(raw.get("SCHEDULE_INTERVAL_MIN", "30"))
            manual_level_stale_threshold = int(raw.get("MANUAL_LEVEL_STALE_THRESHOLD", "2"))
            safe_ratio = float(raw.get("SAFE_RATIO", "0.85"))
            warning_ratio = float(raw.get("WARNING_RATIO", "0.80"))
            alert_ratio = float(raw.get("ALERT_RATIO", "0.90"))
            emergency_ratio = float(raw.get("EMERGENCY_RATIO", "0.95"))
            min_rate_ratio = float(raw.get("MIN_RATE_RATIO", "0.30"))
            process_buffer_ratio = float(raw.get("PROCESS_BUFFER_RATIO", "1.20"))

            # 转换调度周期为小时
            schedule_interval_h = schedule_interval_min / 60.0

            return SolverParams(
                tank_capacity=tank_capacity,
                process_capacity=process_capacity,
                schedule_interval_h=schedule_interval_h,
                schedule_interval_min=schedule_interval_min,
                manual_level_stale_threshold=manual_level_stale_threshold,
                safe_ratio=safe_ratio,
                warning_ratio=warning_ratio,
                alert_ratio=alert_ratio,
                emergency_ratio=emergency_ratio,
                min_rate_ratio=min_rate_ratio,
                process_buffer_ratio=process_buffer_ratio,
            )
        except (ValueError, TypeError) as e:
            raise ConfigLoadError(f"配置参数解析失败: {e}") from e

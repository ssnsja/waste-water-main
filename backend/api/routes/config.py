# -*- coding: utf-8 -*-
"""
配置读写 API 路由

- GET  /                   获取全部系统配置
- PUT  /                   批量更新系统配置
- POST /restart-scheduler  手动重启调度器
"""

from __future__ import annotations

from typing import Dict, Optional

import oracledb
from fastapi import APIRouter, Request
from pydantic import BaseModel

from backend.api.serializers import (
    error,
    round2,
    server_error,
    success,
)
from backend.utils.exceptions import DBWriteError
from backend.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic 请求模型
# ---------------------------------------------------------------------------

class ConfigUpdateRequest(BaseModel):
    """批量更新配置请求体

    仅包含需要更新的字段，未传递的字段不更新。
    """
    tank_capacity: Optional[float] = None
    process_capacity: Optional[float] = None
    schedule_interval_min: Optional[int] = None
    manual_level_stale_threshold: Optional[int] = None
    safe_ratio: Optional[float] = None
    warning_ratio: Optional[float] = None
    alert_ratio: Optional[float] = None
    emergency_ratio: Optional[float] = None
    min_rate_ratio: Optional[float] = None
    process_buffer_ratio: Optional[float] = None


# API 字段名 → 数据库 CONFIG_KEY 映射
FIELD_TO_CONFIG_KEY = {
    "tank_capacity": "TANK_CAPACITY",
    "process_capacity": "PROCESS_CAPACITY",
    "schedule_interval_min": "SCHEDULE_INTERVAL_MIN",
    "manual_level_stale_threshold": "MANUAL_LEVEL_STALE_THRESHOLD",
    "safe_ratio": "SAFE_RATIO",
    "warning_ratio": "WARNING_RATIO",
    "alert_ratio": "ALERT_RATIO",
    "emergency_ratio": "EMERGENCY_RATIO",
    "min_rate_ratio": "MIN_RATE_RATIO",
    "process_buffer_ratio": "PROCESS_BUFFER_RATIO",
}


# ---------------------------------------------------------------------------
# 路由端点
# ---------------------------------------------------------------------------

@router.get("")
def get_config(request: Request):
    """获取全部系统配置。"""
    try:
        config_svc = request.app.state.config_svc
        params = config_svc.get_all_params()

        data = {
            "tank_capacity": params.tank_capacity,
            "process_capacity": params.process_capacity,
            "schedule_interval_min": params.schedule_interval_min,
            "manual_level_stale_threshold": params.manual_level_stale_threshold,
            "safe_ratio": params.safe_ratio,
            "warning_ratio": params.warning_ratio,
            "alert_ratio": params.alert_ratio,
            "emergency_ratio": params.emergency_ratio,
            "min_rate_ratio": params.min_rate_ratio,
            "process_buffer_ratio": params.process_buffer_ratio,
        }

        return success(data=data)

    except Exception as e:
        logger.error(f"获取系统配置失败: {e}", exc_info=True)
        return server_error(f"获取系统配置失败: {e}")


@router.put("")
def update_config(body: ConfigUpdateRequest, request: Request):
    """批量更新系统配置。

    遍历请求体，逐项更新 WW_SYSTEM_CONFIG 表。
    更新后清除配置缓存，返回 need_restart 标识。
    """
    try:
        config_svc = request.app.state.config_svc
        config_dao = config_svc._config_dao
        pool = request.app.state.pool

        # 构建配置更新字典（仅包含非 None 的字段）
        configs: Dict[str, str] = {}
        for field_name, config_key in FIELD_TO_CONFIG_KEY.items():
            value = getattr(body, field_name, None)
            if value is not None:
                configs[config_key] = str(value)

        if not configs:
            return success(
                message="无更新字段",
                data={"need_restart": False},
            )

        # 判断是否需要重启调度器（调度周期变更才需要）
        need_restart = "SCHEDULE_INTERVAL_MIN" in configs

        # 写入数据库
        conn = None
        try:
            conn = pool.acquire()
            conn.autocommit = False
            config_dao.update_batch(conn, configs)
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                pool.release(conn)

        # 清除配置缓存
        config_svc.refresh()

        if need_restart:
            message = "配置已保存至数据库，需重启调度器使配置生效"
        else:
            message = "配置已保存至数据库并生效"

        return success(
            message=message,
            data={"need_restart": need_restart},
        )

    except DBWriteError as e:
        return server_error(f"配置更新失败: {e}")
    except Exception as e:
        logger.error(f"更新系统配置失败: {e}", exc_info=True)
        return server_error(f"更新系统配置失败: {e}")


@router.post("/restart-scheduler")
def restart_scheduler(request: Request):
    """手动重启调度器（操作员确认后调用）。"""
    try:
        trigger = request.app.state.trigger

        # 重启调度器
        trigger.restart()

        interval_min = trigger.get_interval_min()

        return success(
            message="调度器已重启，新配置已生效",
            data={"interval_min": interval_min},
        )

    except Exception as e:
        logger.error(f"重启调度器失败: {e}", exc_info=True)
        return server_error(f"重启调度器失败: {e}")

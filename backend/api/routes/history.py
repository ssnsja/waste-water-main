# -*- coding: utf-8 -*-
"""
历史查询 API 路由

- GET /records  分页查询历史调度记录
- GET /trend    获取历史液位趋势数据
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Query, Request

from backend.api.serializers import (
    alert_level_to_text,
    ratio_to_percent,
    round2,
    serialize,
    server_error,
    success,
)
from backend.utils.exceptions import DBQueryError
from backend.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/records")
def get_history_records(
    request: Request,
    start_time: Optional[str] = Query(default=None, description="起始时间，ISO 8601"),
    end_time: Optional[str] = Query(default=None, description="结束时间，ISO 8601"),
    zone: Optional[str] = Query(default=None, description="液位区间筛选"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=10, ge=1, le=100, description="每页条数"),
):
    """分页查询历史调度记录（按调度批次聚合）。"""
    try:
        trigger = request.app.state.trigger
        input_dao = trigger._scheduler_svc._input_dao

        # 解析时间参数
        start_dt = None
        end_dt = None
        if start_time:
            try:
                start_dt = datetime.fromisoformat(start_time)
            except ValueError:
                pass
        if end_time:
            try:
                end_dt = datetime.fromisoformat(end_time)
            except ValueError:
                pass

        # 默认查询最近24小时
        if not start_dt:
            start_dt = datetime.now() - timedelta(hours=24)
        if not end_dt:
            end_dt = datetime.now()

        total, records = input_dao.query_records(
            start_time=start_dt,
            end_time=end_dt,
            zone=zone,
            page=page,
            page_size=page_size,
        )

        # 序列化
        serialized_records = []
        for rec in records:
            alert_info = None
            if rec.get("alert_info"):
                ai = rec["alert_info"]
                alert_info = {
                    "alert_level": ai.get("alert_level"),
                    "alert_time": serialize(ai.get("alert_time")),
                    "alert_message": ai.get("alert_message", ""),
                }

            serialized_records.append({
                "schedule_id": rec.get("schedule_id", ""),
                "schedule_time": serialize(rec.get("schedule_time")),
                "zone": rec.get("zone", ""),
                "tank_level": round2(rec.get("tank_level")),
                "level_ratio": rec.get("level_ratio"),
                "workshop_count": rec.get("workshop_count", 0),
                "solver_status": rec.get("solver_status"),
                "alert_info": alert_info,
            })

        data = {
            "total": total,
            "page": page,
            "page_size": page_size,
            "records": serialized_records,
        }

        return success(data=data)

    except DBQueryError as e:
        return server_error(f"数据库查询失败: {e}")
    except Exception as e:
        logger.error(f"查询历史记录失败: {e}", exc_info=True)
        return server_error(f"查询历史记录失败: {e}")


@router.get("/trend")
def get_history_trend(
    request: Request,
    start_time: Optional[str] = Query(default=None, description="起始时间"),
    end_time: Optional[str] = Query(default=None, description="结束时间"),
):
    """获取历史液位趋势数据。"""
    try:
        trigger = request.app.state.trigger
        tank_dao = trigger._tank_dao

        start_dt = None
        end_dt = None
        if start_time:
            try:
                start_dt = datetime.fromisoformat(start_time)
            except ValueError:
                pass
        if end_time:
            try:
                end_dt = datetime.fromisoformat(end_time)
            except ValueError:
                pass

        if not start_dt:
            start_dt = datetime.now() - timedelta(hours=24)
        if not end_dt:
            end_dt = datetime.now()

        trend_data = tank_dao.get_trend(start_time=start_dt, end_time=end_dt)

        return success(data=trend_data)

    except Exception as e:
        logger.error(f"获取趋势数据失败: {e}", exc_info=True)
        return server_error(f"获取趋势数据失败: {e}")

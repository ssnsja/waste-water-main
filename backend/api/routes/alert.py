# -*- coding: utf-8 -*-
"""
告警查询 API 路由

- GET /  分页查询告警记录
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Query, Request

from backend.api.serializers import (
    alert_level_to_text,
    round2,
    serialize,
    server_error,
    success,
)
from backend.utils.exceptions import DBQueryError
from backend.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("")
def get_alerts(
    request: Request,
    start_time: Optional[str] = Query(default=None, description="起始时间，ISO 8601"),
    end_time: Optional[str] = Query(default=None, description="结束时间，ISO 8601"),
    alert_level: Optional[int] = Query(default=None, description="告警级别: 2=告警, 3=紧急"),
    is_handled: Optional[int] = Query(default=None, description="是否已处理: 0=未处理, 1=已处理"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=10, ge=1, le=100, description="每页条数"),
):
    """分页查询告警记录。"""
    try:
        trigger = request.app.state.trigger
        alert_dao = trigger._scheduler_svc._alert_dao

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

        total, records = alert_dao.query_alerts(
            start_time=start_dt,
            end_time=end_dt,
            alert_level=alert_level,
            is_handled=is_handled,
            page=page,
            page_size=page_size,
        )

        # 序列化
        serialized_records = []
        for rec in records:
            serialized_records.append({
                "alert_id": rec.get("alert_id"),
                "schedule_id": rec.get("schedule_id", ""),
                "alert_time": serialize(rec.get("alert_time")),
                "alert_level": rec.get("alert_level"),
                "alert_level_text": alert_level_to_text(rec.get("alert_level", 0)),
                "tank_level": round2(rec.get("tank_level")),
                "level_ratio": rec.get("level_ratio"),
                "alert_message": rec.get("alert_message", ""),
                "is_handled": rec.get("is_handled", 0),
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
        logger.error(f"查询告警记录失败: {e}", exc_info=True)
        return server_error(f"查询告警记录失败: {e}")

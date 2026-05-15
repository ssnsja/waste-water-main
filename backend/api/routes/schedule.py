# -*- coding: utf-8 -*-
"""
调度详情/触发 API 路由

- GET  /{schedule_id}/detail  获取单次调度的完整详情数据
- POST /trigger               手动触发一次调度
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel, field_validator

from backend.api.serializers import (
    error,
    not_found,
    round2,
    serialize,
    server_error,
    success,
)
from backend.utils.exceptions import (
    InvalidTankLevelError,
    NoActiveWorkshopError,
)
from backend.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


class TriggerRequest(BaseModel):
    """手动触发调度请求体"""
    tank_level: float

    @field_validator("tank_level")
    @classmethod
    def validate_tank_level(cls, v):
        if v is None or v <= 0:
            raise ValueError(f"液位值非法：{v}")
        return v


@router.get("/{schedule_id}/detail")
def get_schedule_detail(schedule_id: str, request: Request):
    """获取单次调度的完整详情数据。"""
    try:
        trigger = request.app.state.trigger
        scheduler_svc = trigger._scheduler_svc

        input_dao = scheduler_svc._input_dao
        input_workshop_dao = scheduler_svc._input_workshop_dao
        result_dao = scheduler_svc._result_dao
        alert_dao = scheduler_svc._alert_dao
        workshop_dao = scheduler_svc._workshop_dao

        # 1. 获取调度输入快照
        input_snapshot = input_dao.get_by_schedule_id(schedule_id)
        if not input_snapshot:
            return not_found(f"调度批次号 {schedule_id} 不存在")

        # 2. 获取车间快照
        workshop_snapshots = input_workshop_dao.get_by_schedule_id(schedule_id)

        # 3. 获取建议排放
        result_records = result_dao.get_by_schedule_id(schedule_id)
        all_workshops = workshop_dao.get_all()
        ws_name_map = {ws.workshop_id: ws.workshop_name for ws in all_workshops}

        suggestions = []
        for r in result_records:
            suggestions.append({
                "workshop_id": r.workshop_id,
                "workshop_name": ws_name_map.get(r.workshop_id, r.workshop_id),
                "allowed_rate": round2(r.allowed_rate),
                "allowed_volume": round2(r.allowed_volume),
                "schedule_status": r.schedule_status,
                "solver_status": r.solver_status,
            })

        # 4. 获取告警记录
        alert_record = alert_dao.get_by_schedule_id(schedule_id)

        data = {
            "input_snapshot": serialize(input_snapshot),
            "workshop_snapshots": serialize(workshop_snapshots),
            "suggestions": suggestions,
            "alert_record": serialize(alert_record),
        }

        return success(data=data)

    except Exception as e:
        logger.error(f"获取调度详情失败: {e}", exc_info=True)
        return server_error(f"获取调度详情失败: {e}")


@router.post("/trigger")
def trigger_schedule(body: TriggerRequest, request: Request):
    """手动触发一次调度。"""
    try:
        trigger = request.app.state.trigger
        scheduler_svc = trigger._scheduler_svc

        summary = scheduler_svc.run(body.tank_level)

        if summary is None:
            return server_error("调度执行失败：未返回摘要信息")

        return success(
            message="调度执行成功",
            data=serialize(summary),
        )

    except InvalidTankLevelError as e:
        return error(status=400, message=str(e), http_status_code=400)
    except NoActiveWorkshopError as e:
        return error(status=400, message=f"无启用车间，调度跳过", http_status_code=400)
    except Exception as e:
        logger.error(f"手动调度执行失败: {e}", exc_info=True)
        return server_error(f"调度执行失败：{e}")

# -*- coding: utf-8 -*-
"""
Dashboard API 路由

提供调度概览数据获取接口：
- GET /overview          一次性获取全部聚合数据
- GET /tank-status       获取最新储罐状态（轮询端点）
- GET /latest-schedule   获取最新一次调度结果
- GET /recent-alerts     获取最近 N 条告警
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Query, Request

from backend.api.serializers import (
    alert_level_to_text,
    error,
    not_found,
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


@router.get("/overview")
def get_dashboard_overview(request: Request):
    """获取 Dashboard 页面所需的全部聚合数据。"""
    try:
        config_svc = request.app.state.config_svc
        trigger = request.app.state.trigger

        # 从 trigger 获取 DAO 实例
        tank_dao = trigger._tank_dao
        result_dao = trigger._scheduler_svc._result_dao
        alert_dao = trigger._scheduler_svc._alert_dao
        workshop_dao = trigger._scheduler_svc._workshop_dao

        # 1. 获取最新液位
        tank_data = tank_dao.get_latest_manual_level()
        params = config_svc.get_all_params()

        if tank_data:
            level, create_time = tank_data
            level_ratio = level / params.tank_capacity
            # 判断区间
            if level_ratio < params.warning_ratio:
                zone, k = "NORMAL", 1.0
            elif level_ratio < params.alert_ratio:
                from backend.scheduler.scheduler_service import SchedulerService
                svc = trigger._scheduler_svc
                _, k = svc._determine_zone(level, params)
                zone = "WARNING"
            elif level_ratio < params.emergency_ratio:
                zone, k = "ALERT", 0.0
            else:
                zone, k = "EMERGENCY", 0.0

            tank_status = {
                "level": round2(level),
                "ratio": ratio_to_percent(level_ratio),
                "status": zone,
                "k": round2(k),
                "predicted_level": None,
                "record_time": serialize(create_time),
            }
        else:
            tank_status = None

        # 2. 获取最新调度结果
        latest_schedule_id = result_dao.get_latest_schedule_id()
        schedule_results = None
        if latest_schedule_id:
            result_records = result_dao.get_by_schedule_id(latest_schedule_id)
            if result_records:
                total_rate = round(sum(r.allowed_rate for r in result_records), 2)
                workshop_dao_ref = workshop_dao
                # 获取 workshop_name 映射
                all_workshops = workshop_dao_ref.get_all()
                ws_name_map = {ws.workshop_id: ws.workshop_name for ws in all_workshops}

                results_list = []
                for r in result_records:
                    results_list.append({
                        "workshop_id": r.workshop_id,
                        "workshop_name": ws_name_map.get(r.workshop_id, r.workshop_id),
                        "max_rate": round2(
                            next(
                                (ws.max_discharge_rate for ws in all_workshops if ws.workshop_id == r.workshop_id),
                                0.0,
                            )
                        ),
                        "allowed_rate": round2(r.allowed_rate),
                        "allowed_volume": round2(r.allowed_volume),
                    })

                schedule_results = {
                    "total_rate": total_rate,
                    "schedule_id": latest_schedule_id,
                    "schedule_time": serialize(result_records[0].schedule_time),
                    "results": results_list,
                }

        # 3. 获取最近告警
        alert_records = alert_dao.get_recent_alerts(10)
        alerts_list = []
        for a in alert_records:
            alerts_list.append({
                "alert_time": serialize(a.alert_time),
                "alert_level": alert_level_to_text(a.alert_level),
                "tank_level": round2(a.tank_level),
                "level_ratio": ratio_to_percent(a.level_ratio),
                "alert_message": a.alert_message,
            })

        # 4. 启用车间数
        active_workshops = workshop_dao.get_active_workshops()

        # 5. 计算调度周期
        interval_min = params.schedule_interval_min
        now = datetime.now()
        minutes = now.minute
        # 对齐到调度周期
        cycle_minutes = (minutes // interval_min) * interval_min
        current_cycle = now.replace(minute=cycle_minutes, second=0, microsecond=0)
        next_cycle = current_cycle + timedelta(minutes=interval_min)

        data = {
            "tank_status": tank_status,
            "schedule_results": schedule_results,
            "alerts": alerts_list,
            "active_workshop_count": len(active_workshops),
            "current_cycle": serialize(current_cycle),
            "next_cycle": serialize(next_cycle),
        }

        return success(data=data)

    except DBQueryError as e:
        return server_error(f"数据库查询失败: {e}")
    except Exception as e:
        logger.error(f"获取概览数据失败: {e}", exc_info=True)
        return server_error(f"获取概览数据失败: {e}")


@router.get("/tank-status")
def get_tank_status(request: Request):
    """获取最新储罐状态（轮询端点，前端每 10 秒调用一次）。"""
    try:
        config_svc = request.app.state.config_svc
        trigger = request.app.state.trigger
        tank_dao = trigger._tank_dao

        tank_data = tank_dao.get_latest_manual_level()
        if not tank_data:
            return success(data=None)

        level, create_time = tank_data
        params = config_svc.get_all_params()
        level_ratio = level / params.tank_capacity

        # 判断区间
        from backend.scheduler.scheduler_service import SchedulerService
        svc = trigger._scheduler_svc
        zone, k = svc._determine_zone(level, params)

        data = {
            "level": round2(level),
            "ratio": ratio_to_percent(level_ratio),
            "status": zone,
            "k": round2(k),
            "predicted_level": None,
            "record_time": serialize(create_time),
        }

        return success(data=data)

    except Exception as e:
        logger.error(f"获取储罐状态失败: {e}", exc_info=True)
        return server_error(f"获取储罐状态失败: {e}")


@router.get("/latest-schedule")
def get_latest_schedule(request: Request):
    """获取最新一次调度结果。"""
    try:
        trigger = request.app.state.trigger
        result_dao = trigger._scheduler_svc._result_dao
        workshop_dao = trigger._scheduler_svc._workshop_dao

        latest_schedule_id = result_dao.get_latest_schedule_id()
        if not latest_schedule_id:
            return success(data=None)

        result_records = result_dao.get_by_schedule_id(latest_schedule_id)
        if not result_records:
            return success(data=None)

        total_rate = round(sum(r.allowed_rate for r in result_records), 2)
        all_workshops = workshop_dao.get_all()
        ws_name_map = {ws.workshop_id: ws.workshop_name for ws in all_workshops}

        results_list = []
        for r in result_records:
            results_list.append({
                "workshop_id": r.workshop_id,
                "workshop_name": ws_name_map.get(r.workshop_id, r.workshop_id),
                "max_rate": round2(
                    next(
                        (ws.max_discharge_rate for ws in all_workshops if ws.workshop_id == r.workshop_id),
                        0.0,
                    )
                ),
                "allowed_rate": round2(r.allowed_rate),
                "allowed_volume": round2(r.allowed_volume),
            })

        data = {
            "schedule_id": latest_schedule_id,
            "schedule_time": serialize(result_records[0].schedule_time),
            "total_rate": total_rate,
            "results": results_list,
        }

        return success(data=data)

    except Exception as e:
        logger.error(f"获取最新调度结果失败: {e}", exc_info=True)
        return server_error(f"获取最新调度结果失败: {e}")


@router.get("/recent-alerts")
def get_recent_alerts(request: Request, limit: int = Query(default=10, ge=1, le=50)):
    """获取最近 N 条告警。"""
    try:
        trigger = request.app.state.trigger
        alert_dao = trigger._scheduler_svc._alert_dao

        alert_records = alert_dao.get_recent_alerts(limit)
        alerts_list = []
        for a in alert_records:
            alerts_list.append({
                "alert_time": serialize(a.alert_time),
                "alert_level": alert_level_to_text(a.alert_level),
                "tank_level": round2(a.tank_level),
                "level_ratio": ratio_to_percent(a.level_ratio),
                "alert_message": a.alert_message,
            })

        return success(data=alerts_list)

    except Exception as e:
        logger.error(f"获取最近告警失败: {e}", exc_info=True)
        return server_error(f"获取最近告警失败: {e}")

# -*- coding: utf-8 -*-
"""
告警服务模块

生成停排建议记录，构建告警记录对象（只构建，不写库）。
"""

from __future__ import annotations

from datetime import datetime
from typing import List

from backend.model import AlertRecord
from backend.model import ScheduleResultRecord
from backend.model import Workshop
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# 告警级别映射
ALERT_LEVEL_MAP = {"ALERT": 2, "EMERGENCY": 3}


class AlertService:
    """告警服务"""

    def generate_stop_advisory(
        self,
        workshops: List[Workshop],
        tank_level: float,
        zone: str,
        schedule_id: str,
        schedule_time: datetime,
        T: float,
    ) -> List[ScheduleResultRecord]:
        """
        为所有车间生成 allowed_rate=0, allowed_volume=0, solver_status=SKIPPED 的建议。

        Args:
            workshops: 车间列表
            tank_level: 当前储罐液位
            zone: 区间名称（"ALERT" or "EMERGENCY"）
            schedule_id: 调度批次号
            schedule_time: 调度时间
            T: 调度周期（小时）

        Returns:
            停排建议记录列表
        """
        records = [
            ScheduleResultRecord(
                schedule_id=schedule_id,
                schedule_time=schedule_time,
                workshop_id=ws.workshop_id,
                allowed_rate=0.0,
                allowed_volume=0.0,
                tank_level_before=tank_level,
                schedule_status=zone,
                solver_status="SKIPPED",
            )
            for ws in workshops
        ]
        logger.info(f"生成停排建议: zone={zone}, workshops={len(workshops)}")
        return records

    def build_alert_record(
        self,
        schedule_id: str,
        tank_level: float,
        level_ratio: float,
        zone: str,
        reason: str,
    ) -> AlertRecord:
        """
        构建告警记录。

        Args:
            schedule_id: 调度批次号
            tank_level: 当前储罐液位
            level_ratio: 液位占比
            zone: 区间名称（"ALERT" or "EMERGENCY"）
            reason: 告警原因

        Returns:
            告警记录对象
        """
        alert_level = ALERT_LEVEL_MAP.get(zone, 2)
        alert_time = datetime.now()

        alert = AlertRecord(
            schedule_id=schedule_id,
            alert_time=alert_time,
            alert_level=alert_level,
            tank_level=tank_level,
            level_ratio=level_ratio,
            alert_message=f"[{zone}] {reason}（当前液位{tank_level:.2f}m³，占比{level_ratio*100:.1f}%）",
            is_handled=0,
        )
        logger.info(f"构建告警记录: level={alert_level}, zone={zone}, reason={reason}")
        return alert

# -*- coding: utf-8 -*-
"""数据模型模块"""

from backend.model.alert import AlertRecord
from backend.model.schedule_input import ScheduleInputRecord, ScheduleInputWorkshopRecord
from backend.model.schedule_result import ScheduleResultRecord
from backend.model.solver_params import SolverParams, SolverResult
from backend.model.tank_status import TankStatusRecord
from backend.model.workshop import Workshop


class ScheduleSummary:
    """调度摘要（手动触发接口返回值）"""

    def __init__(
        self,
        schedule_id: str,
        zone: str,
        workshop_count: int,
        solver_status: str,
        total_rate: float,
        elapsed_ms: int,
    ):
        self.schedule_id = schedule_id
        self.zone = zone
        self.workshop_count = workshop_count
        self.solver_status = solver_status
        self.total_rate = total_rate
        self.elapsed_ms = elapsed_ms

    def to_dict(self):
        return {
            "schedule_id": self.schedule_id,
            "zone": self.zone,
            "workshop_count": self.workshop_count,
            "solver_status": self.solver_status,
            "total_rate": self.total_rate,
            "elapsed_ms": self.elapsed_ms,
        }


__all__ = [
    "AlertRecord",
    "ScheduleInputRecord",
    "ScheduleInputWorkshopRecord",
    "ScheduleResultRecord",
    "ScheduleSummary",
    "SolverParams",
    "SolverResult",
    "TankStatusRecord",
    "Workshop",
]

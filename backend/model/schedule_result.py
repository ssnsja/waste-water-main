# -*- coding: utf-8 -*-
"""
调度结果记录数据类
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class ScheduleResultRecord:
    """调度结果记录数据类"""

    schedule_id: str
    schedule_time: datetime
    workshop_id: str
    allowed_rate: float        # r_i (m³/h)
    allowed_volume: float      # r_i * T (m³)
    tank_level_before: float
    schedule_status: str       # NORMAL / WARNING / ALERT / EMERGENCY
    solver_status: str         # Optimal / Infeasible / SKIPPED / Timeout

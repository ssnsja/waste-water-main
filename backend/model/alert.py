# -*- coding: utf-8 -*-
"""
告警记录数据类
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class AlertRecord:
    """告警记录数据类"""

    schedule_id: str                 # 调度批次号，关联 WW_SCHEDULE_RESULT
    alert_time: datetime
    alert_level: int           # 2=ALERT, 3=EMERGENCY
    tank_level: float
    level_ratio: float
    alert_message: str
    is_handled: int = field(default=0)
    create_time: datetime = field(default_factory=datetime.now)

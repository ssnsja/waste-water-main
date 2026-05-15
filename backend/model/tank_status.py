# -*- coding: utf-8 -*-
"""
储罐状态记录数据类
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class TankStatusRecord:
    """储罐状态记录数据类"""

    record_time: datetime
    current_level: float
    level_ratio: float
    tank_status: str
    predicted_level: Optional[float]
    input_type: str = field(default="MANUAL")   # "MANUAL" | "AUTO" (预留)
    create_time: datetime = field(default_factory=datetime.now)

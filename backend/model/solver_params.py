# -*- coding: utf-8 -*-
"""
求解器参数与结果数据类
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class SolverParams:
    """求解器参数数据类"""

    tank_capacity: float          # V (m³)
    process_capacity: float       # C (m³/h)
    schedule_interval_h: float    # T（小时，如 0.5）
    schedule_interval_min: int    # 调度周期（分钟）
    manual_level_stale_threshold: int  # 液位超期阈值（调度周期倍数）
    safe_ratio: float             # 默认 0.85
    warning_ratio: float          # 默认 0.80
    alert_ratio: float            # 默认 0.90
    emergency_ratio: float        # 默认 0.95
    min_rate_ratio: float         # 默认 0.30
    process_buffer_ratio: float   # 默认 1.20


@dataclass
class SolverResult:
    """求解器结果数据类"""

    status: str                           # "Optimal" / "Infeasible" / "Timeout"
    rates: Dict[str, float]               # workshop_id → r_i (m³/h)
    objective_value: Optional[float]      # 加权总排放速率，Infeasible/Timeout 时为 None

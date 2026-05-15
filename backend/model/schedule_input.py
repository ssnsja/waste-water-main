# -*- coding: utf-8 -*-
"""
调度输入快照数据类

存储每次调度运行时的配置快照，便于复盘、调试和AI训练。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class ScheduleInputRecord:
    """调度输入系统级快照记录"""

    schedule_id: str
    schedule_time: datetime
    tank_capacity: float              # V (m³)
    process_capacity: float           # C (m³/h)
    schedule_interval_min: int        # 调度周期（分钟）
    safe_ratio: float                 # 安全容量系数
    warning_ratio: float              # 预警阈值
    alert_ratio: float                # 告警阈值
    emergency_ratio: float            # 紧急阈值
    min_rate_ratio: float             # 弹性压缩最低保留比例
    process_buffer_ratio: float       # 处理能力缓冲系数
    tank_level: float                 # 调度时储罐液位（m³）
    level_ratio: float                # 调度时液位占比
    zone: str                         # 液位区间（NORMAL/WARNING/ALERT/EMERGENCY）
    elastic_k: Optional[float]        # 弹性系数 k（预警区间有效）
    capacity_limit: Optional[float]   # 容量约束上限计算值（m³/h）
    process_limit: Optional[float]    # 处理能力约束上限计算值（m³/h）
    effective_limit: Optional[float]  # 实际生效约束上限
    workshop_count: int               # 本次调度启用车间数量


@dataclass
class ScheduleInputWorkshopRecord:
    """调度输入车间级快照记录"""

    schedule_id: str
    workshop_id: str
    workshop_name: str
    max_discharge_rate: float         # 最大排放速率（m³/h）
    min_discharge_rate: float         # 最小排放速率（m³/h）
    priority_weight: float            # 优先级权重
    elastic_max_rate: Optional[float] # 弹性压缩后的速率上限（m³/h）
    create_time: datetime             # 创建时间

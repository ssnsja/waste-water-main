# -*- coding: utf-8 -*-
"""
车间数据类
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Workshop:
    """车间信息数据类"""

    workshop_id: str
    workshop_name: str
    max_discharge_rate: float   # 最大排放速率 m³/h
    min_discharge_rate: float   # 最小排放速率 m³/h
    priority_weight: float      # 优先权重
    # 新增字段（带默认值，向后兼容）
    is_active: int = 1          # 是否启用 1/0
    remark: str = ""            # 备注
    update_time: Optional[datetime] = None  # 最后更新时间

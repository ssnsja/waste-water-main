# -*- coding: utf-8 -*-
"""
求解器服务模块

构建 PuLP LP 模型并求解，返回各车间建议排放速率。
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from pulp import (
    LpMaximize,
    LpProblem,
    LpStatus,
    LpVariable,
    lpSum,
    value,
)
from pulp.apis import PULP_CBC_CMD

from backend.model import SolverResult
from backend.model import Workshop
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class SolverService:
    """LP 求解服务"""

    def solve(
        self,
        workshops: List[Workshop],
        effective_limit: float,
        k: float,
        T: float,
    ) -> SolverResult:
        """
        构建并求解 LP，返回 SolverResult。

        Args:
            workshops: 车间列表
            effective_limit: 有效速率上限（取容量约束与处理能力约束较小值）
            k: 弹性系数（正常区间=1.0，预警区间∈[MIN_RATE_RATIO, 1.0]）
            T: 调度周期（小时）

        Returns:
            求解器结果对象
        """
        prob, r_vars = self._build_model(workshops, effective_limit, k, T)
        result = self._parse_result(prob, r_vars, workshops)

        logger.info(
            f"LP求解完成: status={result.status}, "
            f"objective={result.objective_value}, "
            f"workshops={len(workshops)}"
        )
        return result

    def _build_model(
        self,
        workshops: List[Workshop],
        effective_limit: float,
        k: float,
        T: float,
    ) -> Tuple[LpProblem, Dict[str, LpVariable]]:
        """
        构建 PuLP 模型。

        Args:
            workshops: 车间列表
            effective_limit: 有效速率上限
            k: 弹性系数
            T: 调度周期（小时）

        Returns:
            (PuLP 问题对象, 决策变量字典)
        """
        prob = LpProblem("WasteWaterScheduler", LpMaximize)

        # 决策变量：r_i ∈ [r_min, r_max * k]
        r_vars: Dict[str, LpVariable] = {}
        for ws in workshops:
            r_vars[ws.workshop_id] = LpVariable(
                f"r_{ws.workshop_id}",
                lowBound=ws.min_discharge_rate,
                upBound=ws.max_discharge_rate * k,
            )

        # 目标函数：最大化加权总排放速率
        prob += lpSum(
            ws.priority_weight * r_vars[ws.workshop_id] for ws in workshops
        )

        # 约束：总排放速率 ≤ effective_limit
        prob += lpSum(r_vars[ws.workshop_id] for ws in workshops) <= effective_limit

        logger.debug(
            f"LP模型构建完成: 变量数={len(r_vars)}, effective_limit={effective_limit:.4f}"
        )
        return prob, r_vars

    def _parse_result(
        self,
        prob: LpProblem,
        r_vars: Dict[str, LpVariable],
        workshops: List[Workshop],
    ) -> SolverResult:
        """
        解析求解结果，处理 Optimal/Infeasible/Timeout 三种状态。

        Args:
            prob: PuLP 问题对象
            r_vars: 决策变量字典
            workshops: 车间列表

        Returns:
            求解器结果对象
        """
        # 求解（10秒超时，静默模式）
        status_code = prob.solve(PULP_CBC_CMD(timeLimit=10, msg=0))
        status_str = LpStatus[status_code]

        if status_str == "Optimal":
            # 提取各车间速率，四舍五入保留4位小数
            rates = {
                ws_id: round(float(value(var)), 4)
                for ws_id, var in r_vars.items()
            }
            objective_value = round(float(value(prob.objective)), 4)
            logger.debug(f"LP求解成功: total_rate={objective_value:.4f}")
            return SolverResult(
                status="Optimal",
                rates=rates,
                objective_value=objective_value,
            )
        else:
            # Infeasible 或 Timeout，返回全零速率
            rates = {ws.workshop_id: 0.0 for ws in workshops}
            logger.warning(f"LP求解异常: status={status_str}")
            return SolverResult(
                status=status_str,  # "Infeasible" or "Timeout"
                rates=rates,
                objective_value=None,
            )

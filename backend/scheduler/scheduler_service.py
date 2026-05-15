# -*- coding: utf-8 -*-
"""
调度主流程服务模块

调度全流程编排，串联所有子模块，不包含业务计算逻辑。
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime
from typing import List, Optional, Tuple

import oracledb

from backend.dao.alert_log_dao import AlertLogDAO
from backend.dao.schedule_input_dao import ScheduleInputDAO
from backend.dao.schedule_input_workshop_dao import ScheduleInputWorkshopDAO
from backend.dao.schedule_result_dao import ScheduleResultDAO
from backend.dao.tank_status_dao import TankStatusDAO
from backend.dao.workshop_dao import WorkshopDAO
from backend.model import AlertRecord
from backend.model import ScheduleInputRecord
from backend.model import ScheduleInputWorkshopRecord
from backend.model import ScheduleResultRecord
from backend.model import ScheduleSummary
from backend.model import SolverParams
from backend.model import TankStatusRecord
from backend.model import Workshop
from backend.scheduler.alert_service import AlertService
from backend.scheduler.config_service import ConfigService
from backend.scheduler.solver_service import SolverService
from backend.utils.exceptions import (
    DBWriteError,
    InvalidTankLevelError,
    NoActiveWorkshopError,
)
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class SchedulerService:
    """调度主流程服务"""

    def __init__(
        self,
        config_svc: ConfigService,
        solver_svc: SolverService,
        alert_svc: AlertService,
        workshop_dao: WorkshopDAO,
        tank_dao: TankStatusDAO,
        result_dao: ScheduleResultDAO,
        alert_dao: AlertLogDAO,
        input_dao: ScheduleInputDAO,
        input_workshop_dao: ScheduleInputWorkshopDAO,
        pool: oracledb.ConnectionPool,
    ) -> None:
        """
        初始化调度服务。

        Args:
            config_svc: 配置服务
            solver_svc: 求解器服务
            alert_svc: 告警服务
            workshop_dao: 车间 DAO
            tank_dao: 储罐状态 DAO
            result_dao: 调度结果 DAO
            alert_dao: 告警日志 DAO
            input_dao: 调度输入快照 DAO
            input_workshop_dao: 调度输入车间快照 DAO
            pool: 数据库连接池
        """
        self._config_svc = config_svc
        self._solver_svc = solver_svc
        self._alert_svc = alert_svc
        self._workshop_dao = workshop_dao
        self._tank_dao = tank_dao
        self._result_dao = result_dao
        self._alert_dao = alert_dao
        self._input_dao = input_dao
        self._input_workshop_dao = input_workshop_dao
        self._pool = pool

    def run(self, tank_level: float) -> ScheduleSummary | None:
        """
        主调度入口，执行完整 Step1~Step9 流程。

        Args:
            tank_level: 当前储罐液位（m³）

        Returns:
            ScheduleSummary 调度摘要，异常时返回 None
        """
        start_time = time.time()
        schedule_id = str(uuid.uuid4())
        schedule_time = datetime.now()

        logger.info(f"[{schedule_id}] 调度开始，液位={tank_level} m³")

        try:
            # Step 1: 读取配置
            params = self._config_svc.get_all_params()
            logger.debug(f"[{schedule_id}] 配置加载完成: V={params.tank_capacity}")

            # Step 2: 液位校验
            L = self._validate_tank_level(tank_level, params, schedule_id)

            # Step 3: 读取启用车间
            workshops = self._workshop_dao.get_active_workshops()
            if not workshops:
                logger.warning(f"[{schedule_id}] 无启用车间，跳过本次调度")
                raise NoActiveWorkshopError("无启用车间")

            # Step 4: 区间判断
            zone, k = self._determine_zone(L, params)
            level_ratio = L / params.tank_capacity
            logger.info(f"[{schedule_id}] 区间判断: zone={zone}, k={k:.4f}")

            # Step 5~6: 根据区间执行不同分支
            results: List[ScheduleResultRecord] = []
            alert_record: Optional[AlertRecord] = None

            # 初始化约束计算值（用于快照记录）
            capacity_limit: Optional[float] = None
            process_limit: Optional[float] = None
            effective_limit: Optional[float] = None

            if zone in ("ALERT", "EMERGENCY"):
                # ALERT/EMERGENCY: 生成停排建议
                results = self._alert_svc.generate_stop_advisory(
                    workshops=workshops,
                    tank_level=L,
                    zone=zone,
                    schedule_id=schedule_id,
                    schedule_time=schedule_time,
                    T=params.schedule_interval_h,
                )
                alert_record = self._alert_svc.build_alert_record(
                    schedule_id=schedule_id,
                    tank_level=L,
                    level_ratio=level_ratio,
                    zone=zone,
                    reason=f"液位进入{zone}区间，建议停止排放",
                )
            else:
                # NORMAL/WARNING: LP 求解
                # 预计算 effective_limit
                V = params.tank_capacity
                C = params.process_capacity
                T = params.schedule_interval_h
                safe_ratio = params.safe_ratio
                process_buffer_ratio = params.process_buffer_ratio

                # 输出约束计算过程
                logger.debug(
                    f"[{schedule_id}] 约束计算: L={L}, V={V}, T={T}, C={C}"
                )

                capacity_limit = (V * safe_ratio - L) / T + C
                logger.debug(
                    f"[{schedule_id}] 容量约束: (V*SAFE_RATIO-L)/T+C = "
                    f"({V}*{safe_ratio}-{L})/{T}+{C} = {capacity_limit:.4f}"
                )

                process_limit = C * process_buffer_ratio
                logger.debug(
                    f"[{schedule_id}] 处理能力约束: C*PROCESS_BUFFER_RATIO = "
                    f"{C}*{process_buffer_ratio} = {process_limit:.4f}"
                )

                effective_limit = min(capacity_limit, process_limit)
                logger.debug(
                    f"[{schedule_id}] 生效约束: effective_limit = "
                    f"min({capacity_limit:.4f}, {process_limit:.4f}) = {effective_limit:.4f}"
                )

                if zone == "WARNING":
                    # 输出弹性系数计算过程
                    warning_threshold = params.warning_ratio * V
                    numerator = L - warning_threshold
                    denominator = 0.1 * V
                    k_calc = 1 - numerator / denominator * (1 - params.min_rate_ratio)
                    logger.debug(
                        f"[{schedule_id}] 弹性系数: k = 1 - (L-WARNING_RATIO*V)/(0.1*V)*(1-MIN_RATE_RATIO) = "
                        f"1 - ({L}-{warning_threshold:.4f})/{denominator:.4f}*{1-params.min_rate_ratio:.4f} = {k:.4f}"
                    )

                if effective_limit <= 0:
                    # effective_limit <= 0: 生成全零建议
                    logger.warning(
                        f"[{schedule_id}] effective_limit={effective_limit:.4f} <= 0，生成全零建议"
                    )
                    results = self._generate_zero_advisory(
                        workshops=workshops,
                        tank_level=L,
                        zone=zone,
                        schedule_id=schedule_id,
                        schedule_time=schedule_time,
                        T=params.schedule_interval_h,
                    )
                    alert_record = self._alert_svc.build_alert_record(
                        schedule_id=schedule_id,
                        tank_level=L,
                        level_ratio=level_ratio,
                        zone="WARNING",
                        reason="effective_limit <= 0，无法分配排放配额",
                    )
                else:
                    # 调用求解器
                    solver_result = self._solver_svc.solve(
                        workshops=workshops,
                        effective_limit=effective_limit,
                        k=k,
                        T=params.schedule_interval_h,
                    )

                    if solver_result.status == "Optimal":
                        # 正常结果
                        results = self._build_result_records(
                            workshops=workshops,
                            rates=solver_result.rates,
                            tank_level=L,
                            zone=zone,
                            schedule_id=schedule_id,
                            schedule_time=schedule_time,
                            T=params.schedule_interval_h,
                            solver_status="Optimal",
                        )
                    else:
                        # Infeasible 或 Timeout
                        results = self._generate_zero_advisory(
                            workshops=workshops,
                            tank_level=L,
                            zone=zone,
                            schedule_id=schedule_id,
                            schedule_time=schedule_time,
                            T=params.schedule_interval_h,
                            solver_status=solver_result.status,
                        )
                        alert_record = self._alert_svc.build_alert_record(
                            schedule_id=schedule_id,
                            tank_level=L,
                            level_ratio=level_ratio,
                            zone="ALERT",
                            reason=f"LP求解{solver_result.status}，已生成保守建议",
                        )

            # Step 7: 计算派生字段
            L_predicted = self._compute_derived(results, L, params)

            # Step 8: 构建快照记录
            tank_record = TankStatusRecord(
                record_time=schedule_time,
                current_level=L,
                level_ratio=level_ratio,
                tank_status=zone,
                predicted_level=L_predicted,
                input_type="MANUAL",
                create_time=schedule_time
            )

            # 构建调度输入系统级快照
            elastic_k = k if zone == "WARNING" else None
            schedule_input_record = ScheduleInputRecord(
                schedule_id=schedule_id,
                schedule_time=schedule_time,
                tank_capacity=params.tank_capacity,
                process_capacity=params.process_capacity,
                schedule_interval_min=int(params.schedule_interval_h * 60),
                safe_ratio=params.safe_ratio,
                warning_ratio=params.warning_ratio,
                alert_ratio=params.alert_ratio,
                emergency_ratio=params.emergency_ratio,
                min_rate_ratio=params.min_rate_ratio,
                process_buffer_ratio=params.process_buffer_ratio,
                tank_level=L,
                level_ratio=level_ratio,
                zone=zone,
                elastic_k=elastic_k,
                capacity_limit=capacity_limit,
                process_limit=process_limit,
                effective_limit=effective_limit,
                workshop_count=len(workshops),
            )

            # 构建调度输入车间级快照
            input_workshop_records = [
                ScheduleInputWorkshopRecord(
                    schedule_id=schedule_id,
                    workshop_id=ws.workshop_id,
                    workshop_name=ws.workshop_name,
                    max_discharge_rate=ws.max_discharge_rate,
                    min_discharge_rate=ws.min_discharge_rate,
                    priority_weight=ws.priority_weight,
                    elastic_max_rate=ws.max_discharge_rate * k if zone == "WARNING" else None,
                    create_time=schedule_time,
                )
                for ws in workshops
            ]

            # Step 9: 事务写库
            self._write_all(tank_record, results, schedule_input_record, input_workshop_records, alert_record)

            # Step 10: 完成
            elapsed_ms = int((time.time() - start_time) * 1000)
            total_rate = round(sum(r.allowed_rate for r in results), 2)
            solver_status = results[0].solver_status if results else "SKIPPED"

            logger.info(
                f"[{schedule_id}] 调度完成 zone={zone} workshops={len(workshops)} elapsed={elapsed_ms}ms"
            )

            return ScheduleSummary(
                schedule_id=schedule_id,
                zone=zone,
                workshop_count=len(workshops),
                solver_status=solver_status,
                total_rate=total_rate,
                elapsed_ms=elapsed_ms,
            )

        except (InvalidTankLevelError, NoActiveWorkshopError) as e:
            # 已在内部记录日志，此处不再抛出，避免中断定时调度
            logger.error(f"[{schedule_id}] 调度跳过: {e}")
            raise
        except Exception as e:
            logger.error(f"[{schedule_id}] 调度异常: {e}", exc_info=True)
            raise

    def _validate_tank_level(
        self, L: float, params: SolverParams, schedule_id: str
    ) -> float:
        """
        校验液位合法性。

        Args:
            L: 原始液位值
            params: 求解器参数
            schedule_id: 调度批次号

        Returns:
            校验后的液位值

        Raises:
            InvalidTankLevelError: 液位非法
        """
        if L is None or L <= 0:
            logger.error(f"[{schedule_id}] 液位非法: L={L}")
            raise InvalidTankLevelError(f"液位非法: {L}")

        if L > params.tank_capacity:
            logger.error(
                f"[{schedule_id}] 液位超上限: L={L} > V={params.tank_capacity}，按 EMERGENCY 处理"
            )
            # 不抛出异常，返回 V 作为液位继续处理
            return params.tank_capacity

        return L

    def _determine_zone(self, L: float, params: SolverParams) -> Tuple[str, float]:
        """
        判断液位区间，返回 (zone, k)。

        Args:
            L: 当前液位
            params: 求解器参数

        Returns:
            (区间名称, 弹性系数)
        """
        V = params.tank_capacity
        level_ratio = L / V

        if level_ratio < params.warning_ratio:
            # 正常区间
            return "NORMAL", 1.0
        elif level_ratio < params.alert_ratio:
            # 预警区间：计算弹性系数
            k = self._compute_k(L, params)
            return "WARNING", k
        elif level_ratio < params.emergency_ratio:
            # 告警区间
            return "ALERT", 0.0
        else:
            # 紧急区间
            return "EMERGENCY", 0.0

    def _compute_k(self, L: float, params: SolverParams) -> float:
        """
        计算预警区间的弹性系数。

        公式: k = 1 - (L - WARNING_RATIO*V) / (0.1*V) * (1 - MIN_RATE_RATIO)
        范围: [MIN_RATE_RATIO, 1.0]

        Args:
            L: 当前液位
            params: 求解器参数

        Returns:
            弹性系数 k
        """
        V = params.tank_capacity
        warning_threshold = params.warning_ratio * V

        # 计算 k
        k = 1 - (L - warning_threshold) / (0.1 * V) * (1 - params.min_rate_ratio)

        # 确保 k 在 [MIN_RATE_RATIO, 1.0] 范围内
        k = max(k, params.min_rate_ratio)
        k = min(k, 1.0)

        return k

    def _compute_derived(
        self,
        results: List[ScheduleResultRecord],
        L: float,
        params: SolverParams,
    ) -> float:
        """
        计算预测液位。

        公式: L_predicted = max(0.0, L + Σ(r_i*T) - C*T)

        Args:
            results: 调度结果列表
            L: 当前液位
            params: 求解器参数

        Returns:
            预测液位
        """
        total_rate = sum(r.allowed_rate for r in results)
        total_inflow = total_rate * params.schedule_interval_h
        total_outflow = params.process_capacity * params.schedule_interval_h
        L_predicted = L + total_inflow - total_outflow
        L_predicted = max(0.0, L_predicted)
        return L_predicted

    def _build_result_records(
        self,
        workshops: List[Workshop],
        rates: dict,
        tank_level: float,
        zone: str,
        schedule_id: str,
        schedule_time: datetime,
        T: float,
        solver_status: str,
    ) -> List[ScheduleResultRecord]:
        """
        构建调度结果记录列表。

        Args:
            workshops: 车间列表
            rates: 各车间建议速率字典
            tank_level: 当前液位
            zone: 区间名称
            schedule_id: 调度批次号
            schedule_time: 调度时间
            T: 调度周期（小时）
            solver_status: 求解器状态

        Returns:
            调度结果记录列表
        """
        records = []
        for ws in workshops:
            rate = rates.get(ws.workshop_id, 0.0)
            records.append(
                ScheduleResultRecord(
                    schedule_id=schedule_id,
                    schedule_time=schedule_time,
                    workshop_id=ws.workshop_id,
                    allowed_rate=rate,
                    allowed_volume=rate * T,
                    tank_level_before=tank_level,
                    schedule_status=zone,
                    solver_status=solver_status,
                )
            )
        return records

    def _generate_zero_advisory(
        self,
        workshops: List[Workshop],
        tank_level: float,
        zone: str,
        schedule_id: str,
        schedule_time: datetime,
        T: float,
        solver_status: str = "SKIPPED",
    ) -> List[ScheduleResultRecord]:
        """
        生成全零建议。

        Args:
            workshops: 车间列表
            tank_level: 当前液位
            zone: 区间名称
            schedule_id: 调度批次号
            schedule_time: 调度时间
            T: 调度周期（小时）
            solver_status: 求解器状态

        Returns:
            全零调度结果记录列表
        """
        return [
            ScheduleResultRecord(
                schedule_id=schedule_id,
                schedule_time=schedule_time,
                workshop_id=ws.workshop_id,
                allowed_rate=0.0,
                allowed_volume=0.0,
                tank_level_before=tank_level,
                schedule_status=zone,
                solver_status=solver_status,
            )
            for ws in workshops
        ]

    def _write_all(
        self,
        tank_record: TankStatusRecord,
        results: List[ScheduleResultRecord],
        schedule_input: ScheduleInputRecord,
        input_workshops: List[ScheduleInputWorkshopRecord],
        alert: Optional[AlertRecord],
    ) -> None:
        """
        事务写库：WW_TANK_STATUS → WW_SCHEDULE_RESULT → WW_SCHEDULE_INPUT → WW_SCHEDULE_INPUT_WORKSHOP → WW_ALERT_LOG。

        Args:
            tank_record: 储罐状态记录
            results: 调度结果列表
            schedule_input: 调度输入系统级快照
            input_workshops: 调度输入车间级快照列表
            alert: 告警记录（可选）

        Raises:
            DBWriteError: 数据库写入失败
        """
        conn = None
        try:
            conn = self._pool.acquire()
            conn.autocommit = False

            # 1. 写入储罐状态
            self._tank_dao.insert(conn, tank_record)

            # 2. 批量写入调度结果
            self._result_dao.batch_insert(conn, results)

            # 3. 写入调度输入系统级快照
            self._input_dao.insert(conn, schedule_input)

            # 4. 批量写入调度输入车间级快照
            self._input_workshop_dao.batch_insert(conn, input_workshops)

            # 5. 写入告警记录（如有）
            if alert:
                self._alert_dao.insert(conn, alert)

            # 提交事务
            conn.commit()
            logger.debug("事务写入完成，已提交")

        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"事务写入失败，已回滚: {e}", exc_info=True)
            raise DBWriteError(f"数据库写入失败: {e}") from e
        finally:
            if conn:
                self._pool.release(conn)

# -*- coding: utf-8 -*-
"""
调度结果 DAO 模块
"""

from __future__ import annotations

from typing import List, Optional

import oracledb

from backend.dao.base_dao import BaseDAO
from backend.model import ScheduleResultRecord
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class ScheduleResultDAO(BaseDAO):
    """调度结果数据访问对象"""

    def batch_insert(
        self, conn: oracledb.Connection, records: List[ScheduleResultRecord]
    ) -> None:
        """
        批量写入调度结果，使用 executemany，主键使用 SEQ_SCHEDULE_RESULT.NEXTVAL。

        Args:
            conn: 数据库连接（外部管理事务）
            records: 调度结果记录列表
        """
        sql = """
            INSERT INTO WW_SCHEDULE_RESULT
                (RESULT_ID, SCHEDULE_ID, SCHEDULE_TIME, WORKSHOP_ID,
                 ALLOWED_RATE, ALLOWED_VOLUME, TANK_LEVEL_BEFORE,
                 SCHEDULE_STATUS, SOLVER_STATUS, CREATE_TIME)
            VALUES
                (SEQ_SCHEDULE_RESULT.NEXTVAL, :schedule_id, :schedule_time, :workshop_id,
                 :allowed_rate, :allowed_volume, :tank_level_before,
                 :schedule_status, :solver_status, :create_time)
        """
        params_list = [
            {
                "schedule_id": r.schedule_id,
                "schedule_time": r.schedule_time,
                "workshop_id": r.workshop_id,
                "allowed_rate": r.allowed_rate,
                "allowed_volume": r.allowed_volume,
                "tank_level_before": r.tank_level_before,
                "schedule_status": r.schedule_status,
                "solver_status": r.solver_status,
                "create_time": r.schedule_time,  # CREATE_TIME 使用调度时间
            }
            for r in records
        ]
        self.execute_batch(conn, sql, params_list)
        logger.debug(f"批量写入 {len(records)} 条调度结果")

    def get_latest_schedule_id(self) -> Optional[str]:
        """
        获取最新一次调度的批次号（按 SCHEDULE_TIME DESC 取第一条）。

        Returns:
            最新批次号，无记录返回 None
        """
        sql = """
            SELECT SCHEDULE_ID FROM (
                SELECT SCHEDULE_ID
                FROM   WW_SCHEDULE_RESULT
                ORDER  BY SCHEDULE_TIME DESC
            ) WHERE ROWNUM = 1
        """
        rows = self.execute_query(sql)
        if rows:
            return rows[0]["schedule_id"]
        return None

    def get_by_schedule_id(self, schedule_id: str) -> List[ScheduleResultRecord]:
        """
        按调度批次号查询所有车间调度结果。

        Args:
            schedule_id: 调度批次号

        Returns:
            调度结果记录列表
        """
        sql = """
            SELECT SCHEDULE_ID, SCHEDULE_TIME, WORKSHOP_ID,
                   ALLOWED_RATE, ALLOWED_VOLUME, TANK_LEVEL_BEFORE,
                   SCHEDULE_STATUS, SOLVER_STATUS
            FROM   WW_SCHEDULE_RESULT
            WHERE  SCHEDULE_ID = :schedule_id
            ORDER  BY WORKSHOP_ID
        """
        rows = self.execute_query(sql, {"schedule_id": schedule_id})
        records = [self._row_to_record(row) for row in rows]
        logger.debug(f"查询批次 {schedule_id} 的调度结果: {len(records)} 条")
        return records

    def _row_to_record(self, row: dict) -> ScheduleResultRecord:
        """
        将数据库行转换为 ScheduleResultRecord 对象。

        Args:
            row: 数据库行（字典）

        Returns:
            ScheduleResultRecord 对象
        """
        return ScheduleResultRecord(
            schedule_id=row["schedule_id"],
            schedule_time=row["schedule_time"],
            workshop_id=row["workshop_id"],
            allowed_rate=float(row["allowed_rate"]),
            allowed_volume=float(row["allowed_volume"]),
            tank_level_before=float(row["tank_level_before"]),
            schedule_status=row["schedule_status"],
            solver_status=row["solver_status"],
        )

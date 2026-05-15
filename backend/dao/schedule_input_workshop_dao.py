# -*- coding: utf-8 -*-
"""
调度输入车间快照 DAO 模块
"""

from __future__ import annotations

from typing import List

import oracledb

from backend.dao.base_dao import BaseDAO
from backend.model import ScheduleInputWorkshopRecord
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class ScheduleInputWorkshopDAO(BaseDAO):
    """调度输入车间级快照数据访问对象"""

    def batch_insert(
        self, conn: oracledb.Connection, records: List[ScheduleInputWorkshopRecord]
    ) -> None:
        """
        批量写入调度输入车间级快照，主键使用 SEQ_SCHEDULE_INPUT_WORKSHOP.NEXTVAL。

        Args:
            conn: 数据库连接（外部管理事务）
            records: 调度输入车间快照记录列表
        """
        sql = """
            INSERT INTO WW_SCHEDULE_INPUT_WORKSHOP
                (INPUT_WORKSHOP_ID, SCHEDULE_ID, WORKSHOP_ID, WORKSHOP_NAME,
                 MAX_DISCHARGE_RATE, MIN_DISCHARGE_RATE, PRIORITY_WEIGHT, ELASTIC_MAX_RATE, CREATE_TIME)
            VALUES
                (SEQ_SCHEDULE_INPUT_WORKSHOP.NEXTVAL, :schedule_id, :workshop_id, :workshop_name,
                 :max_discharge_rate, :min_discharge_rate, :priority_weight, :elastic_max_rate, :create_time)
        """
        params_list = [
            {
                "schedule_id": r.schedule_id,
                "workshop_id": r.workshop_id,
                "workshop_name": r.workshop_name,
                "max_discharge_rate": r.max_discharge_rate,
                "min_discharge_rate": r.min_discharge_rate,
                "priority_weight": r.priority_weight,
                "elastic_max_rate": r.elastic_max_rate,
                "create_time": r.create_time,
            }
            for r in records
        ]
        self.execute_batch(conn, sql, params_list)
        logger.debug(f"批量写入 {len(records)} 条车间快照")

    def get_by_schedule_id(self, schedule_id: str) -> List[ScheduleInputWorkshopRecord]:
        """
        按调度批次号查询车间级快照。

        Args:
            schedule_id: 调度批次号

        Returns:
            车间级快照记录列表
        """
        sql = """
            SELECT SCHEDULE_ID, WORKSHOP_ID, WORKSHOP_NAME,
                   MAX_DISCHARGE_RATE, MIN_DISCHARGE_RATE,
                   PRIORITY_WEIGHT, ELASTIC_MAX_RATE, CREATE_TIME
            FROM   WW_SCHEDULE_INPUT_WORKSHOP
            WHERE  SCHEDULE_ID = :schedule_id
            ORDER  BY WORKSHOP_ID
        """
        rows = self.execute_query(sql, {"schedule_id": schedule_id})
        records = [self._row_to_record(row) for row in rows]
        logger.debug(f"查询批次 {schedule_id} 的车间快照: {len(records)} 条")
        return records

    def _row_to_record(self, row: dict) -> ScheduleInputWorkshopRecord:
        """
        将数据库行转换为 ScheduleInputWorkshopRecord 对象。

        Args:
            row: 数据库行（字典）

        Returns:
            ScheduleInputWorkshopRecord 对象
        """
        return ScheduleInputWorkshopRecord(
            schedule_id=row["schedule_id"],
            workshop_id=row["workshop_id"],
            workshop_name=row["workshop_name"],
            max_discharge_rate=float(row["max_discharge_rate"]),
            min_discharge_rate=float(row["min_discharge_rate"]),
            priority_weight=float(row["priority_weight"]),
            elastic_max_rate=float(row["elastic_max_rate"]) if row.get("elastic_max_rate") is not None else None,
            create_time=row["create_time"],
        )

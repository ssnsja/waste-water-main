# -*- coding: utf-8 -*-
"""
调度输入快照 DAO 模块
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Tuple

import oracledb

from backend.dao.base_dao import BaseDAO
from backend.model import ScheduleInputRecord
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class ScheduleInputDAO(BaseDAO):
    """调度输入系统级快照数据访问对象"""

    def insert(self, conn: oracledb.Connection, record: ScheduleInputRecord) -> None:
        """
        写入调度输入系统级快照，主键使用 SEQ_SCHEDULE_INPUT.NEXTVAL。

        Args:
            conn: 数据库连接（外部管理事务）
            record: 调度输入快照记录
        """
        sql = """
            INSERT INTO WW_SCHEDULE_INPUT
                (INPUT_ID, SCHEDULE_ID, SCHEDULE_TIME, TANK_CAPACITY, PROCESS_CAPACITY,
                 SCHEDULE_INTERVAL_MIN, SAFE_RATIO, WARNING_RATIO, ALERT_RATIO, EMERGENCY_RATIO,
                 MIN_RATE_RATIO, PROCESS_BUFFER_RATIO, TANK_LEVEL, LEVEL_RATIO, ZONE,
                 ELASTIC_K, CAPACITY_LIMIT, PROCESS_LIMIT, EFFECTIVE_LIMIT, WORKSHOP_COUNT, CREATE_TIME)
            VALUES
                (SEQ_SCHEDULE_INPUT.NEXTVAL, :schedule_id, :schedule_time, :tank_capacity, :process_capacity,
                 :schedule_interval_min, :safe_ratio, :warning_ratio, :alert_ratio, :emergency_ratio,
                 :min_rate_ratio, :process_buffer_ratio, :tank_level, :level_ratio, :zone,
                 :elastic_k, :capacity_limit, :process_limit, :effective_limit, :workshop_count, :create_time)
        """
        params = {
            "schedule_id": record.schedule_id,
            "schedule_time": record.schedule_time,
            "tank_capacity": record.tank_capacity,
            "process_capacity": record.process_capacity,
            "schedule_interval_min": record.schedule_interval_min,
            "safe_ratio": record.safe_ratio,
            "warning_ratio": record.warning_ratio,
            "alert_ratio": record.alert_ratio,
            "emergency_ratio": record.emergency_ratio,
            "min_rate_ratio": record.min_rate_ratio,
            "process_buffer_ratio": record.process_buffer_ratio,
            "tank_level": record.tank_level,
            "level_ratio": record.level_ratio,
            "zone": record.zone,
            "elastic_k": record.elastic_k,
            "capacity_limit": record.capacity_limit,
            "process_limit": record.process_limit,
            "effective_limit": record.effective_limit,
            "workshop_count": record.workshop_count,
            "create_time": record.schedule_time,
        }
        self.execute_dml(conn, sql, params)
        logger.debug(f"写入调度输入快照: schedule_id={record.schedule_id}")

    def get_by_schedule_id(self, schedule_id: str) -> Optional[ScheduleInputRecord]:
        """
        按调度批次号查询输入快照。

        Args:
            schedule_id: 调度批次号

        Returns:
            调度输入快照记录，不存在返回 None
        """
        sql = """
            SELECT SCHEDULE_ID, SCHEDULE_TIME, TANK_CAPACITY, PROCESS_CAPACITY,
                   SCHEDULE_INTERVAL_MIN, SAFE_RATIO, WARNING_RATIO, ALERT_RATIO,
                   EMERGENCY_RATIO, MIN_RATE_RATIO, PROCESS_BUFFER_RATIO,
                   TANK_LEVEL, LEVEL_RATIO, ZONE, ELASTIC_K,
                   CAPACITY_LIMIT, PROCESS_LIMIT, EFFECTIVE_LIMIT, WORKSHOP_COUNT
            FROM   WW_SCHEDULE_INPUT
            WHERE  SCHEDULE_ID = :schedule_id
        """
        rows = self.execute_query(sql, {"schedule_id": schedule_id})
        if not rows:
            return None
        return self._row_to_record(rows[0])

    def query_records(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        zone: Optional[str] = None,
        page: int = 1,
        page_size: int = 10,
    ) -> Tuple[int, list]:
        """
        分页聚合查询历史调度记录（从 WW_SCHEDULE_INPUT 主表 + LEFT JOIN WW_ALERT_LOG）。

        Args:
            start_time: 起始时间
            end_time: 结束时间
            zone: 液位区间筛选
            page: 页码
            page_size: 每页条数

        Returns:
            (总数, 记录字典列表)
        """
        conditions = []
        params: dict = {}

        if start_time:
            conditions.append("si.SCHEDULE_TIME >= :start_time")
            params["start_time"] = start_time
        if end_time:
            conditions.append("si.SCHEDULE_TIME <= :end_time")
            params["end_time"] = end_time
        if zone:
            conditions.append("si.ZONE = :zone")
            params["zone"] = zone

        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

        # 计算总数
        count_sql = f"SELECT COUNT(*) AS CNT FROM WW_SCHEDULE_INPUT si{where_clause}"
        count_rows = self.execute_query(count_sql, params)
        total = int(count_rows[0]["cnt"]) if count_rows else 0

        # 分页查询
        offset = (page - 1) * page_size
        data_sql = f"""
            SELECT * FROM (
                SELECT ROWNUM RN, T.* FROM (
                    SELECT si.SCHEDULE_ID, si.SCHEDULE_TIME, si.ZONE,
                           si.TANK_LEVEL, si.LEVEL_RATIO, si.WORKSHOP_COUNT,
                           al.ALERT_LEVEL, al.ALERT_TIME, al.ALERT_MESSAGE
                    FROM   WW_SCHEDULE_INPUT si
                    LEFT JOIN WW_ALERT_LOG al ON si.SCHEDULE_ID = al.SCHEDULE_ID
                    {where_clause}
                    ORDER  BY si.SCHEDULE_TIME DESC
                ) T WHERE ROWNUM <= :end_row
            ) WHERE RN > :start_row
        """
        params["start_row"] = offset
        params["end_row"] = offset + page_size

        rows = self.execute_query(data_sql, params)
        records = []
        for row in rows:
            alert_info = None
            if row.get("alert_level") is not None:
                alert_info = {
                    "alert_level": int(row["alert_level"]),
                    "alert_time": row.get("alert_time"),
                    "alert_message": row.get("alert_message", ""),
                }
            records.append({
                "schedule_id": row.get("schedule_id", ""),
                "schedule_time": row.get("schedule_time"),
                "zone": row.get("zone", ""),
                "tank_level": float(row["tank_level"]) if row.get("tank_level") is not None else None,
                "level_ratio": float(row["level_ratio"]) if row.get("level_ratio") is not None else None,
                "workshop_count": int(row.get("workshop_count", 0)),
                "solver_status": None,  # 需从 WW_SCHEDULE_RESULT 补充
                "alert_info": alert_info,
            })

        # 补充 solver_status
        if records:
            schedule_ids = [r["schedule_id"] for r in records]
            for rec in records:
                solver_sql = """
                    SELECT SOLVER_STATUS FROM (
                        SELECT SOLVER_STATUS
                        FROM   WW_SCHEDULE_RESULT
                        WHERE  SCHEDULE_ID = :schedule_id
                        ORDER  BY RESULT_ID
                    ) WHERE ROWNUM = 1
                """
                solver_rows = self.execute_query(solver_sql, {"schedule_id": rec["schedule_id"]})
                if solver_rows:
                    rec["solver_status"] = solver_rows[0]["solver_status"]

        return total, records

    def _row_to_record(self, row: dict) -> ScheduleInputRecord:
        """
        将数据库行转换为 ScheduleInputRecord 对象。

        Args:
            row: 数据库行（字典）

        Returns:
            ScheduleInputRecord 对象
        """
        return ScheduleInputRecord(
            schedule_id=row["schedule_id"],
            schedule_time=row["schedule_time"],
            tank_capacity=float(row["tank_capacity"]),
            process_capacity=float(row["process_capacity"]),
            schedule_interval_min=int(row["schedule_interval_min"]),
            safe_ratio=float(row["safe_ratio"]),
            warning_ratio=float(row["warning_ratio"]),
            alert_ratio=float(row["alert_ratio"]),
            emergency_ratio=float(row["emergency_ratio"]),
            min_rate_ratio=float(row["min_rate_ratio"]),
            process_buffer_ratio=float(row["process_buffer_ratio"]),
            tank_level=float(row["tank_level"]),
            level_ratio=float(row["level_ratio"]),
            zone=row["zone"],
            elastic_k=float(row["elastic_k"]) if row.get("elastic_k") is not None else None,
            capacity_limit=float(row["capacity_limit"]) if row.get("capacity_limit") is not None else None,
            process_limit=float(row["process_limit"]) if row.get("process_limit") is not None else None,
            effective_limit=float(row["effective_limit"]) if row.get("effective_limit") is not None else None,
            workshop_count=int(row["workshop_count"]),
        )

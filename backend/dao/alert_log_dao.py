# -*- coding: utf-8 -*-
"""
告警日志 DAO 模块
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Tuple

import oracledb

from backend.dao.base_dao import BaseDAO
from backend.model import AlertRecord
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class AlertLogDAO(BaseDAO):
    """告警日志数据访问对象"""

    def insert(self, conn: oracledb.Connection, record: AlertRecord) -> None:
        """
        写入告警记录，主键使用 SEQ_ALERT_LOG.NEXTVAL。

        Args:
            conn: 数据库连接（外部管理事务）
            record: 告警记录
        """
        sql = """
            INSERT INTO WW_ALERT_LOG
                (ALERT_ID, SCHEDULE_ID, ALERT_TIME, ALERT_LEVEL, TANK_LEVEL,
                 LEVEL_RATIO, ALERT_MESSAGE, IS_HANDLED, CREATE_TIME)
            VALUES
                (SEQ_ALERT_LOG.NEXTVAL, :schedule_id, :alert_time, :alert_level, :tank_level,
                 :level_ratio, :alert_message, :is_handled, :create_time)
        """
        params = {
            "schedule_id": record.schedule_id,
            "alert_time": record.alert_time,
            "alert_level": record.alert_level,
            "tank_level": record.tank_level,
            "level_ratio": record.level_ratio,
            "alert_message": record.alert_message,
            "is_handled": record.is_handled,
            "create_time": record.create_time,
        }
        self.execute_dml(conn, sql, params)
        logger.debug(f"写入告警记录: 级别={record.alert_level}, 液位={record.tank_level}")

    def get_by_schedule_id(self, schedule_id: str) -> Optional[AlertRecord]:
        """
        根据调度批次号查询告警记录。

        Args:
            schedule_id: 调度批次号

        Returns:
            告警记录，不存在则返回 None
        """
        sql = """
            SELECT ALERT_ID, SCHEDULE_ID, ALERT_TIME, ALERT_LEVEL, TANK_LEVEL,
                   LEVEL_RATIO, ALERT_MESSAGE, IS_HANDLED, HANDLED_BY,
                   HANDLED_TIME, HANDLE_REMARK, CREATE_TIME
            FROM   WW_ALERT_LOG
            WHERE  SCHEDULE_ID = :schedule_id
        """
        rows = self.execute_query(sql, {"schedule_id": schedule_id})
        if not rows:
            return None
        return self._row_to_record(rows[0])

    def get_recent_alerts(self, limit: int = 10) -> List[AlertRecord]:
        """
        查询最近 N 条告警记录。

        Args:
            limit: 返回条数

        Returns:
            告警记录列表
        """
        sql = """
            SELECT ALERT_ID, SCHEDULE_ID, ALERT_TIME, ALERT_LEVEL, TANK_LEVEL,
                   LEVEL_RATIO, ALERT_MESSAGE, IS_HANDLED, CREATE_TIME
            FROM (
                SELECT ALERT_ID, SCHEDULE_ID, ALERT_TIME, ALERT_LEVEL, TANK_LEVEL,
                       LEVEL_RATIO, ALERT_MESSAGE, IS_HANDLED, CREATE_TIME
                FROM   WW_ALERT_LOG
                ORDER  BY ALERT_TIME DESC
            ) WHERE ROWNUM <= :limit
        """
        rows = self.execute_query(sql, {"limit": limit})
        records = [self._row_to_record(row) for row in rows]
        logger.debug(f"查询最近 {limit} 条告警: 返回 {len(records)} 条")
        return records

    def query_alerts(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        alert_level: Optional[int] = None,
        is_handled: Optional[int] = None,
        page: int = 1,
        page_size: int = 10,
    ) -> Tuple[int, List[dict]]:
        """
        分页查询告警记录。

        Args:
            start_time: 起始时间
            end_time: 结束时间
            alert_level: 告警级别筛选
            is_handled: 是否已处理筛选
            page: 页码
            page_size: 每页条数

        Returns:
            (总数, 记录字典列表)
        """
        conditions = []
        params: dict = {}

        if start_time:
            conditions.append("ALERT_TIME >= :start_time")
            params["start_time"] = start_time
        if end_time:
            conditions.append("ALERT_TIME <= :end_time")
            params["end_time"] = end_time
        if alert_level is not None:
            conditions.append("ALERT_LEVEL = :alert_level")
            params["alert_level"] = alert_level
        if is_handled is not None:
            conditions.append("IS_HANDLED = :is_handled")
            params["is_handled"] = is_handled

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        # 计算总数
        count_sql = f"SELECT COUNT(*) AS CNT FROM WW_ALERT_LOG WHERE {where_clause}"
        count_rows = self.execute_query(count_sql, params)
        total = int(count_rows[0]["cnt"]) if count_rows else 0

        # 分页查询（Oracle 11g ROWNUM 分页）
        offset = (page - 1) * page_size
        data_sql = f"""
            SELECT * FROM (
                SELECT ROWNUM RN, T.* FROM (
                    SELECT ALERT_ID, SCHEDULE_ID, ALERT_TIME, ALERT_LEVEL, TANK_LEVEL,
                           LEVEL_RATIO, ALERT_MESSAGE, IS_HANDLED, CREATE_TIME
                    FROM   WW_ALERT_LOG
                    WHERE  {where_clause}
                    ORDER  BY ALERT_TIME DESC
                ) T WHERE ROWNUM <= :end_row
            ) WHERE RN > :start_row
        """
        params["start_row"] = offset
        params["end_row"] = offset + page_size

        rows = self.execute_query(data_sql, params)
        records = []
        for row in rows:
            records.append({
                "alert_id": row.get("alert_id"),
                "schedule_id": row.get("schedule_id", ""),
                "alert_time": row.get("alert_time"),
                "alert_level": row.get("alert_level"),
                "tank_level": float(row["tank_level"]) if row.get("tank_level") is not None else None,
                "level_ratio": float(row["level_ratio"]) if row.get("level_ratio") is not None else None,
                "alert_message": row.get("alert_message", ""),
                "is_handled": int(row.get("is_handled", 0)),
            })

        return total, records

    def _row_to_record(self, row: dict) -> AlertRecord:
        """
        将数据库行转换为 AlertRecord 对象。

        Args:
            row: 数据库行（字典）

        Returns:
            AlertRecord 对象
        """
        return AlertRecord(
            schedule_id=row.get("schedule_id", ""),
            alert_time=row["alert_time"],
            alert_level=row["alert_level"],
            tank_level=row["tank_level"],
            level_ratio=row["level_ratio"],
            alert_message=row["alert_message"],
            is_handled=row.get("is_handled", 0),
            create_time=row.get("create_time"),
        )

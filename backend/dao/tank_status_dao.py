# -*- coding: utf-8 -*-
"""
储罐状态 DAO 模块
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Tuple

import oracledb

from backend.dao.base_dao import BaseDAO
from backend.model import TankStatusRecord
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class TankStatusDAO(BaseDAO):
    """储罐状态数据访问对象"""

    def get_latest_manual_level(self) -> Optional[Tuple[float, datetime]]:
        """
        返回最新一条 INPUT_TYPE=MANUAL 的液位值和创建时间。

        Returns:
            (液位值, 创建时间) 元组，无记录返回 None
        """
        sql = """
            SELECT CURRENT_LEVEL, CREATE_TIME FROM (
                SELECT CURRENT_LEVEL, CREATE_TIME
                FROM   WW_TANK_STATUS
                WHERE  INPUT_TYPE = 'MANUAL'
                ORDER  BY CREATE_TIME DESC
            ) WHERE ROWNUM = 1
        """
        rows = self.execute_query(sql)
        if rows:
            level = float(rows[0]["current_level"])
            create_time = rows[0]["create_time"]
            logger.debug(f"获取最新手动液位: {level} m³, 时间: {create_time}")
            return level, create_time
        logger.warning("未找到手动录入的液位记录")
        return None

    def insert(self, conn: oracledb.Connection, record: TankStatusRecord) -> None:
        """
        写入液位快照，主键使用 SEQ_TANK_STATUS.NEXTVAL。

        Args:
            conn: 数据库连接（外部管理事务）
            record: 储罐状态记录
        """
        sql = """
            INSERT INTO WW_TANK_STATUS
                (STATUS_ID, RECORD_TIME, CURRENT_LEVEL, LEVEL_RATIO,
                 TANK_STATUS, PREDICTED_LEVEL, INPUT_TYPE,CREATE_TIME)
            VALUES
                (SEQ_TANK_STATUS.NEXTVAL, :record_time, :current_level, :level_ratio,
                 :tank_status, :predicted_level, :input_type, :create_time)
        """
        params = {
            "record_time": record.record_time,
            "current_level": record.current_level,
            "level_ratio": record.level_ratio,
            "tank_status": record.tank_status,
            "predicted_level": record.predicted_level,
            "input_type": record.input_type,
            "create_time": record.create_time
        }
        self.execute_dml(conn, sql, params)
        logger.debug(
            f"写入液位快照: 液位={record.current_level} m³, 状态={record.tank_status}"
        )

    def get_trend(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> dict:
        """
        获取历史液位趋势数据。

        Args:
            start_time: 起始时间
            end_time: 结束时间

        Returns:
            dict: {times: [...], levels: [...], predicted: [...]}
        """
        conditions = ["INPUT_TYPE = 'MANUAL'"]
        params: dict = {}

        if start_time:
            conditions.append("CREATE_TIME >= :start_time")
            params["start_time"] = start_time
        if end_time:
            conditions.append("CREATE_TIME <= :end_time")
            params["end_time"] = end_time

        where_clause = " AND ".join(conditions)

        sql = f"""
            SELECT RECORD_TIME, CURRENT_LEVEL, PREDICTED_LEVEL
            FROM   WW_TANK_STATUS
            WHERE  {where_clause}
            ORDER  BY CREATE_TIME ASC
        """
        rows = self.execute_query(sql, params)

        times = []
        levels = []
        predicted = []

        for row in rows:
            rt = row["record_time"]
            if isinstance(rt, datetime):
                times.append(rt.strftime("%H:%M"))
            else:
                times.append(str(rt))
            levels.append(round(float(row["current_level"]), 1))
            pred = row.get("predicted_level")
            predicted.append(round(float(pred), 1) if pred is not None else None)

        return {"times": times, "levels": levels, "predicted": predicted}

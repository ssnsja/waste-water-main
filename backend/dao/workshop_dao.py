# -*- coding: utf-8 -*-
"""
车间信息 DAO 模块
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

import oracledb

from backend.dao.base_dao import BaseDAO
from backend.model import Workshop
from backend.utils.exceptions import DBWriteError
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class WorkshopDAO(BaseDAO):
    """车间信息数据访问对象"""

    def get_active_workshops(self) -> List[Workshop]:
        """
        查询 IS_ACTIVE=1 的车间列表，按 WORKSHOP_ID 排序。

        Returns:
            启用状态的车间列表
        """
        sql = """
            SELECT WORKSHOP_ID, WORKSHOP_NAME, MAX_DISCHARGE_RATE,
                   MIN_DISCHARGE_RATE, PRIORITY_WEIGHT,
                   IS_ACTIVE, REMARK, UPDATE_TIME
            FROM   WW_WORKSHOP_INFO
            WHERE  IS_ACTIVE = 1
            ORDER  BY WORKSHOP_ID
        """
        rows = self.execute_query(sql)
        workshops = [self._row_to_workshop(row) for row in rows]
        logger.debug(f"查询到 {len(workshops)} 个启用车间")
        return workshops

    def get_all(self) -> List[Workshop]:
        """
        查询全部车间列表（含停用），按 WORKSHOP_ID 排序。

        Returns:
            全部车间列表
        """
        sql = """
            SELECT WORKSHOP_ID, WORKSHOP_NAME, MAX_DISCHARGE_RATE,
                   MIN_DISCHARGE_RATE, PRIORITY_WEIGHT,
                   IS_ACTIVE, REMARK, UPDATE_TIME
            FROM   WW_WORKSHOP_INFO
            ORDER  BY WORKSHOP_ID
        """
        rows = self.execute_query(sql)
        workshops = [self._row_to_workshop(row) for row in rows]
        logger.debug(f"查询到 {len(workshops)} 个车间")
        return workshops

    def get_by_id(self, workshop_id: str) -> Optional[Workshop]:
        """
        根据车间编号查询车间信息。

        Args:
            workshop_id: 车间编号

        Returns:
            车间信息，不存在返回 None
        """
        sql = """
            SELECT WORKSHOP_ID, WORKSHOP_NAME, MAX_DISCHARGE_RATE,
                   MIN_DISCHARGE_RATE, PRIORITY_WEIGHT,
                   IS_ACTIVE, REMARK, UPDATE_TIME
            FROM   WW_WORKSHOP_INFO
            WHERE  WORKSHOP_ID = :workshop_id
        """
        rows = self.execute_query(sql, {"workshop_id": workshop_id})
        if not rows:
            return None
        return self._row_to_workshop(rows[0])

    def insert(self, conn: oracledb.Connection, workshop: Workshop) -> None:
        """
        新增车间记录。

        Args:
            conn: 数据库连接（外部管理事务）
            workshop: 车间信息
        """
        sql = """
            INSERT INTO WW_WORKSHOP_INFO
                (WORKSHOP_ID, WORKSHOP_NAME, MAX_DISCHARGE_RATE,
                 MIN_DISCHARGE_RATE, PRIORITY_WEIGHT, IS_ACTIVE,
                 REMARK, CREATE_TIME, UPDATE_TIME)
            VALUES
                (:workshop_id, :workshop_name, :max_discharge_rate,
                 :min_discharge_rate, :priority_weight, :is_active,
                 :remark, :create_time, :update_time)
        """
        now = datetime.now()
        params = {
            "workshop_id": workshop.workshop_id,
            "workshop_name": workshop.workshop_name,
            "max_discharge_rate": workshop.max_discharge_rate,
            "min_discharge_rate": workshop.min_discharge_rate,
            "priority_weight": workshop.priority_weight,
            "is_active": workshop.is_active,
            "remark": workshop.remark,
            "create_time": now,
            "update_time": now,
        }
        self.execute_dml(conn, sql, params)
        logger.debug(f"新增车间: {workshop.workshop_id}")

    def update(self, conn: oracledb.Connection, workshop_id: str, data: Dict[str, object]) -> None:
        """
        更新车间信息（部分字段）。

        Args:
            conn: 数据库连接（外部管理事务）
            workshop_id: 车间编号
            data: 待更新字段字典
        """
        # 构建动态 SET 子句
        set_clauses = []
        params: Dict[str, object] = {"workshop_id": workshop_id}

        field_mapping = {
            "workshop_name": "WORKSHOP_NAME",
            "max_discharge_rate": "MAX_DISCHARGE_RATE",
            "min_discharge_rate": "MIN_DISCHARGE_RATE",
            "priority_weight": "PRIORITY_WEIGHT",
            "is_active": "IS_ACTIVE",
            "remark": "REMARK",
        }

        for py_name, db_col in field_mapping.items():
            if py_name in data:
                set_clauses.append(f"{db_col} = :{py_name}")
                params[py_name] = data[py_name]

        if not set_clauses:
            return

        # 始终更新 UPDATE_TIME
        set_clauses.append("UPDATE_TIME = :update_time")
        params["update_time"] = datetime.now()

        sql = f"""
            UPDATE WW_WORKSHOP_INFO
            SET    {', '.join(set_clauses)}
            WHERE  WORKSHOP_ID = :workshop_id
        """
        self.execute_dml(conn, sql, params)
        logger.debug(f"更新车间: {workshop_id}, 字段: {list(data.keys())}")

    def deactivate(self, conn: oracledb.Connection, workshop_id: str) -> None:
        """
        逻辑删除车间（IS_ACTIVE=0）。

        Args:
            conn: 数据库连接（外部管理事务）
            workshop_id: 车间编号
        """
        sql = """
            UPDATE WW_WORKSHOP_INFO
            SET    IS_ACTIVE = 0, UPDATE_TIME = :update_time
            WHERE  WORKSHOP_ID = :workshop_id
        """
        self.execute_dml(
            conn, sql,
            {"workshop_id": workshop_id, "update_time": datetime.now()},
        )
        logger.debug(f"逻辑删除车间: {workshop_id}")

    def _row_to_workshop(self, row: dict) -> Workshop:
        """
        将数据库行转换为 Workshop 对象。

        Args:
            row: 数据库行（字典）

        Returns:
            Workshop 对象
        """
        return Workshop(
            workshop_id=row["workshop_id"],
            workshop_name=row["workshop_name"],
            max_discharge_rate=float(row["max_discharge_rate"]),
            min_discharge_rate=float(row["min_discharge_rate"]),
            priority_weight=float(row["priority_weight"]),
            is_active=int(row.get("is_active", 1)),
            remark=row.get("remark", "") or "",
            update_time=row.get("update_time"),
        )

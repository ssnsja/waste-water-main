# -*- coding: utf-8 -*-
"""
DAO 基类模块

封装连接池，提供通用数据库操作方法。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import oracledb

from backend.utils.exceptions import DBQueryError, DBWriteError
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class BaseDAO:
    """DAO 基类，封装连接池操作"""

    def __init__(self, pool: oracledb.ConnectionPool) -> None:
        """
        初始化 DAO 基类。

        Args:
            pool: Oracle 连接池实例
        """
        self._pool = pool

    def execute_query(
        self, sql: str, params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        执行只读查询，自动从池获取连接，查完自动归还。

        Args:
            sql: SQL 查询语句
            params: 绑定参数字典（可选）

        Returns:
            查询结果列表，每条记录为字典（列名转小写）

        Raises:
            DBQueryError: 数据库查询异常
        """
        conn = None
        try:
            conn = self._pool.acquire()
            cursor = conn.cursor()
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)

            # 获取列名，转为小写
            columns = [col[0].lower() for col in cursor.description]
            rows = cursor.fetchall()

            # 转换为字典列表
            result = [dict(zip(columns, row)) for row in rows]

            cursor.close()
            return result

        except oracledb.DatabaseError as e:
            error_msg = f"数据库查询失败: {e}"
            logger.error(error_msg, exc_info=True)
            raise DBQueryError(error_msg) from e
        finally:
            if conn is not None:
                self._pool.release(conn)

    def execute_dml(
        self, conn: oracledb.Connection, sql: str, params: Dict[str, Any]
    ) -> None:
        """
        执行单条 DML，使用外部传入连接（调用方控制事务）。

        Args:
            conn: 数据库连接（外部管理）
            sql: SQL 语句
            params: 绑定参数字典

        Raises:
            DBWriteError: 数据库写入异常
        """
        try:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            cursor.close()
        except oracledb.DatabaseError as e:
            error_msg = f"数据库 DML 执行失败: {e}"
            logger.error(error_msg, exc_info=True)
            raise DBWriteError(error_msg) from e

    def execute_batch(
        self,
        conn: oracledb.Connection,
        sql: str,
        params_list: List[Dict[str, Any]],
    ) -> None:
        """
        执行批量 DML，使用 executemany，使用外部传入连接。

        Args:
            conn: 数据库连接（外部管理）
            sql: SQL 语句
            params_list: 绑定参数字典列表

        Raises:
            DBWriteError: 数据库写入异常
        """
        try:
            cursor = conn.cursor()
            cursor.executemany(sql, params_list)
            cursor.close()
        except oracledb.DatabaseError as e:
            error_msg = f"数据库批量 DML 执行失败: {e}"
            logger.error(error_msg, exc_info=True)
            raise DBWriteError(error_msg) from e

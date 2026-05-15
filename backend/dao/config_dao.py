# -*- coding: utf-8 -*-
"""
系统配置 DAO 模块
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List

import oracledb

from backend.dao.base_dao import BaseDAO
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class ConfigDAO(BaseDAO):
    """系统配置数据访问对象"""

    def get_all_configs(self) -> Dict[str, str]:
        """
        返回所有配置项字典。

        Returns:
            配置项字典，key=CONFIG_KEY，value=CONFIG_VALUE
        """
        sql = """
            SELECT CONFIG_KEY, CONFIG_VALUE
            FROM   WW_SYSTEM_CONFIG
        """
        rows = self.execute_query(sql)
        configs = {row["config_key"]: row["config_value"] for row in rows}
        logger.debug(f"加载 {len(configs)} 个配置项")
        return configs

    def update_batch(self, conn: oracledb.Connection, configs: Dict[str, str]) -> None:
        """
        批量更新配置项。

        Args:
            conn: 数据库连接（外部管理事务）
            configs: 配置项字典，key=CONFIG_KEY，value=CONFIG_VALUE
        """
        sql = """
            UPDATE WW_SYSTEM_CONFIG
            SET    CONFIG_VALUE = :config_value, UPDATE_TIME = :update_time
            WHERE  CONFIG_KEY = :config_key
        """
        now = datetime.now()
        params_list = [
            {"config_key": key, "config_value": str(value), "update_time": now}
            for key, value in configs.items()
        ]
        self.execute_batch(conn, sql, params_list)
        logger.debug(f"批量更新 {len(configs)} 个配置项")

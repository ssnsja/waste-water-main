# -*- coding: utf-8 -*-
"""
调度触发层模块

APScheduler 定时触发 + 对外暴露 run_once() 供 CLI 调用。
支持通过 restart() 方法热更新调度间隔。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from backend.dao.tank_status_dao import TankStatusDAO
from backend.scheduler.config_service import ConfigService
from backend.scheduler.scheduler_service import SchedulerService
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# 默认配置（数据库不可用时使用）
DEFAULT_SCHEDULE_INTERVAL_MIN = 30
DEFAULT_MANUAL_LEVEL_STALE_THRESHOLD = 2


class SchedulerTrigger:
    """调度触发器，支持热更新"""

    def __init__(
        self,
        scheduler_svc: SchedulerService,
        config_svc: ConfigService,
        tank_dao: TankStatusDAO,
    ) -> None:
        """
        初始化触发器。

        Args:
            scheduler_svc: 调度服务
            config_svc: 配置服务
            tank_dao: 储罐状态 DAO
        """
        self._scheduler_svc = scheduler_svc
        self._config_svc = config_svc
        self._tank_dao = tank_dao

        # 当前调度间隔（分钟）
        self._interval_min: int = DEFAULT_SCHEDULE_INTERVAL_MIN
        self._stale_threshold: int = DEFAULT_MANUAL_LEVEL_STALE_THRESHOLD

        # 创建后台调度器
        self._scheduler = BackgroundScheduler(
            executors={"default": ThreadPoolExecutor(max_workers=1)}
        )

    def start(self) -> None:
        """启动 APScheduler BackgroundScheduler，从数据库读取调度间隔。"""
        # 从数据库读取配置
        try:
            params = self._config_svc.get_all_params()
            self._interval_min = params.schedule_interval_min
            self._stale_threshold = params.manual_level_stale_threshold
            # 清除缓存，确保下次读取最新配置
            self._config_svc.refresh()
        except Exception as e:
            logger.warning(f"从数据库读取调度配置失败，使用默认值: {e}")

        self._scheduler.add_job(
            func=self.run_once,
            trigger=IntervalTrigger(minutes=self._interval_min),
            max_instances=1,  # 防止任务重叠
            coalesce=True,  # 错过的任务合并为一次
            misfire_grace_time=60,  # 错过触发时间的容忍秒数
            id="waste_water_scheduler",
            replace_existing=True,
        )
        self._scheduler.start()
        logger.info(f"调度器已启动，周期={self._interval_min}分钟")

    def stop(self) -> None:
        """优雅停止调度器。"""
        self._scheduler.shutdown(wait=True)
        logger.info("调度器已停止")

    def restart(self) -> None:
        """
        重启调度器，重新从数据库读取配置。

        前端修改配置后调用此方法使配置生效。
        """
        logger.info("正在重启调度器...")
        was_running = self._scheduler.running

        if was_running:
            self._scheduler.shutdown(wait=True)

        # 重新读取配置
        try:
            params = self._config_svc.get_all_params()
            self._interval_min = params.schedule_interval_min
            self._stale_threshold = params.manual_level_stale_threshold
            logger.info(f"配置已更新：周期={self._interval_min}分钟，超期阈值={self._stale_threshold}倍周期")
        except Exception as e:
            logger.error(f"重启调度器时读取配置失败: {e}")
            # 使用当前配置继续

        if was_running:
            # 重新创建调度器
            self._scheduler = BackgroundScheduler(
                executors={"default": ThreadPoolExecutor(max_workers=1)}
            )
            self._scheduler.add_job(
                func=self.run_once,
                trigger=IntervalTrigger(minutes=self._interval_min),
                max_instances=1,
                coalesce=True,
                misfire_grace_time=60,
                id="waste_water_scheduler",
                replace_existing=True,
            )
            self._scheduler.start()
            logger.info(f"调度器已重启，周期={self._interval_min}分钟")

    def get_interval_min(self) -> int:
        """获取当前调度间隔（分钟）。"""
        return self._interval_min

    def get_stale_threshold(self) -> int:
        """获取液位超期阈值（调度周期倍数）。"""
        return self._stale_threshold

    def run_once(self, tank_level: Optional[float] = None) -> None:
        """
        APScheduler 回调或手动触发：

        1. 从 DB 读取最新 MANUAL 液位（TankStatusDAO.get_latest_manual_level）
        2. 检查时效（超 N×T 记录 WARNING，不中止）
        3. 调用 SchedulerService.run(tank_level)

        Args:
            tank_level: 手动传入的液位值（可选，用于 CLI 手动触发）
        """
        schedule_id = datetime.now().strftime("%Y%m%d%H%M%S")
        logger.info(f"[{schedule_id}] 触发调度...")

        try:
            if tank_level is None:
                # 定时触发：从数据库读取最新手动液位
                result = self._tank_dao.get_latest_manual_level()
                if result is None:
                    logger.error(f"[{schedule_id}] 无法获取液位，跳过本次调度")
                    return

                tank_level, create_time = result

                # 时效检查（使用数据库配置的阈值）
                stale_threshold = timedelta(
                    minutes=self._interval_min * self._stale_threshold
                )
                if datetime.now() - create_time > stale_threshold:
                    logger.warning(
                        f"[{schedule_id}] 液位数据超期未更新 "
                        f"(距上次更新 {(datetime.now() - create_time).total_seconds() / 60:.1f} 分钟)"
                    )

            # 执行调度
            self._scheduler_svc.run(tank_level)

        except Exception as e:
            logger.error(f"[{schedule_id}] 调度执行失败: {e}", exc_info=True)

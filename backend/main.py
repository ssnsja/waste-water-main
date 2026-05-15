# -*- coding: utf-8 -*-
"""
程序入口

依赖注入组装 + 定时启动 / CLI 手动触发
"""

from __future__ import annotations

import argparse
import signal
import sys

import oracledb

from backend.config.settings import (
    DB_DSN,
    DB_PASSWORD,
    DB_USER,
    ORACLE_CLIENT_LIB_DIR,
    POOL_INCREMENT,
    POOL_MAX,
    POOL_MIN,
    POOL_PING_INTERVAL,
)
from backend.dao.alert_log_dao import AlertLogDAO
from backend.dao.config_dao import ConfigDAO
from backend.dao.schedule_input_dao import ScheduleInputDAO
from backend.dao.schedule_input_workshop_dao import ScheduleInputWorkshopDAO
from backend.dao.schedule_result_dao import ScheduleResultDAO
from backend.dao.tank_status_dao import TankStatusDAO
from backend.dao.workshop_dao import WorkshopDAO
from backend.scheduler.alert_service import AlertService
from backend.scheduler.config_service import ConfigService
from backend.scheduler.scheduler_service import SchedulerService
from backend.scheduler.solver_service import SolverService
from backend.scheduler.trigger import SchedulerTrigger
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# 全局变量，用于优雅退出
_trigger: SchedulerTrigger | None = None
_pool: oracledb.ConnectionPool | None = None


def build_dependencies() -> SchedulerTrigger:
    """
    完成所有依赖注入：
    初始化 oracledb Thick Mode → 创建连接池 → 实例化 DAO/Service/Trigger

    Returns:
        SchedulerTrigger 实例
    """
    global _pool

    # 1. 初始化 Oracle Thick Mode
    logger.info("初始化 Oracle Thick Mode...")
    #oracledb.init_oracle_client(lib_dir=ORACLE_CLIENT_LIB_DIR)

    # 2. 创建连接池
    logger.info("创建数据库连接池...")
    _pool = oracledb.create_pool(
        user=DB_USER,
        password=DB_PASSWORD,
        dsn=DB_DSN,
        min=POOL_MIN,
        max=POOL_MAX,
        increment=POOL_INCREMENT,
        ping_interval=POOL_PING_INTERVAL,
    )

    # 3. 实例化各 DAO
    workshop_dao = WorkshopDAO(_pool)
    config_dao = ConfigDAO(_pool)
    tank_dao = TankStatusDAO(_pool)
    result_dao = ScheduleResultDAO(_pool)
    alert_dao = AlertLogDAO(_pool)
    input_dao = ScheduleInputDAO(_pool)
    input_workshop_dao = ScheduleInputWorkshopDAO(_pool)

    # 4. 实例化各 Service
    config_svc = ConfigService(config_dao)
    solver_svc = SolverService()
    alert_svc = AlertService()
    scheduler_svc = SchedulerService(
        config_svc=config_svc,
        solver_svc=solver_svc,
        alert_svc=alert_svc,
        workshop_dao=workshop_dao,
        tank_dao=tank_dao,
        result_dao=result_dao,
        alert_dao=alert_dao,
        input_dao=input_dao,
        input_workshop_dao=input_workshop_dao,
        pool=_pool,
    )

    # 5. 实例化 Trigger
    trigger = SchedulerTrigger(
        scheduler_svc=scheduler_svc,
        config_svc=config_svc,
        tank_dao=tank_dao,
    )

    logger.info("依赖注入完成")
    return trigger


def run_scheduled() -> None:
    """启动定时调度，注册 SIGINT/SIGTERM 优雅退出。"""
    global _trigger

    _trigger = build_dependencies()

    def signal_handler(signum, frame):
        """信号处理函数，优雅退出"""
        logger.info(f"收到信号 {signum}，正在退出...")
        if _trigger:
            _trigger.stop()
        if _pool:
            _pool.close()
            logger.info("连接池已关闭")
        sys.exit(0)

    # 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 启动定时调度
    _trigger.start()

    logger.info("定时调度已启动，按 Ctrl+C 退出")

    # 保持主线程运行
    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        signal_handler(signal.SIGINT, None)


def run_manual(tank_level: float) -> None:
    """手动触发一次调度，完成后退出。"""
    global _trigger, _pool

    try:
        _trigger = build_dependencies()
        _trigger.run_once(tank_level=tank_level)
        logger.info(f"手动调度完成，液位={tank_level}")
    finally:
        if _pool:
            _pool.close()
            logger.info("连接池已关闭")


def run_web(with_scheduler: bool = False) -> None:
    """启动 Web 服务（FastAPI + uvicorn）。"""
    global _trigger, _pool

    _trigger = build_dependencies()

    if with_scheduler:
        _trigger.start()

    from backend.api.app import create_app
    app = create_app(
        scheduler_svc=_trigger._scheduler_svc,
        config_svc=_trigger._config_svc,
        trigger=_trigger,
        pool=_pool,
    )

    import uvicorn
    logger.info("Web 服务启动中... (host=127.0.0.1, port=8000)")
    uvicorn.run(app, host="127.0.0.1", port=8000)


def main() -> None:
    """主入口"""
    parser = argparse.ArgumentParser(description="废水排放调度系统")
    parser.add_argument(
        "--manual",
        action="store_true",
        help="手动触发模式",
    )
    parser.add_argument(
        "--level",
        type=float,
        help="手动模式指定的液位值（m³）",
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="启动 Web 服务（FastAPI + uvicorn）",
    )
    parser.add_argument(
        "--with-scheduler",
        action="store_true",
        help="Web 模式下同时启动定时调度",
    )

    args = parser.parse_args()

    if args.manual:
        if args.level is None:
            parser.error("手动模式必须指定 --level 参数")
        run_manual(args.level)
    elif args.web:
        run_web(with_scheduler=args.with_scheduler)
    else:
        run_scheduled()


if __name__ == "__main__":
    main()

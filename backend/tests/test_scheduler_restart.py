"""
测试调度器重启功能

执行方式（在 waste_water/ 根目录下）：python backend/tests/test_scheduler_restart.py
"""

import sys
import time

# 添加项目根目录到路径
sys.path.insert(0, r"D:\CodeSpace\pyCodeSpace\waste_water")

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
import oracledb

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


def main() -> None:
    pool = None
    trigger = None

    try:
        # Step 1: 初始化 Oracle Thick Mode
        print("[Step 1] 初始化 Oracle Thick Mode...")
        oracledb.init_oracle_client(lib_dir=ORACLE_CLIENT_LIB_DIR)
        print("[OK] Thick Mode 初始化成功")

        # Step 2: 创建连接池
        print("[Step 2] 创建数据库连接池...")
        pool = oracledb.create_pool(
            user=DB_USER,
            password=DB_PASSWORD,
            dsn=DB_DSN,
            min=POOL_MIN,
            max=POOL_MAX,
            increment=POOL_INCREMENT,
            ping_interval=POOL_PING_INTERVAL,
        )
        print("[OK] 连接池创建成功")

        # Step 3: 实例化 DAO
        print("[Step 3] 实例化 DAO...")
        workshop_dao = WorkshopDAO(pool)
        config_dao = ConfigDAO(pool)
        tank_dao = TankStatusDAO(pool)
        result_dao = ScheduleResultDAO(pool)
        alert_dao = AlertLogDAO(pool)
        input_dao = ScheduleInputDAO(pool)
        input_workshop_dao = ScheduleInputWorkshopDAO(pool)
        print("[OK] DAO 实例化完成")

        # Step 4: 实例化 Service
        print("[Step 4] 实例化 Service...")
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
            pool=pool,
        )
        print("[OK] Service 实例化完成")

        # Step 5: 实例化 Trigger
        print("[Step 5] 实例化 SchedulerTrigger...")
        trigger = SchedulerTrigger(
            scheduler_svc=scheduler_svc,
            config_svc=config_svc,
            tank_dao=tank_dao,
        )
        print("[OK] Trigger 实例化完成")

        # Step 6: 启动调度器
        print("[Step 6] 启动调度器...")
        trigger.start()
        interval = trigger.get_interval_min()
        stale = trigger.get_stale_threshold()
        print(f"[OK] 调度器已启动，当前配置：周期={interval}分钟，超期阈值={stale}倍周期")

        # Step 7: 测试 restart 方法
        print("[Step 7] 测试 restart 方法...")
        time.sleep(1)  # 等待一秒
        trigger.restart()
        new_interval = trigger.get_interval_min()
        new_stale = trigger.get_stale_threshold()
        print(f"[OK] 调度器已重启，当前配置：周期={new_interval}分钟，超期阈值={new_stale}倍周期")

        # Step 8: 验证配置一致
        if new_interval == interval and new_stale == stale:
            print("[OK] 重启后配置保持一致")
        else:
            print(f"[WARN] 重启后配置发生变化（可能是数据库配置被修改）")

        # Step 9: 停止调度器
        print("[Step 8] 停止调度器...")
        trigger.stop()
        print("[OK] 调度器已停止")

        print("\n--- 调度器重启测试通过 ---")

    except Exception as e:
        print(f"[FAIL] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        if trigger:
            try:
                trigger.stop()
            except:
                pass
        if pool:
            pool.close()
            print("[OK] 连接池已关闭")


if __name__ == "__main__":
    main()

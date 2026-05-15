# -*- coding: utf-8 -*-
"""
FastAPI 应用工厂

创建 FastAPI 实例，注册路由，配置静态文件服务和页面路由。
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.utils.logger import get_logger

logger = get_logger(__name__)

FRONTEND_DIR = str(Path(__file__).parent.parent.parent / "frontend")


def create_app(
    scheduler_svc=None,
    config_svc=None,
    trigger=None,
    pool=None,
) -> FastAPI:
    """
    创建 FastAPI 应用实例。

    Args:
        scheduler_svc: 调度服务实例
        config_svc: 配置服务实例
        trigger: 调度触发器实例
        pool: 数据库连接池

    Returns:
        FastAPI 应用实例
    """
    app = FastAPI(
        title="废水排放调度系统 API",
        description="建议层（Advisory System）前后端联调 API",
        version="1.0.0",
    )

    # 将依赖注入对象存储到 app.state
    app.state.scheduler_svc = scheduler_svc
    app.state.config_svc = config_svc
    app.state.trigger = trigger
    app.state.pool = pool

    # 注册路由
    from backend.api.routes import dashboard, history, schedule, workshop, config, alert
    app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
    app.include_router(history.router, prefix="/api/history", tags=["History"])
    app.include_router(schedule.router, prefix="/api/schedule", tags=["Schedule"])
    app.include_router(workshop.router, prefix="/api/workshops", tags=["Workshops"])
    app.include_router(config.router, prefix="/api/config", tags=["Config"])
    app.include_router(alert.router, prefix="/api/alerts", tags=["Alerts"])

    # 静态文件服务（JS/CSS/图片等）
    static_dir = Path(FRONTEND_DIR) / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # 首页路由
    @app.get("/", include_in_schema=False)
    async def index():
        return FileResponse(Path(FRONTEND_DIR) / "index.html")

    # 子页面路由（views/*.html）
    @app.get("/views/{page_name}", include_in_schema=False)
    async def view_page(page_name: str):
        page_path = Path(FRONTEND_DIR) / "views" / page_name
        if page_path.exists():
            return FileResponse(page_path)
        from backend.api.serializers import not_found
        return not_found(f"页面 {page_name} 不存在")

    logger.info("FastAPI 应用创建完成")
    return app

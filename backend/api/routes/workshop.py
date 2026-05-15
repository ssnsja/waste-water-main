# -*- coding: utf-8 -*-
"""
车间管理 CRUD API 路由

- GET    /                   查询全部车间列表
- POST   /                   新增车间
- PUT    /{workshop_id}      更新车间信息
- PUT    /{workshop_id}/status  切换车间启用状态
- DELETE /{workshop_id}      逻辑删除车间
"""

from __future__ import annotations

from typing import Optional

import oracledb
from fastapi import APIRouter, Request
from pydantic import BaseModel, field_validator

from backend.api.serializers import (
    created,
    error,
    not_found,
    round2,
    serialize,
    server_error,
    success,
)
from backend.utils.exceptions import DBWriteError
from backend.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic 请求模型
# ---------------------------------------------------------------------------

class WorkshopCreateRequest(BaseModel):
    """新增车间请求体"""
    workshop_id: str
    workshop_name: str
    max_discharge_rate: float
    min_discharge_rate: float
    priority_weight: float = 1.0
    is_active: int = 1
    remark: str = ""

    @field_validator("max_discharge_rate")
    @classmethod
    def validate_max_rate(cls, v):
        if v is None or v <= 0:
            raise ValueError("最大排放速率必须大于0")
        return v

    @field_validator("min_discharge_rate")
    @classmethod
    def validate_min_rate(cls, v):
        if v is None or v < 0:
            raise ValueError("最小排放速率不能为负数")
        return v


class WorkshopUpdateRequest(BaseModel):
    """更新车间请求体"""
    workshop_name: Optional[str] = None
    max_discharge_rate: Optional[float] = None
    min_discharge_rate: Optional[float] = None
    priority_weight: Optional[float] = None
    is_active: Optional[int] = None
    remark: Optional[str] = None


class WorkshopStatusRequest(BaseModel):
    """切换车间启用状态请求体"""
    is_active: int


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _get_workshop_dao(request: Request):
    """从 app.state 获取 WorkshopDAO 实例"""
    trigger = request.app.state.trigger
    return trigger._scheduler_svc._workshop_dao


def _get_pool(request: Request) -> oracledb.ConnectionPool:
    """从 app.state 获取连接池"""
    return request.app.state.pool


# ---------------------------------------------------------------------------
# 路由端点
# ---------------------------------------------------------------------------

@router.get("")
def get_workshops(request: Request):
    """查询全部车间列表（含 is_active/remark/update_time）。"""
    try:
        workshop_dao = _get_workshop_dao(request)
        workshops = workshop_dao.get_all()

        data = []
        for ws in workshops:
            data.append({
                "workshop_id": ws.workshop_id,
                "workshop_name": ws.workshop_name,
                "max_discharge_rate": round2(ws.max_discharge_rate),
                "min_discharge_rate": round2(ws.min_discharge_rate),
                "priority_weight": round2(ws.priority_weight),
                "is_active": ws.is_active,
                "remark": ws.remark,
                "update_time": serialize(ws.update_time),
            })

        return success(data=data)

    except Exception as e:
        logger.error(f"查询车间列表失败: {e}", exc_info=True)
        return server_error(f"查询车间列表失败: {e}")


@router.post("")
def create_workshop(body: WorkshopCreateRequest, request: Request):
    """新增车间。"""
    try:
        workshop_dao = _get_workshop_dao(request)
        pool = _get_pool(request)

        # 校验速率范围
        if body.max_discharge_rate < body.min_discharge_rate:
            return error(
                status=400,
                message="速率范围非法：最大排放速率不能小于最小排放速率",
                http_status_code=400,
            )

        # 检查车间编号是否已存在
        existing = workshop_dao.get_by_id(body.workshop_id)
        if existing:
            return error(
                status=400,
                message=f"车间编号已存在: {body.workshop_id}",
                http_status_code=400,
            )

        from backend.model.workshop import Workshop
        workshop = Workshop(
            workshop_id=body.workshop_id,
            workshop_name=body.workshop_name,
            max_discharge_rate=body.max_discharge_rate,
            min_discharge_rate=body.min_discharge_rate,
            priority_weight=body.priority_weight,
            is_active=body.is_active,
            remark=body.remark,
        )

        conn = None
        try:
            conn = pool.acquire()
            conn.autocommit = False
            workshop_dao.insert(conn, workshop)
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                pool.release(conn)

        return created(
            data={"workshop_id": body.workshop_id},
            message="车间新增成功",
        )

    except DBWriteError as e:
        return server_error(f"车间新增失败: {e}")
    except Exception as e:
        logger.error(f"新增车间失败: {e}", exc_info=True)
        return server_error(f"新增车间失败: {e}")


@router.put("/{workshop_id}")
def update_workshop(workshop_id: str, body: WorkshopUpdateRequest, request: Request):
    """更新车间信息。"""
    try:
        workshop_dao = _get_workshop_dao(request)
        pool = _get_pool(request)

        # 检查车间是否存在
        existing = workshop_dao.get_by_id(workshop_id)
        if not existing:
            return not_found(f"车间 {workshop_id} 不存在")

        # 构建更新数据（仅包含非 None 的字段）
        data = {}
        if body.workshop_name is not None:
            data["workshop_name"] = body.workshop_name
        if body.max_discharge_rate is not None:
            data["max_discharge_rate"] = body.max_discharge_rate
        if body.min_discharge_rate is not None:
            data["min_discharge_rate"] = body.min_discharge_rate
        if body.priority_weight is not None:
            data["priority_weight"] = body.priority_weight
        if body.is_active is not None:
            data["is_active"] = body.is_active
        if body.remark is not None:
            data["remark"] = body.remark

        if not data:
            return success(message="无更新字段", data=None)

        # 速率范围校验
        max_rate = data.get("max_discharge_rate", existing.max_discharge_rate)
        min_rate = data.get("min_discharge_rate", existing.min_discharge_rate)
        if max_rate < min_rate:
            return error(
                status=400,
                message="速率范围非法：最大排放速率不能小于最小排放速率",
                http_status_code=400,
            )

        conn = None
        try:
            conn = pool.acquire()
            conn.autocommit = False
            workshop_dao.update(conn, workshop_id, data)
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                pool.release(conn)

        return success(message="车间信息更新成功", data=None)

    except DBWriteError as e:
        return server_error(f"更新车间失败: {e}")
    except Exception as e:
        logger.error(f"更新车间失败: {e}", exc_info=True)
        return server_error(f"更新车间失败: {e}")


@router.put("/{workshop_id}/status")
def update_workshop_status(workshop_id: str, body: WorkshopStatusRequest, request: Request):
    """切换车间启用状态。"""
    try:
        workshop_dao = _get_workshop_dao(request)
        pool = _get_pool(request)

        # 检查车间是否存在
        existing = workshop_dao.get_by_id(workshop_id)
        if not existing:
            return not_found(f"车间 {workshop_id} 不存在")

        conn = None
        try:
            conn = pool.acquire()
            conn.autocommit = False
            workshop_dao.update(conn, workshop_id, {"is_active": body.is_active})
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                pool.release(conn)

        return success(message="车间状态已更新", data=None)

    except DBWriteError as e:
        return server_error(f"更新车间状态失败: {e}")
    except Exception as e:
        logger.error(f"更新车间状态失败: {e}", exc_info=True)
        return server_error(f"更新车间状态失败: {e}")


@router.delete("/{workshop_id}")
def delete_workshop(workshop_id: str, request: Request):
    """逻辑删除车间（IS_ACTIVE=0）。"""
    try:
        workshop_dao = _get_workshop_dao(request)
        pool = _get_pool(request)

        # 检查车间是否存在
        existing = workshop_dao.get_by_id(workshop_id)
        if not existing:
            return not_found(f"车间 {workshop_id} 不存在")

        conn = None
        try:
            conn = pool.acquire()
            conn.autocommit = False
            workshop_dao.deactivate(conn, workshop_id)
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                pool.release(conn)

        return success(message="车间已停用", data=None)

    except DBWriteError as e:
        return server_error(f"删除车间失败: {e}")
    except Exception as e:
        logger.error(f"删除车间失败: {e}", exc_info=True)
        return server_error(f"删除车间失败: {e}")

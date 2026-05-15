# -*- coding: utf-8 -*-
"""
统一响应格式与数据序列化工具

提供：
- ApiResponse：统一 JSON 响应构建器
- 序列化辅助函数：dataclass/datetime → JSON 安全值
"""

from __future__ import annotations

from dataclasses import asdict, fields, is_dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

from fastapi.responses import JSONResponse


# ---------------------------------------------------------------------------
# 统一响应格式
# ---------------------------------------------------------------------------

class ApiResponse(JSONResponse):
    """统一 API 响应格式"""

    def __init__(
        self,
        status: int = 200,
        message: str = "success",
        data: Any = None,
        http_status_code: int = 200,
    ):
        body = {
            "status": status,
            "message": message,
            "data": data,
        }
        super().__init__(content=body, status_code=http_status_code)


def success(data: Any = None, message: str = "success") -> ApiResponse:
    """构建成功响应"""
    return ApiResponse(status=200, message=message, data=data, http_status_code=200)


def created(data: Any = None, message: str = "创建成功") -> ApiResponse:
    """构建创建成功响应"""
    return ApiResponse(status=201, message=message, data=data, http_status_code=201)


def error(
    status: int = 400,
    message: str = "请求错误",
    http_status_code: int = 400,
) -> ApiResponse:
    """构建错误响应"""
    return ApiResponse(
        status=status, message=message, data=None, http_status_code=http_status_code
    )


def not_found(message: str = "资源不存在") -> ApiResponse:
    """构建 404 响应"""
    return ApiResponse(status=404, message=message, data=None, http_status_code=404)


def server_error(message: str = "服务器内部错误") -> ApiResponse:
    """构建 500 响应"""
    return ApiResponse(status=500, message=message, data=None, http_status_code=500)


# ---------------------------------------------------------------------------
# 序列化辅助
# ---------------------------------------------------------------------------

def serialize(obj: Any) -> Any:
    """
    递归序列化 Python 对象为 JSON 安全值。

    - dataclass → dict（递归处理字段）
    - datetime  → ISO 8601 字符串
    - Decimal   → float
    - None      → None
    - list/tuple → 递归列表
    - dict      → 递归字典
    """
    if obj is None:
        return None
    if isinstance(obj, datetime):
        return obj.strftime("%Y-%m-%dT%H:%M:%S")
    if isinstance(obj, Decimal):
        return float(obj)
    if is_dataclass(obj) and not isinstance(obj, type):
        return serialize(asdict(obj))
    if isinstance(obj, (list, tuple)):
        return [serialize(item) for item in obj]
    if isinstance(obj, dict):
        return {k: serialize(v) for k, v in obj.items()}
    if isinstance(obj, (int, float, str, bool)):
        return obj
    # 兜底：尝试转为字符串
    return str(obj)


def round2(value: Optional[float]) -> Optional[float]:
    """保留2位小数，None 安全"""
    if value is None:
        return None
    return round(float(value), 2)


def alert_level_to_text(level: int) -> str:
    """告警级别 int → 字符串映射"""
    mapping = {2: "ALERT", 3: "EMERGENCY"}
    return mapping.get(level, "UNKNOWN")


def ratio_to_percent(ratio: Optional[float]) -> Optional[float]:
    """小数比例 → 百分比（保留1位小数），如 0.641 → 64.1"""
    if ratio is None:
        return None
    return round(float(ratio) * 100, 1)

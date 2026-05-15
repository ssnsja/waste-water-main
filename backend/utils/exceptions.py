# -*- coding: utf-8 -*-
"""
自定义异常模块

所有异常统一使用本模块定义的自定义异常。
"""


class SchedulerBaseError(Exception):
    """调度系统基础异常类"""

    pass


class ConfigLoadError(SchedulerBaseError):
    """配置加载异常"""

    pass


class DBQueryError(SchedulerBaseError):
    """数据库查询异常"""

    pass


class DBWriteError(SchedulerBaseError):
    """数据库写入异常"""

    pass


class InvalidTankLevelError(SchedulerBaseError):
    """储罐液位非法异常"""

    pass


class NoActiveWorkshopError(SchedulerBaseError):
    """无启用车间异常"""

    pass

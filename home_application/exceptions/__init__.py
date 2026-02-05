"""
统一的异常模块

提供所有业务异常的导入入口，简化导入语句
"""

# CMDB 模块异常
from .cmdb import (
    CmdbBaseException,
    CmdbExecutionError,
    CmdbParameterError,
)

# 异常处理器
from .exception_handler import custom_exception_handler

# Job 模块异常
from .job import (
    JobAPIError,
    JobBaseException,
    JobExecutionError,
    JobNetworkError,
    JobNotFoundError,
    JobParameterError,
    JobPermissionError,
    JobStatusError,
    JobTimeoutError,
)

__all__ = [
    # Job 异常
    "JobBaseException",
    "JobParameterError",
    "JobExecutionError",
    "JobTimeoutError",
    "JobStatusError",
    "JobNetworkError",
    "JobAPIError",
    "JobNotFoundError",
    "JobPermissionError",
    # CMDB 异常
    "CmdbBaseException",
    "CmdbParameterError",
    "CmdbExecutionError",
    # 异常处理器
    "custom_exception_handler",
]

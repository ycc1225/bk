"""
Job 模块异常定义

提供 Job 相关的业务异常类
"""

from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import APIException


class JobBaseException(APIException):
    """
    Job 模块基础异常

    支持传递额外的上下文信息，便于调试和日志记录
    """

    status_code = 400
    default_detail = _("Job execution error.")
    default_code = "job_error"

    def __init__(self, detail=None, code=None, **extra_context):
        """
        初始化异常
        Args:
            detail: 错误详情（字符串）
            code: 错误码
            **extra_context: 额外的上下文信息（如 job_id, operator, bk_biz_id 等）
        """
        super().__init__(detail, code)
        self.extra_context = extra_context

    def get_full_details(self):
        """
        获取完整的错误信息（包含上下文）

        Returns:
            dict: 包含 detail、code 和 context 的字典
        """
        return {
            "detail": str(self.detail),
            "code": self.get_codes(),
            "context": self.extra_context,
        }

    def __str__(self):
        """字符串表示，包含上下文信息"""
        if self.extra_context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.extra_context.items())
            return f"{self.detail} ({context_str})"
        return str(self.detail)

    @classmethod
    def from_exception(cls, message, original_exception, **extra_context):
        """
        从原始异常创建业务异常，保留异常链

        Args:
            message: 业务错误信息
            original_exception: 原始异常
            **extra_context: 额外上下文

        Returns:
            JobBaseException: 新的异常实例
        """
        exc = cls(message, **extra_context)
        exc.__cause__ = original_exception  # 保留异常链
        return exc


class JobParameterError(JobBaseException):
    """Job 参数校验异常"""

    status_code = 400
    default_detail = _("Invalid job parameters.")
    default_code = "job_param_error"


class JobExecutionError(JobBaseException):
    """Job 执行异常（通用执行错误）"""

    status_code = 500
    default_detail = _("Failed to execute job.")
    default_code = "job_execution_error"


class JobTimeoutError(JobBaseException):
    """Job 执行超时异常"""

    status_code = 504
    default_detail = _("Job execution timed out.")
    default_code = "job_timeout"


class JobStatusError(JobBaseException):
    """Job 状态异常"""

    status_code = 500
    default_detail = _("Unknown job status.")
    default_code = "job_status_error"


class JobNetworkError(JobBaseException):
    """Job API 网络异常（连接失败、超时等）"""

    status_code = 503
    default_detail = _("Failed to connect to Job API.")
    default_code = "job_network_error"


class JobAPIError(JobBaseException):
    """Job API 返回错误（API 调用成功但返回错误）"""

    status_code = 500
    default_detail = _("Job API returned an error.")
    default_code = "job_api_error"


class JobNotFoundError(JobBaseException):
    """作业不存在"""

    status_code = 404
    default_detail = _("Job not found.")
    default_code = "job_not_found"


class JobPermissionError(JobBaseException):
    """作业权限不足"""

    status_code = 403
    default_detail = _("Permission denied for job operation.")
    default_code = "job_permission_denied"

"""
CMDB 模块异常定义

提供 CMDB 相关的业务异常类
"""

from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import APIException


class CmdbBaseException(APIException):
    """
    CMDB 模块基础异常

    支持传递额外的上下文信息，便于调试和日志记录
    """

    status_code = 400
    default_detail = _("CMDB execution error.")
    default_code = "cmdb_error"

    def __init__(self, detail=None, code=None, **extra_context):
        """
        初始化异常

        Args:
            detail: 错误详情（字符串）
            code: 错误码
            **extra_context: 额外的上下文信息（如 bk_biz_id, bk_host_id 等）
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
            CmdbBaseException: 新的异常实例
        """
        exc = cls(message, **extra_context)
        exc.__cause__ = original_exception  # 保留异常链
        return exc


class CmdbParameterError(CmdbBaseException):
    """CMDB 参数校验异常"""

    status_code = 400
    default_detail = _("Invalid CMDB parameters.")
    default_code = "cmdb_param_error"


class CmdbExecutionError(CmdbBaseException):
    """CMDB 执行异常（调用 API 失败）"""

    status_code = 500
    default_detail = _("Failed to execute CMDB operation.")
    default_code = "cmdb_execution_error"

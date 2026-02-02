from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import APIException


class JobBaseException(APIException):
    """Job 模块基础异常"""

    status_code = 400
    default_detail = _("Job execution error.")
    default_code = "job_error"


class JobParameterError(JobBaseException):
    """Job 参数校验异常"""

    status_code = 400
    default_detail = _("Invalid job parameters.")
    default_code = "job_param_error"


class JobExecutionError(JobBaseException):
    """Job 执行异常（调用 API 失败）"""

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

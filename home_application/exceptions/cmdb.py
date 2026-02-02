from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import APIException


class CmdbBaseException(APIException):
    """CMDB 模块基础异常"""

    status_code = 400
    default_detail = _("CMDB execution error.")
    default_code = "cmdb_error"


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

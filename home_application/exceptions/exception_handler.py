"""
自定义异常处理器

提供统一的异常处理逻辑，返回标准的 JSON 格式
"""

import logging

from blueapps.utils import failed_data
from opentelemetry import trace
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    自定义异常处理器

    功能：
    1. 返回统一的 JSON 格式
    2. 记录结构化日志（包含 trace_id）
    3. 提取额外的上下文信息
    4. 支持异常链追踪

    Args:
        exc: 异常实例
        context: 请求上下文

    Returns:
        Response: DRF Response 对象
    """
    response = exception_handler(exc, context)

    if response is not None:
        # 获取当前 trace_id
        span = trace.get_current_span()
        span_context = span.get_span_context()
        trace_id = format(span_context.trace_id, "032x") if span_context.trace_id else "unknown"

        # 提取错误信息
        message = _extract_error_message(response.data)

        # 提取额外的上下文（如果异常支持）
        extra_context = {}
        if hasattr(exc, "extra_context"):
            extra_context = exc.extra_context

        # 获取请求信息
        request = context.get("request")
        request_path = request.path if request else None
        request_method = request.method if request else None

        # 记录结构化日志
        logger.error(
            "API exception occurred",
            extra={
                "trace_id": trace_id,
                "exception_type": exc.__class__.__name__,
                "exception_module": exc.__class__.__module__,
                "status_code": response.status_code,
                "error_message": message,
                "context": extra_context,
                "request_path": request_path,
                "request_method": request_method,
            },
            exc_info=True,  # 包含完整的异常堆栈
        )

        # 构造响应数据（只返回 trace_id，不暴露内部细节）
        response_data = {
            "trace_id": trace_id,
        }

        response.data = failed_data(
            message=str(message),
            code=response.status_code,
            data=response_data,
        )

    return response


def _extract_error_message(data):
    """
    提取错误信息

    Args:
        data: 异常数据（可能是 dict、list 或其他类型）

    Returns:
        str: 提取的错误信息
    """
    if isinstance(data, dict):
        if "detail" in data:
            return data["detail"]
        else:
            # 处理参数校验错误，将所有错误拼接
            errors = []
            for field, msgs in data.items():
                if isinstance(msgs, list):
                    errors.append(f"{field}: {'; '.join([str(m) for m in msgs])}")
                else:
                    errors.append(f"{field}: {str(msgs)}")
            return " | ".join(errors)
    elif isinstance(data, list):
        return "; ".join([str(x) for x in data])
    else:
        return str(data)

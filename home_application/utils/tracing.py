"""OpenTelemetry 追踪工具函数

提供轻量级的追踪工具，配合 Celery 自动埋点使用
"""

from typing import Any, TypeVar

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

T = TypeVar("T")


def add_trace_attrs(**kwargs: Any) -> None:
    """
    向当前 Span 添加属性（简化版）

    自动将下划线格式转换为点号格式：
    job_instance_id -> job.instance.id

    Example:
        add_trace_attrs(
            job_instance_id=123,
            job_bk_biz_id=456,
            job_step_status="running"
        )
    """
    span = trace.get_current_span()
    if span.is_recording():
        for key, value in kwargs.items():
            # 自动转换 key 格式：job_instance_id -> job.instance.id
            formatted_key = key.replace("_", ".")
            span.set_attribute(formatted_key, str(value))


def add_trace_event(name: str, **attrs: Any) -> None:
    """
    向当前 Span 添加事件

    Example:
        add_trace_event("job_still_running", retry_count=3)
        add_trace_event("job_processing_completed", final_status="success")
    """
    span = trace.get_current_span()
    if span.is_recording():
        span.add_event(name, attributes={k: str(v) for k, v in attrs.items()})


def mark_trace_error(error: Exception) -> None:
    """
    标记当前 Span 为错误状态

    自动记录异常信息和堆栈

    Example:
        try:
            do_something()
        except Exception as e:
            mark_trace_error(e)
            raise
    """
    span = trace.get_current_span()
    if span.is_recording():
        span.record_exception(error)
        span.set_status(Status(StatusCode.ERROR, str(error)))

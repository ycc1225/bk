"""
Prometheus 指标 Push 上报模块

采用 Push 模式主动将指标推送到蓝鲸监控平台的自定义指标端点。
通过自定义 handler 携带 X-BK-TOKEN 实现鉴权。

环境变量：
    BK_MONITOR_PUSH_ENDPOINT: 上报端点地址（如 10.0.32.5:4318）
    BK_MONITOR_PUSH_TOKEN: 自定义指标上报 Token
"""

import logging

from django.conf import settings
from prometheus_client import CollectorRegistry, Counter, Gauge, push_to_gateway
from prometheus_client.exposition import default_handler

logger = logging.getLogger(__name__)

# ===================== 上报配置 =====================
# 从 Django settings 读取（配置定义在 config/default.py 中）
PUSH_ENDPOINT = getattr(settings, "BK_MONITOR_PUSH_ENDPOINT", "")
PUSH_TOKEN = getattr(settings, "BK_MONITOR_PUSH_TOKEN", "")
PUSH_JOB_NAME = getattr(settings, "BK_MONITOR_PUSH_JOB", "job_backupend")

# ===================== 自定义 Handler =====================


def bk_handler(url, method, timeout, headers, data):
    """
    基于蓝鲸监控 Token 的上报 handler。
    在 default_handler 基础上注入 X-BK-TOKEN 请求头，用于平台鉴权。
    """

    def handle():
        headers.append(["X-BK-TOKEN", PUSH_TOKEN])
        default_handler(url, method, timeout, headers, data)()

    return handle


# ===================== 指标定义 =====================
# 使用独立的 CollectorRegistry，避免与默认 REGISTRY 冲突
registry = CollectorRegistry()

# --- 业务指标 ---
# API 请求总数（按方法和端点分组）
requests_total = Counter(
    "job_backupend_requests_total",
    "API 请求总数",
    ["method", "endpoint"],
    registry=registry,
)

# API 请求错误数
requests_errors_total = Counter(
    "job_backupend_requests_errors_total",
    "API 请求错误总数",
    ["method", "endpoint", "status_code"],
    registry=registry,
)

# Celery 任务执行计数
celery_tasks_total = Counter(
    "job_backupend_celery_tasks_total",
    "Celery 任务执行总数",
    ["task_name", "status"],
    registry=registry,
)

# JOB 执行任务状态
job_execution_status = Gauge(
    "job_backupend_job_execution_status",
    "JOB 平台任务最近执行状态（1=成功, 0=失败）",
    ["job_name"],
    registry=registry,
)

# CMDB 同步最后成功时间
cmdb_sync_last_success = Gauge(
    "job_backupend_cmdb_sync_last_success_timestamp",
    "CMDB 同步最后成功时间戳",
    ["sync_type"],
    registry=registry,
)

# 最后一次推送成功时间
push_last_success = Gauge(
    "job_backupend_push_last_success_timestamp",
    "指标推送最后成功时间戳",
    registry=registry,
)


# ===================== 推送函数 =====================


def push_metrics():
    """
    将 registry 中的所有指标推送到蓝鲸监控平台。

    Returns:
        bool: 推送成功返回 True，失败返回 False
    """
    if not PUSH_TOKEN:
        logger.warning("BK_MONITOR_PUSH_TOKEN 未配置，跳过指标推送")
        return False

    if not PUSH_ENDPOINT:
        logger.warning("BK_MONITOR_PUSH_ENDPOINT 未配置，跳过指标推送")
        return False

    try:
        push_to_gateway(
            gateway=PUSH_ENDPOINT,
            job=PUSH_JOB_NAME,
            registry=registry,
            handler=bk_handler,
        )
        push_last_success.set_to_current_time()
        logger.info(f"指标推送成功 -> {PUSH_ENDPOINT} (job={PUSH_JOB_NAME})")
        return True
    except Exception as e:
        logger.error(f"指标推送失败: {e}", exc_info=True)
        return False

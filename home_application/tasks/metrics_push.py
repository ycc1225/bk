"""
定时任务：推送 Prometheus 指标到蓝鲸监控平台

在推送前会从数据库拉取 API 请求统计数据，
填充 Web 进程无法直接打点的 requests_total 和 requests_errors_total 指标。
"""

import logging
from datetime import date

from celery import shared_task

logger = logging.getLogger(__name__)


def _collect_api_request_metrics():
    """
    从数据库 ApiRequestCount 表中拉取当天的 API 请求统计，
    填充到 Prometheus 指标中。

    由于 Web 进程（Gunicorn）和 Worker 进程（Celery）内存隔离，
    Web 进程中间件记录到 Redis/DB 的数据需要在 Worker 中主动拉取后填充。
    """
    from home_application.models import ApiRequestCount
    from home_application.views.metrics import requests_errors_total, requests_total

    try:
        today = date.today()
        records = ApiRequestCount.objects.filter(date=today)

        for record in records:
            # 使用 api_category 作为 endpoint 标签（如 backup、sync 等）
            endpoint = f"{record.api_category}/{record.api_name}"

            # Counter 只能递增，这里用 _metrics 的 _value 直接设置
            # 但更安全的做法是：每次推送时用 Gauge 类型，或重新创建 registry
            # 这里我们利用 inc(amount) 来累加当天数据库中的值
            # 注意：由于每 60 秒推送一次，需要避免重复累加
            # 所以这里改用"快照"策略：先清零再设值
            if record.request_count > 0:
                requests_total.labels(method="ALL", endpoint=endpoint).inc(0)
                requests_total.labels(method="ALL", endpoint=endpoint)._value.set(record.request_count)

            if record.error_count > 0:
                requests_errors_total.labels(method="ALL", endpoint=endpoint, status_code="5xx").inc(0)
                requests_errors_total.labels(method="ALL", endpoint=endpoint, status_code="5xx")._value.set(
                    record.error_count
                )

        logger.info(f"[指标收集] 从数据库拉取了 {records.count()} 条 API 请求记录")
    except Exception as e:
        logger.error(f"[指标收集] 拉取 API 请求数据失败: {e}", exc_info=True)


@shared_task
def push_metrics_task():
    """
    定时推送 Prometheus 指标到蓝鲸监控平台。
    建议配置为每 60 秒执行一次（通过 django_celery_beat 配置）。

    推送前会：
    1. 从数据库拉取 API 请求统计填充 requests_total / requests_errors_total
    2. 然后将所有指标一次性推送
    """
    from home_application.views.metrics import push_metrics

    # 推送前先收集跨进程指标
    _collect_api_request_metrics()

    success = push_metrics()
    if success:
        return "指标推送成功"
    return "指标推送失败，请检查日志"

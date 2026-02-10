"""
定时任务：推送 Prometheus 指标到蓝鲸监控平台
"""

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def push_metrics_task():
    """
    定时推送 Prometheus 指标到蓝鲸监控平台。
    建议配置为每 60 秒执行一次（通过 django_celery_beat 配置）。
    """
    from home_application.views.metrics import push_metrics

    success = push_metrics()
    if success:
        return "指标推送成功"
    return "指标推送失败，请检查日志"

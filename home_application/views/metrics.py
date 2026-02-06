"""
在 Django 中暴露 Prometheus 指标端点
"""

from django.http import HttpResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from rest_framework.views import APIView


class MetricsAPIView(APIView):
    """
    Prometheus 指标端点
    访问 /metrics 可以获取所有指标数据
    """

    def get(self, request):
        metrics_data = generate_latest()
        return HttpResponse(metrics_data, content_type=CONTENT_TYPE_LATEST)

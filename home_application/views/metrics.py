"""
在 Django 中暴露 Prometheus 指标端点
"""

from django.http import HttpResponse
from prometheus_client import Counter
from rest_framework.views import APIView

# 使用 prometheus_client 创建指标
requests_total_omg = Counter(
    "requests_total_omg", "Total number of HTTP requests", ["api_category", "api_name", "is_error"]  # 标签名称列表
)


class MetricsAPIView(APIView):
    """
    Prometheus 指标端点
    访问 /metrics 可以获取所有指标数据
    """

    def get(self, request):
        requests_total_omg.labels(method=request.method, endpoint=request.path).inc()
        return HttpResponse("custom_metrics")

"""
在 Django 中暴露 Prometheus 指标端点
"""

from blueapps.account.decorators import login_exempt
from django_prometheus import exports
from prometheus_client import Counter
from rest_framework.views import APIView

# 使用 prometheus_client 创建指标
requests_total_omg = Counter("requests_total_omg", "Total HTTP Requests", ["method", "endpoint"])


class MetricsAPIView(APIView):
    """
    Prometheus 指标端点
    访问 /metrics 可以获取所有指标数据
    """

    @login_exempt
    def get(self, request):
        requests_total_omg.labels(method=request.method, endpoint=request.path).inc()
        return exports.ExportToDjangoView(request)

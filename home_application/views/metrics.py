from blueapps.account.decorators import login_exempt
from django.http import HttpResponse
from django_prometheus import exports
from prometheus_client import Counter


@login_exempt
def metrics(request):
    return exports.ExportToDjangoView(request)


requests_total_omg = Counter("requests_total_omg", "Total HTTP Requests", ["method", "endpoint"])


def custom_metrics(request):
    # 在每次请求时增加计数
    requests_total_omg.labels(method=request.method, endpoint=request.path).inc()
    return HttpResponse("custom_metrics")

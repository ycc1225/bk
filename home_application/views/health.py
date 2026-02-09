from celery import current_app
from django.db import connection
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from home_application.utils.redis_utils import get_redis_client


class HealthCheckAPIView(APIView):
    """健康检查端点"""

    permission_classes = [AllowAny]
    authentication_classes = []  # 健康检查接口豁免认证

    def get(self, request):
        checks = {
            "database": self._check_database(),
            "redis": self._check_redis(),
            "celery": self._check_celery(),
        }

        is_healthy = all(checks.values())
        status_code = 200 if is_healthy else 503

        return Response(
            {
                "status": "healthy" if is_healthy else "unhealthy",
                "checks": checks,
            },
            status=status_code,
        )

    def _check_database(self):
        try:
            connection.ensure_connection()
            return True
        except Exception:
            return False

    def _check_redis(self):
        try:
            client = get_redis_client()
            return client.ping() if client else False
        except Exception:
            return False

    def _check_celery(self):
        # 检查 Celery worker 是否在线
        try:
            stats = current_app.control.inspect().stats()
            return bool(stats)
        except Exception:
            return False

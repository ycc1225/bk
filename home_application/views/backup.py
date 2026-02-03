from blueapps.utils import ok_data
from rest_framework.response import Response
from rest_framework.views import APIView

from home_application.models import BackupJob
from home_application.serializers import (
    BackupJobDetailSerializer,
    BackupJobListSerializer,
)


class BackupJobListAPIView(APIView):
    """备份作业列表API"""

    def get(self, request):
        """获取备份作业列表"""
        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", 10))
        start = (page - 1) * page_size

        total_count = BackupJob.objects.count()
        jobs = BackupJob.objects.all()[start : start + page_size]

        serializer = BackupJobListSerializer(jobs, many=True)
        res_data = {
            "result": True,
            "data": serializer.data,
            "pagination": {
                "count": total_count,
                "current": page,
                "page_size": page_size,
            },
        }
        return Response(res_data)


class BackupJobDetailAPIView(APIView):
    """备份作业详情API"""

    def get(self, request, pk):
        """获取备份作业详情"""
        job = BackupJob.objects.prefetch_related("records").get(id=pk)

        serializer = BackupJobDetailSerializer(job)
        return Response(ok_data(serializer.data))

from blueapps.utils import ok_data
from rest_framework.response import Response
from rest_framework.views import APIView

from home_application.exceptions.job import JobParameterError
from home_application.models import BackupJob
from home_application.permission import IsDevOrAbove
from home_application.serializers.job import (
    BackupJobDetailSerializer,
    BackupJobListSerializer,
    BackupJobQuerySerializer,
)


class BackupJobListAPIView(APIView):
    """备份作业列表API"""

    permission_classes = [IsDevOrAbove]

    def get(self, request):
        """获取备份作业列表，支持按状态、操作人、时间范围过滤"""
        # 使用序列化器校验查询参数
        query_serializer = BackupJobQuerySerializer(data=request.query_params)
        if not query_serializer.is_valid():
            raise JobParameterError(f"查询参数校验失败: {query_serializer.errors}")

        params = query_serializer.validated_data
        page = params.get("page", 1)
        page_size = params.get("page_size", 10)

        # 构建过滤条件
        queryset = BackupJob.objects.all()

        status = params.get("status")
        if status:
            queryset = queryset.filter(status=status)

        operator = params.get("operator")
        if operator:
            queryset = queryset.filter(operator=operator)

        created_at_start = params.get("created_at_start")
        if created_at_start:
            queryset = queryset.filter(created_at__gte=created_at_start)

        created_at_end = params.get("created_at_end")
        if created_at_end:
            queryset = queryset.filter(created_at__lte=created_at_end)

        # 分页
        total_count = queryset.count()
        start = (page - 1) * page_size
        jobs = queryset[start : start + page_size]

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

    permission_classes = [IsDevOrAbove]

    def get(self, request, pk):
        """获取备份作业详情"""
        job = BackupJob.objects.prefetch_related("records").get(id=pk)

        serializer = BackupJobDetailSerializer(job)
        return Response(ok_data(serializer.data))

from blueapps.utils import failed, ok_data
from rest_framework.response import Response
from rest_framework.views import APIView

from home_application.models import SyncStatus
from home_application.serializers.common import SyncStatusSerializer
from home_application.tasks.cmdb_sync import basic_sync_data_task, topo_sync_data_task


class BasicSyncAPIView(APIView):
    def get(self, request):
        token = request.COOKIES.get("bk_token")
        if not token:
            return Response(failed(message="未授权"))

        status, _ = SyncStatus.objects.get_or_create(name="basic_sync")

        # 检查是否正在运行且未超时
        if status.last_status == "running":
            return Response(failed(message="同步中，请稍后再试"))

        status.mark_running()
        try:
            basic_sync_data_task.delay(token)
        except Exception as e:
            status.mark_failed(f"任务启动失败: {str(e)}")
            return Response(failed(message="任务启动失败"))

        return Response(ok_data())


class TopoSyncAPIView(APIView):
    def get(self, request):
        token = request.COOKIES.get("bk_token")
        if not token:
            return Response(failed(message="未授权"))

        status, _ = SyncStatus.objects.get_or_create(name="topo_sync")

        if status.last_status == "running":
            return Response(failed(message="同步中，请稍后再试"))

        status.mark_running()
        try:
            topo_sync_data_task.delay(token)
        except Exception as e:
            status.mark_failed(f"任务启动失败: {str(e)}")
            return Response(failed(message="任务启动失败"))

        return Response(ok_data())


class SyncStatusAPIView(APIView):
    def get(self, request):
        instance = SyncStatus.objects.last()
        if instance:
            data = SyncStatusSerializer(instance).data
        else:
            data = {}
        return Response(ok_data(data=data))

from blueapps.utils import ok, ok_data, failed
from rest_framework.response import Response
from rest_framework.views import APIView

from home_application.models import SyncStatus
from home_application.serializers import SyncStatusSerializer
from home_application.tasks import basic_sync_data_task, topo_sync_data_task


class BasicSyncAPIView(APIView):
    def get(self, request):
        token = request.COOKIES.get("bk_token")
        if not token:
            return Response(failed(message="未授权"))
        basic_sync_data_task.delay(token)
        return Response(ok_data())

class TopoSyncAPIView(APIView):
    def get(self, request):
        token = request.COOKIES.get("bk_token")
        if not token:
            return Response(failed(message="未授权"))
        topo_sync_data_task.delay(token)
        return Response(ok_data())

class SyncStatusAPIView(APIView):
    def get(self, request):
        instance = SyncStatus.objects.last()
        if instance:
            data = SyncStatusSerializer(instance).data
        else:
            data = {}
        return Response(ok_data(data=data))
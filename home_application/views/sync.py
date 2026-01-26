from blueapps.utils import ok, ok_data, failed
from rest_framework.response import Response
from rest_framework.views import APIView

from home_application.models import SyncStatus
from home_application.tasks import basic_sync_data_task, topo_sync_data_task


class BasicSyncAPIView(APIView):
    def get(self, request):
        token = request.COOKIES.get("bk_token")
        if not token:
            return Response(failed(message="未获取到bk_token"))
        basic_sync_data_task.delay(token)
        return Response(ok_data())

class TopoSyncAPIView(APIView):
    def get(self, request):
        token = request.COOKIES.get("bk_token")
        if not token:
            return Response(failed(message="未获取到bk_token"))
        topo_sync_data_task.delay(token)
        return Response(ok_data())

class SyncStatusAPIView(APIView):
    def get(self, request):
        data = SyncStatus.objects.last()
        return Response(ok_data(data=data))
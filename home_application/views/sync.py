from rest_framework.response import Response
from rest_framework.views import APIView
from home_application.tasks import basic_sync_data_task, topo_sync_data_task


class BasicSyncAPIView(APIView):
    def get(self, request):
        basic_sync_data_task.delay()
        return Response({"msg": "sync triggered"})

class TopoSyncAPIView(APIView):
    def get(self, request):
        token = request.COOKIES.get("bk_token")
        if not token:
            return Response({"error": "bk_token is required"}, status=400)
        topo_sync_data_task.delay(token)
        return Response({"msg": "sync triggered"})
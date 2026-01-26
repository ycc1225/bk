from blueapps.utils import ok_data
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from home_application.models import ModuleInfo
from home_application.serializers import ModuleInfoSerializer


class ModuleInfoViewSet(ReadOnlyModelViewSet):
    serializer_class = ModuleInfoSerializer

    def get_queryset(self):
        params = self.request.query_params
        biz_id = params.get("bk_biz_id")
        set_id = params.get("bk_set_id")

        if not biz_id and not set_id:
            return ModuleInfo.objects.none()

        return ModuleInfo.objects.filter(bk_biz_id=biz_id,bk_set_id=set_id).order_by("bk_module_id")

    def list(self, request, *args, **kwargs):
        data = {
            "info": self.get_serializer(self.get_queryset(), many=True).data
        }
        return Response(ok_data(data))
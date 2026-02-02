from blueapps.utils import ok_data
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from home_application.exceptions.cmdb import CmdbParameterError
from home_application.models import SetInfo
from home_application.serializers import SetInfoSerializer


class SetInfoViewSet(ReadOnlyModelViewSet):
    serializer_class = SetInfoSerializer

    def get_queryset(self):
        biz_id = self.request.query_params.get("bk_biz_id")
        if not biz_id:
            raise CmdbParameterError("缺少 bk_biz_id 参数")
        return SetInfo.objects.filter(bk_biz_id=biz_id).order_by("bk_set_id")

    def list(self, request, *args, **kwargs):
        data = {"info": self.get_serializer(self.get_queryset(), many=True).data}
        return Response(ok_data(data))

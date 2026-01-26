from blueapps.utils import ok_data
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from home_application.models import BizInfo
from home_application.serializers import BizInfoSerializer


class BizInfoViewSet(ReadOnlyModelViewSet):
    serializer_class = BizInfoSerializer
    def get_queryset(self):
        return BizInfo.objects.all().order_by("bk_biz_id")
    def list(self, request, *args, **kwargs):
        data = {
            "info": self.get_serializer(self.get_queryset(), many=True).data
        }
        return Response(ok_data(data))
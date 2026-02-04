from blueapps.utils import ok_data
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from home_application.models import BizInfo
from home_application.serializers.cmdb import BizInfoSerializer


class BizInfoViewSet(ReadOnlyModelViewSet):
    """
    业务信息视图集

    返回所有业务列表，无需查询参数
    """

    serializer_class = BizInfoSerializer
    # 如果业务数量很多，可以启用分页：
    # pagination_class = PageNumberPagination

    def get_queryset(self):
        """返回所有业务信息，按业务ID排序"""
        return BizInfo.objects.all().order_by("bk_biz_id")

    def list(self, request, *args, **kwargs):
        """返回业务列表，包装为 {"info": [...]} 格式"""
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(ok_data(data={"info": serializer.data}))

from blueapps.utils import ok_data
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from home_application.exceptions.cmdb import CmdbParameterError
from home_application.models import SetInfo
from home_application.permission import IsDevOrAbove
from home_application.serializers.cmdb import SetInfoQuerySerializer, SetInfoSerializer


class SetInfoViewSet(ReadOnlyModelViewSet):
    """
    集群信息视图集

    查询参数：
        bk_biz_id (int, 必填): 业务ID
    """

    serializer_class = SetInfoSerializer
    permission_classes = [IsDevOrAbove]

    def get_queryset(self):
        """根据业务ID过滤集群信息"""
        # 使用序列化器进行参数校验
        query_serializer = SetInfoQuerySerializer(data=self.request.query_params)
        if not query_serializer.is_valid():
            raise CmdbParameterError(f"参数校验失败: {query_serializer.errors}")

        validated_data = query_serializer.validated_data

        return SetInfo.objects.filter(bk_biz_id=validated_data["bk_biz_id"]).order_by("bk_set_id")

    def list(self, request, *args, **kwargs):
        """返回集群列表，包装为 {"info": [...]} 格式"""
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(ok_data(data={"info": serializer.data}))

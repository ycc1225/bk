from blueapps.utils import ok_data
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from home_application.exceptions.cmdb import CmdbParameterError
from home_application.models import ModuleInfo
from home_application.serializers.cmdb import (
    ModuleInfoQuerySerializer,
    ModuleInfoSerializer,
)


class ModuleInfoViewSet(ReadOnlyModelViewSet):
    """
    模块信息视图集

    查询参数：
        bk_biz_id (int, 必填): 业务ID
        bk_set_id (int, 必填): 集群ID
    """

    serializer_class = ModuleInfoSerializer

    def get_queryset(self):
        """根据业务ID和集群ID过滤模块信息"""
        # 使用序列化器进行参数校验
        query_serializer = ModuleInfoQuerySerializer(data=self.request.query_params)
        if not query_serializer.is_valid():
            raise CmdbParameterError(f"参数校验失败: {query_serializer.errors}")

        validated_data = query_serializer.validated_data

        bk_biz_id = validated_data.get("bk_biz_id")
        bk_set_id = validated_data.get("bk_set_id")

        # 理论上序列化器已经校验了必填字段，但为了防御性编程，再次检查
        if bk_biz_id is None or bk_set_id is None:
            raise CmdbParameterError("缺少必需的参数: bk_biz_id 或 bk_set_id")

        return ModuleInfo.objects.filter(
            bk_biz_id=bk_biz_id,
            bk_set_id=bk_set_id,
        ).order_by("bk_module_id")

    def list(self, request, *args, **kwargs):
        """返回模块列表，包装为 {"info": [...]} 格式"""
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(ok_data(data={"info": serializer.data}))

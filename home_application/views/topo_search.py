from blueapps.utils import ok_data
from rest_framework.response import Response
from rest_framework.views import APIView

from home_application.exceptions.cmdb import CmdbParameterError
from home_application.models import BizInfo, ModuleInfo, SetInfo
from home_application.permission import IsDevOrAbove
from home_application.serializers.cmdb import TopoSearchQuerySerializer


class TopoSearchAPIView(APIView):
    """
    拓扑树模糊搜索接口

    GET /cmdb/topo-search/?keyword=xxx&page=1&page_size=10

    返回匹配的业务/集群/模块节点及其完整拓扑路径，按 业务 > 集群 > 模块 排序。
    """

    permission_classes = [IsDevOrAbove]

    def get(self, request):
        # 使用序列化器进行参数校验
        query_serializer = TopoSearchQuerySerializer(data=request.query_params)
        if not query_serializer.is_valid():
            raise CmdbParameterError(f"参数校验失败: {query_serializer.errors}")

        validated_data = query_serializer.validated_data
        keyword = validated_data["keyword"]
        page = validated_data["page"]
        page_size = validated_data["page_size"]

        # ---- 构建 id->name 映射，用于反查父路径 ----
        biz_map = {b.bk_biz_id: b.bk_biz_name for b in BizInfo.objects.all()}
        set_map = {s.bk_set_id: {"bk_set_name": s.bk_set_name, "bk_biz_id": s.bk_biz_id} for s in SetInfo.objects.all()}

        # ---- 三张表分别模糊搜索 ----
        matched_biz = BizInfo.objects.filter(bk_biz_name__icontains=keyword)
        matched_set = SetInfo.objects.filter(bk_set_name__icontains=keyword)
        matched_module = ModuleInfo.objects.filter(bk_module_name__icontains=keyword)

        # ---- 组装结果（业务 → 集群 → 模块 的顺序）----
        results = []

        for biz in matched_biz:
            results.append(
                {
                    "type": "biz",
                    "topo_path": biz.bk_biz_name,
                    "bk_biz_id": biz.bk_biz_id,
                    "bk_biz_name": biz.bk_biz_name,
                    "bk_set_id": None,
                    "bk_set_name": None,
                    "bk_module_id": None,
                    "bk_module_name": None,
                }
            )

        for s in matched_set:
            biz_name = biz_map.get(s.bk_biz_id, "未知业务")
            results.append(
                {
                    "type": "set",
                    "topo_path": f"{biz_name} / {s.bk_set_name}",
                    "bk_biz_id": s.bk_biz_id,
                    "bk_biz_name": biz_name,
                    "bk_set_id": s.bk_set_id,
                    "bk_set_name": s.bk_set_name,
                    "bk_module_id": None,
                    "bk_module_name": None,
                }
            )

        for m in matched_module:
            biz_name = biz_map.get(m.bk_biz_id, "未知业务")
            set_info = set_map.get(m.bk_set_id, {})
            set_name = set_info.get("bk_set_name", "未知集群")
            results.append(
                {
                    "type": "module",
                    "topo_path": f"{biz_name} / {set_name} / {m.bk_module_name}",
                    "bk_biz_id": m.bk_biz_id,
                    "bk_biz_name": biz_name,
                    "bk_set_id": m.bk_set_id,
                    "bk_set_name": set_name,
                    "bk_module_id": m.bk_module_id,
                    "bk_module_name": m.bk_module_name,
                }
            )

        # ---- 分页 ----
        total = len(results)
        start = (page - 1) * page_size
        end = start + page_size
        paginated = results[start:end]

        return Response(
            ok_data(
                data={
                    "results": paginated,
                    "total": total,
                    "page": page,
                    "page_size": page_size,
                }
            )
        )

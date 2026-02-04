from rest_framework.response import Response
from rest_framework.views import APIView

from blueking.component.shortcuts import get_client_by_request
from home_application.exceptions.cmdb import CmdbExecutionError, CmdbParameterError
from home_application.serializers.cmdb import HostListQuerySerializer


class HostListAPIView(APIView):
    """
    主机列表查询接口

    查询参数：
        bk_biz_id (int, 必填): 业务ID
        bk_set_id (int, 可选): 集群ID
        bk_module_id (int, 可选): 模块ID
        bk_host_id (int, 可选): 主机ID
        bk_host_innerip (str, 可选): 主机内网IP
        operator (str, 可选): 主机维护人
        page (int, 可选): 页码，默认1
        page_size (int, 可选): 每页数量，默认10，最大100
    """

    def get(self, request):
        """根据查询条件返回主机列表"""
        # 使用序列化器进行参数校验
        query_serializer = HostListQuerySerializer(data=request.query_params)
        if not query_serializer.is_valid():
            raise CmdbParameterError(f"参数校验失败: {query_serializer.errors}")

        validated_data = query_serializer.validated_data
        client = get_client_by_request(request)

        # 计算分页参数
        page = validated_data["page"]
        page_size = validated_data["page_size"]
        start = (page - 1) * page_size

        # 构造基础请求参数
        kwargs = {
            "bk_biz_id": validated_data["bk_biz_id"],
            "page": {
                "start": start,
                "limit": page_size,
            },
            "fields": [
                "bk_host_id",  # 主机ID
                "bk_host_innerip",  # 内网IP
                "operator",  # 主要维护人
                "bk_bak_operator",  # 备份维护人
            ],
        }

        # 添加可选的拓扑参数
        if "bk_set_id" in validated_data:
            kwargs["bk_set_ids"] = [validated_data["bk_set_id"]]

        if "bk_module_id" in validated_data:
            kwargs["bk_module_ids"] = [validated_data["bk_module_id"]]

        # 构造主机属性过滤规则
        rules = []
        if "operator" in validated_data:
            rules.append({"field": "operator", "operator": "contains", "value": validated_data["operator"]})
        if "bk_host_id" in validated_data:
            rules.append({"field": "bk_host_id", "operator": "equal", "value": validated_data["bk_host_id"]})
        if "bk_host_innerip" in validated_data:
            rules.append(
                {"field": "bk_host_innerip", "operator": "contains", "value": validated_data["bk_host_innerip"]}
            )

        # 添加过滤器
        if rules:
            kwargs["host_property_filter"] = {"condition": "AND", "rules": rules}

        # 调用 CMDB API
        result = client.cc.list_biz_hosts(kwargs)

        if not result.get("result"):
            raise CmdbExecutionError(result.get("message", "查询主机列表失败"))

        # 添加分页信息到返回数据
        data = result.get("data", {})
        data["pagination"] = {
            "current": page,
            "count": data.get("count", 0),
            "limit": page_size,
        }
        result["data"] = data

        return Response(result)


class HostDetailAPIView(APIView):
    """
    主机详情查询接口

    查询参数：
        bk_host_id (int, 必填): 主机ID
    """

    def get(self, request):
        """根据主机ID返回主机详情信息"""
        from home_application.serializers import HostDetailQuerySerializer

        # 使用序列化器进行参数校验
        query_serializer = HostDetailQuerySerializer(data=request.query_params)
        if not query_serializer.is_valid():
            raise CmdbParameterError(f"参数校验失败: {query_serializer.errors}")

        validated_data = query_serializer.validated_data
        client = get_client_by_request(request)

        kwargs = {
            "bk_host_id": validated_data["bk_host_id"],
        }

        result = client.cc.get_host_base_info(kwargs)
        if not result.get("result"):
            raise CmdbExecutionError(result.get("message", "查询主机详情失败"))

        return Response(result)

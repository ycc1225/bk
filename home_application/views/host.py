from rest_framework.response import Response
from rest_framework.views import APIView

from blueking.component.shortcuts import get_client_by_request


class HostListAPIView(APIView):
    def get(self, request):

        """
        根据传递的查询条件，包括但不限于（业务ID、集群ID、模块ID、主机ID、主机维护人）
        查询主机列表
        """
        client = get_client_by_request(request)

        # 获取分页参数，设置默认值
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 10))
        start = (page - 1) * page_size

        # 构造请求函数
        kwargs = {
            "bk_biz_id": request.GET.get('bk_biz_id'),
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

        # 添加可选参数，如集群ID、模块ID、主机ID...
        if request.GET.get("bk_set_id"):
            kwargs["bk_set_ids"] = [int(request.GET.get("bk_set_id"))]

        if request.GET.get("bk_module_id"):
            kwargs["bk_module_ids"] = [int(request.GET.get("bk_module_id"))]

        rules = []  # 额外的查询参数，配置查询规则，参数参考API文档
        if request.GET.get("operator"):
            rules.append({
                "field": "operator",
                "operator": "contains",
                "value": request.GET.get("operator")
            })
        if request.GET.get("bk_host_id"):
            rules.append({
                "field": "bk_host_id",
                "operator": "equal",
                "value": int(request.GET.get("bk_host_id"))
            })
        if request.GET.get("bk_host_innerip"):
            rules.append({
                "field": "bk_host_innerip",
                "operator": "contains",
                "value": request.GET.get("bk_host_innerip")
            })

        #  将额外的查询添加进过滤器中
        if rules:
            kwargs["host_property_filter"] = {
                "condition": "AND",
                "rules": rules
            }

        result = client.cc.list_biz_hosts(kwargs)

        # 在返回结果中添加分页信息
        if result.get("result"):
            data = result.get("data", {})
            # 计算总页数
            total_count = data.get("count", 0)

            # 添加分页信息到返回数据
            data["pagination"] = {
                "current": page,
                "count": total_count,
                "limit": page_size,
            }
            result["data"] = data

        return Response(result)

class HostDetailAPIView(APIView):
    def get(self,request):
        """
        根据主机ID，查询主机详情信息
        """
        client = get_client_by_request(request)

        kwargs = {
            "bk_host_id": request.GET.get("bk_host_id"),
        }

        result = client.cc.get_host_base_info(kwargs)
        return Response(result)

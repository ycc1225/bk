from rest_framework import serializers

from home_application.models import BizInfo, ModuleInfo, SetInfo


class BizInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = BizInfo
        fields = ["bk_biz_id", "bk_biz_name"]


class SetInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = SetInfo
        fields = ["bk_set_id", "bk_set_name", "bk_biz_id"]


class SetInfoQuerySerializer(serializers.Serializer):
    """集群信息查询参数序列化器"""

    bk_biz_id = serializers.IntegerField(required=True, min_value=1, help_text="业务ID")


class ModuleInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModuleInfo
        fields = ["bk_module_id", "bk_module_name", "bk_set_id", "bk_biz_id"]


class ModuleInfoQuerySerializer(serializers.Serializer):
    """模块信息查询参数序列化器"""

    bk_biz_id = serializers.IntegerField(required=True, min_value=1, help_text="业务ID")
    bk_set_id = serializers.IntegerField(required=True, min_value=1, help_text="集群ID")


class HostListQuerySerializer(serializers.Serializer):
    """主机列表查询参数序列化器"""

    bk_biz_id = serializers.IntegerField(required=True, min_value=1, help_text="业务ID")
    bk_set_id = serializers.IntegerField(required=False, min_value=1, help_text="集群ID")
    bk_module_id = serializers.IntegerField(required=False, min_value=1, help_text="模块ID")
    bk_host_id = serializers.IntegerField(required=False, min_value=1, help_text="主机ID")
    bk_host_innerip = serializers.CharField(required=False, max_length=50, help_text="主机内网IP")
    operator = serializers.CharField(required=False, max_length=50, help_text="主机维护人")
    page = serializers.IntegerField(required=False, default=1, min_value=1, help_text="页码")
    page_size = serializers.IntegerField(required=False, default=10, min_value=1, max_value=100, help_text="每页数量")

    def validate(self, attrs):
        """
        字段间依赖校验

        规则：如果提供了 bk_module_id，则必须同时提供 bk_set_id
        """
        bk_module_id = attrs.get("bk_module_id")
        bk_set_id = attrs.get("bk_set_id")

        if bk_module_id is not None and bk_set_id is None:
            raise serializers.ValidationError({"bk_set_id": "当提供 bk_module_id 时，必须同时提供 bk_set_id"})

        return attrs


class HostDetailQuerySerializer(serializers.Serializer):
    """主机详情查询参数序列化器"""

    bk_host_id = serializers.IntegerField(required=True, min_value=1, help_text="主机ID")


class TopoSearchQuerySerializer(serializers.Serializer):
    """拓扑树搜索查询参数序列化器"""

    keyword = serializers.CharField(required=True, min_length=2, max_length=100, help_text="搜索关键字，至少2个字符")
    page = serializers.IntegerField(required=False, default=1, min_value=1, help_text="页码")
    page_size = serializers.IntegerField(required=False, default=10, min_value=1, max_value=50, help_text="每页数量")

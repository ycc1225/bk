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


class HostDetailQuerySerializer(serializers.Serializer):
    """主机详情查询参数序列化器"""

    bk_host_id = serializers.IntegerField(required=True, min_value=1, help_text="主机ID")

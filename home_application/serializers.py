"""
DRF 序列化器定义
"""

from rest_framework import serializers

from .constants import MAX_FILE_COUNT, MAX_HOST_COUNT
from .models import (
    ApiRequestCount,
    BackupJob,
    BizInfo,
    ModuleInfo,
    SetInfo,
    SyncStatus,
)


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


class SearchFileSubmitSerializer(serializers.Serializer):
    """搜索文件提交序列化器"""

    search_path = serializers.CharField(required=True)
    suffix = serializers.CharField(required=True)
    host_list = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=True, min_length=1, max_length=100
    )

    def validate_suffix(self, value):
        """验证文件后缀是否合法"""
        from home_application.constants import ALLOW_FILE_SUFFIX

        if value not in ALLOW_FILE_SUFFIX:
            raise serializers.ValidationError(f"文件后缀不合法，允许的后缀：{', '.join(ALLOW_FILE_SUFFIX)}")
        return value

    def validate_search_path(self, value):
        """验证搜索路径是否合法"""
        from home_application.constants import ALLOW_PATH_PREFIX

        if not value.startswith(tuple(ALLOW_PATH_PREFIX)) or ".." in value:
            raise serializers.ValidationError("搜索路径不合法，不能包含 '..' 且必须以允许的路径前缀开头")
        return value


class BackupJobSubmitSerializer(serializers.Serializer):
    """备份作业提交序列化器"""

    search_path = serializers.CharField(required=True)
    suffix = serializers.CharField(required=True)
    backup_path = serializers.CharField(required=True)
    host_list = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=True, min_length=1, max_length=100
    )

    def validate_suffix(self, value):
        """验证文件后缀是否合法"""
        from home_application.constants import ALLOW_FILE_SUFFIX

        if value not in ALLOW_FILE_SUFFIX:
            raise serializers.ValidationError(f"文件后缀不合法，允许的后缀：{', '.join(ALLOW_FILE_SUFFIX)}")
        return value

    def validate_search_path(self, value):
        """验证搜索路径是否合法"""
        from home_application.constants import ALLOW_PATH_PREFIX

        if not value.startswith(tuple(ALLOW_PATH_PREFIX)) or ".." in value:
            raise serializers.ValidationError("搜索路径不合法，不能包含 '..' 且必须以允许的路径前缀开头")
        return value

    def validate_backup_path(self, value):
        """验证备份路径是否合法"""
        from home_application.constants import ALLOW_PATH_PREFIX

        if not value.startswith(tuple(ALLOW_PATH_PREFIX)) or ".." in value:
            raise serializers.ValidationError("备份路径不合法，不能包含 '..' 且必须以允许的路径前缀开头")
        return value


class BackupJobListSerializer(serializers.ModelSerializer):
    """备份作业列表序列化器"""

    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", read_only=True)

    class Meta:
        model = BackupJob
        fields = [
            "id",
            "job_instance_id",
            "operator",
            "search_path",
            "suffix",
            "backup_path",
            "bk_job_link",
            "status",
            "host_count",
            "file_count",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class BackupJobDetailSerializer(serializers.ModelSerializer):
    """备份作业详情序列化器"""

    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", read_only=True)
    host_files = serializers.SerializerMethodField()

    class Meta:
        model = BackupJob
        fields = [
            "id",
            "job_instance_id",
            "operator",
            "search_path",
            "suffix",
            "backup_path",
            "bk_job_link",
            "status",
            "host_count",
            "file_count",
            "created_at",
            "host_files",
        ]
        read_only_fields = ["id", "created_at"]

    def get_host_files(self, obj: BackupJob) -> dict:
        """按主机ID分组返回备份记录，利用查询结果有序性优化，最多MAX_HOST_COUNT个主机，单主机最多MAX_FILE_COUNT条"""
        from collections import defaultdict

        host_files = defaultdict(list)
        current_host = None
        host_count = 0

        for record in obj.records.all():
            host_id = record.bk_host_id

            # 新主机
            if host_id != current_host:
                # 主机数已达上限，由于有序，后续都是新主机，直接结束
                if host_count >= MAX_HOST_COUNT:
                    break
                current_host = host_id
                host_count += 1

            # 单主机记录限制
            if len(host_files[host_id]) < MAX_FILE_COUNT:
                host_files[host_id].append(
                    {
                        "file_path": record.bk_backup_name,
                        "status": record.status,
                    }
                )

        return dict(host_files)


class ApiRequestCountSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApiRequestCount
        fields = ["api_category", "api_name", "request_count"]


class SyncStatusSerializer(serializers.ModelSerializer):
    last_sync_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", read_only=True)

    class Meta:
        model = SyncStatus
        fields = ["name", "last_status", "last_sync_at", "last_error"]


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

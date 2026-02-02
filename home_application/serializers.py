"""
DRF 序列化器定义
"""

from rest_framework import serializers

from .models import (
    ApiRequestCount,
    BackupJob,
    BackupRecord,
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


class ModuleInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModuleInfo
        fields = ["bk_module_id", "bk_module_name", "bk_set_id", "bk_biz_id"]


class BackupRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = BackupRecord
        fields = ["id", "bk_host_id", "status", "bk_backup_name"]
        read_only_fields = ["id"]


class BackupJobSerializer(serializers.ModelSerializer):
    """备份作业序列化器"""

    records = BackupRecordSerializer(many=True, read_only=True)
    operator_name = serializers.CharField(source="operator", read_only=True)

    class Meta:
        model = BackupJob
        fields = [
            "id",
            "job_instance_id",
            "operator",
            "operator_name",
            "search_path",
            "suffix",
            "backup_path",
            "bk_job_link",
            "status",
            "host_count",
            "file_count",
            "created_at",
            "records",
        ]
        read_only_fields = ["id", "created_at"]


class BackupJobListSerializer(serializers.ModelSerializer):
    """备份作业列表序列化器（不包含records详情）"""

    operator_name = serializers.CharField(source="operator", read_only=True)

    class Meta:
        model = BackupJob
        fields = [
            "id",
            "job_instance_id",
            "operator",
            "operator_name",
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


class ApiRequestCountSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApiRequestCount
        fields = ["api_category", "api_name", "request_count"]


class SyncStatusSerializer(serializers.ModelSerializer):
    last_sync_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", read_only=True)

    class Meta:
        model = SyncStatus
        fields = ["name", "last_status", "last_sync_at", "last_error"]

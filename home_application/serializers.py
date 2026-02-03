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


class ModuleInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModuleInfo
        fields = ["bk_module_id", "bk_module_name", "bk_set_id", "bk_biz_id"]


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

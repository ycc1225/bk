from collections import defaultdict

from rest_framework import serializers

from home_application.constants import (
    ALLOW_FILE_SUFFIX,
    ALLOW_PATH_PREFIX,
    MAX_FILE_COUNT,
    MAX_HOST_COUNT,
)
from home_application.models import BackupJob


class SearchFileSubmitSerializer(serializers.Serializer):
    """搜索文件提交序列化器"""

    search_path = serializers.CharField(required=True)
    suffix = serializers.ChoiceField(
        choices=ALLOW_FILE_SUFFIX,
        error_messages={"invalid_choice": f"文件后缀不合法，允许的后缀：{','.join(ALLOW_FILE_SUFFIX)}"},
        required=True,
    )
    host_list = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=True, min_length=1, max_length=100
    )

    def validate_search_path(self, value):
        """验证搜索路径是否合法"""

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
        if value not in ALLOW_FILE_SUFFIX:
            raise serializers.ValidationError(f"文件后缀不合法，允许的后缀：{', '.join(ALLOW_FILE_SUFFIX)}")
        return value

    def validate_search_path(self, value):
        """验证搜索路径是否合法"""
        if not value.startswith(tuple(ALLOW_PATH_PREFIX)) or ".." in value:
            raise serializers.ValidationError("搜索路径不合法，不能包含 '..' 且必须以允许的路径前缀开头")
        return value

    def validate_backup_path(self, value):
        """验证备份路径是否合法"""
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
    diagnosis = serializers.SerializerMethodField()

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
            "diagnosis",
        ]
        read_only_fields = ["id", "created_at"]

    def get_diagnosis(self, obj: BackupJob) -> dict | None:
        """返回诊断结果（仅失败/部分成功的作业有值）"""
        try:
            diag = obj.diagnosis
            return {
                "top_category": diag.top_category,
                "top_category_display": diag.get_top_category_display(),
                "summary": diag.summary,
                "suggestion": diag.suggestion,
                "detail": diag.detail,
                "created_at": diag.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            }
        except Exception:
            return None

    def get_host_files(self, obj: BackupJob) -> dict:
        """按主机ID分组返回备份记录，利用查询结果有序性优化，最多MAX_HOST_COUNT个主机，单主机最多MAX_FILE_COUNT条"""
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


class BackupJobQuerySerializer(serializers.Serializer):
    """备份作业列表查询参数序列化器"""

    status = serializers.ChoiceField(
        choices=BackupJob.Status.CHOICES,
        required=False,
        allow_blank=True,
        error_messages={"invalid_choice": "无效的状态值，可选值：pending, processing, success, failed, partial"},
    )
    operator = serializers.CharField(required=False, allow_blank=True, max_length=255)
    created_at_start = serializers.DateTimeField(
        required=False,
        input_formats=["%Y-%m-%d %H:%M:%S", "%Y-%m-%d"],
        help_text="起始时间，格式：YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS",
    )
    created_at_end = serializers.DateTimeField(
        required=False,
        input_formats=["%Y-%m-%d %H:%M:%S", "%Y-%m-%d"],
        help_text="结束时间，格式：YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS",
    )
    page = serializers.IntegerField(required=False, default=1, min_value=1)
    page_size = serializers.IntegerField(required=False, default=10, min_value=1, max_value=100)

    def validate(self, attrs):
        """校验时间范围逻辑"""
        start = attrs.get("created_at_start")
        end = attrs.get("created_at_end")
        if start and end and start > end:
            raise serializers.ValidationError({"created_at_end": "结束时间不能早于起始时间"})
        return attrs

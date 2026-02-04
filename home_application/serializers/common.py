from rest_framework import serializers

from home_application.models import ApiRequestCount, SyncStatus


class ApiRequestCountSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApiRequestCount
        fields = ["api_category", "api_name", "request_count"]


class SyncStatusSerializer(serializers.ModelSerializer):
    last_sync_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", read_only=True)

    class Meta:
        model = SyncStatus
        fields = ["name", "last_status", "last_sync_at", "last_error"]

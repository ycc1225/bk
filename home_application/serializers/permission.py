from rest_framework import serializers

from home_application.constants import ROLE_CHOICES, VALID_ROLES
from home_application.models import UserRole


class UserRoleSerializer(serializers.ModelSerializer):
    """用户角色序列化器 - 用于列表展示和读取"""

    role_display = serializers.CharField(source="get_role_display", read_only=True)

    class Meta:
        model = UserRole
        fields = ("id", "username", "role", "role_display", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


class UserRoleCreateUpdateSerializer(serializers.Serializer):
    """用户角色创建/更新序列化器"""

    username = serializers.CharField(
        max_length=128,
        help_text="用户名",
        error_messages={
            "required": "用户名不能为空",
            "blank": "用户名不能为空",
        },
    )
    role = serializers.ChoiceField(
        choices=ROLE_CHOICES,
        help_text="角色（admin/ops/dev/bot）",
        error_messages={
            "required": "角色不能为空",
            "invalid_choice": f"无效的角色值，有效值为：{', '.join(VALID_ROLES)}",
        },
    )

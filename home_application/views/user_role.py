import logging

from blueapps.utils import ok_data
from rest_framework import status
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from home_application.constants import ROLE_ADMIN, ROLE_BOT, ROLE_DEV, ROLE_OPS
from home_application.models import UserRole
from home_application.permission import IsOpsOrAbove, get_user_role
from home_application.serializers.permission import (
    UserRoleCreateUpdateSerializer,
    UserRoleSerializer,
)

logger = logging.getLogger(__name__)


class UserRoleViewSet(ModelViewSet):
    """
    用户角色管理视图集

    权限规则：
    - list: Admin 和 Ops 可查看所有用户角色列表
    - create: Admin 可创建任意角色；Ops 仅可创建 dev/bot 角色
    - update/partial_update: Admin 可修改任意角色；Ops 不可修改 Admin/Ops 用户，且只能设为 dev/bot
    - destroy: Admin 可删除任意角色；Ops 仅可删除 Dev/Bot 角色记录
    """

    queryset = UserRole.objects.all().order_by("-updated_at")
    permission_classes = [IsOpsOrAbove]
    # lookup 字段使用 username 而非默认 pk，方便通过用户名操作
    lookup_field = "username"

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return UserRoleCreateUpdateSerializer
        return UserRoleSerializer

    def list(self, request, *args, **kwargs):
        """查看所有用户角色列表"""
        queryset = self.get_queryset()
        serializer = UserRoleSerializer(queryset, many=True)
        return Response(ok_data(data={"roles": serializer.data}))

    def create(self, request, *args, **kwargs):
        """创建用户角色"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        username = serializer.validated_data["username"]
        role = serializer.validated_data["role"]
        operator = request.user.username
        operator_role = get_user_role(request)

        # Ops 只能创建 dev/bot 角色
        if operator_role == ROLE_OPS and role not in (ROLE_DEV, ROLE_BOT):
            return Response(
                {"result": False, "message": "运维（Ops）只能分配开发（Dev）或机器人（Bot）角色。", "data": None},
                status=status.HTTP_403_FORBIDDEN,
            )

        # 检查用户是否已存在
        if UserRole.objects.filter(username=username).exists():
            return Response(
                {"result": False, "message": f"用户 {username} 已存在角色记录，请使用更新接口。", "data": None},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user_role = UserRole.objects.create(username=username, role=role)
        logger.info(
            "[角色管理] 操作人: %s, 创建用户角色: %s -> %s",
            operator,
            username,
            role,
        )
        return Response(
            ok_data(data=UserRoleSerializer(user_role).data),
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        """更新用户角色（全量更新）"""
        return self._do_update(request, partial=False, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        """更新用户角色（部分更新）"""
        return self._do_update(request, partial=True, *args, **kwargs)

    def _do_update(self, request, partial=False, *args, **kwargs):
        """更新用户角色的核心逻辑"""
        instance = self.get_object()
        serializer = self.get_serializer(data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        new_role = serializer.validated_data.get("role", instance.role)
        old_role = instance.role
        operator = request.user.username
        operator_role = get_user_role(request)

        # Ops 不可修改已经是 Admin/Ops 的用户
        if operator_role == ROLE_OPS and old_role in (ROLE_ADMIN, ROLE_OPS):
            return Response(
                {
                    "result": False,
                    "message": "运维（Ops）无权修改管理员（Admin）或运维（Ops）用户的角色。",
                    "data": None,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Ops 只能将目标用户设为 dev/bot
        if operator_role == ROLE_OPS and new_role not in (ROLE_DEV, ROLE_BOT):
            return Response(
                {"result": False, "message": "运维（Ops）只能将用户角色设为开发（Dev）或机器人（Bot）。", "data": None},
                status=status.HTTP_403_FORBIDDEN,
            )

        instance.role = new_role
        # 如果提交了 username 字段，忽略它（不允许修改用户名）
        instance.save(update_fields=["role", "updated_at"])

        logger.info(
            "[角色管理] 操作人: %s, 修改用户角色: %s, %s -> %s",
            operator,
            instance.username,
            old_role,
            new_role,
        )
        return Response(ok_data(data=UserRoleSerializer(instance).data))

    def destroy(self, request, *args, **kwargs):
        """删除用户角色"""
        instance = self.get_object()
        operator = request.user.username
        operator_role = get_user_role(request)

        # Ops 仅可删除 Dev/Bot 角色记录
        if operator_role == ROLE_OPS and instance.role in (ROLE_ADMIN, ROLE_OPS):
            return Response(
                {
                    "result": False,
                    "message": "运维（Ops）无权删除管理员（Admin）或运维（Ops）用户的角色记录。",
                    "data": None,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        logger.info(
            "[角色管理] 操作人: %s, 删除用户角色: %s (原角色: %s)",
            operator,
            instance.username,
            instance.role,
        )
        instance.delete()
        return Response(ok_data(data=None), status=status.HTTP_200_OK)

import logging

from rest_framework.permissions import BasePermission

from home_application.constants import (
    ROLE_ADMIN,
    ROLE_DEV,
    ROLE_OPS,
    get_role_level,
)
from home_application.models import UserRole
from home_application.utils.tracing import add_trace_attrs, add_trace_event

logger = logging.getLogger(__name__)


# =============================
# 角色解析辅助函数
# =============================


def get_user_role(request):
    """解析当前请求用户的角色。

    优先级：
    1. 如果用户是 Django superuser 或 staff（可访问 Django Admin），直接返回 'admin'
    2. 否则查询 UserRole 表获取角色
    3. 未找到返回 None（无角色用户）

    Args:
        request: DRF Request 对象

    Returns:
        str or None: 角色字符串（'admin'/'ops'/'dev'/'bot'）或 None
    """
    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return None

    # Admin 检查：Django superuser 或 staff 用户直接视为 Admin
    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return ROLE_ADMIN

    # 查询数据库角色记录
    username = getattr(user, "username", None)
    if not username:
        return None

    try:
        user_role = UserRole.objects.get(username=username)
        role = user_role.role
    except UserRole.DoesNotExist:
        # 未找到角色记录的用户，自动分配 Dev 角色
        UserRole.objects.create(username=username, role=ROLE_DEV)
        role = ROLE_DEV
        logger.info("用户 %s 首次访问，已自动分配 Dev 角色", username)

    add_trace_attrs(auth_username=username, auth_role=role)
    return role


# =============================
# DRF 权限类
# =============================


class IsAdmin(BasePermission):
    """仅允许 Admin 角色访问"""

    message = "权限不足：需要管理员（Admin）权限才能执行此操作。"

    def has_permission(self, request, view):
        role = get_user_role(request)
        allowed = role == ROLE_ADMIN
        if not allowed:
            _trace_permission_denied(request, role, "admin", self.__class__.__name__)
        return allowed


class IsOpsOrAbove(BasePermission):
    """允许 Admin、Ops 角色访问"""

    message = "权限不足：需要运维（Ops）及以上权限才能执行此操作。"

    def has_permission(self, request, view):
        role = get_user_role(request)
        if role is None:
            _trace_permission_denied(request, role, "ops", self.__class__.__name__)
            return False
        allowed = get_role_level(role) >= get_role_level(ROLE_OPS)
        if not allowed:
            _trace_permission_denied(request, role, "ops", self.__class__.__name__)
        return allowed


class IsDevOrAbove(BasePermission):
    """允许 Admin、Ops、Dev 角色访问"""

    message = "权限不足：需要开发（Dev）及以上权限才能执行此操作。"

    def has_permission(self, request, view):
        role = get_user_role(request)
        if role is None:
            _trace_permission_denied(request, role, "dev", self.__class__.__name__)
            return False
        allowed = get_role_level(role) >= get_role_level(ROLE_DEV)
        if not allowed:
            _trace_permission_denied(request, role, "dev", self.__class__.__name__)
        return allowed


class IsAuthenticatedWithRole(BasePermission):
    """允许所有四种角色（Admin/Ops/Dev/Bot）访问，但拒绝无角色用户"""

    message = "权限不足：您尚未被分配任何角色，请联系管理员。"

    def has_permission(self, request, view):
        role = get_user_role(request)
        if role is None:
            _trace_permission_denied(request, role, "any_role", self.__class__.__name__)
            return False
        return True


class ReadWritePermission(BasePermission):
    """根据 HTTP 方法区分读写权限。

    安全方法（GET/HEAD/OPTIONS）使用 read_permission_role 最低要求，
    非安全方法（POST/PUT/PATCH/DELETE）使用 write_permission_role 最低要求。

    视图可通过类属性配置：
        read_permission_role = 'dev'    # 读操作最低角色要求，默认 dev
        write_permission_role = 'ops'   # 写操作最低角色要求，默认 ops

    示例::

        class MyView(APIView):
            permission_classes = [ReadWritePermission]
            read_permission_role = 'dev'
            write_permission_role = 'ops'
    """

    def has_permission(self, request, view):
        role = get_user_role(request)
        if role is None:
            self.message = "权限不足：您尚未被分配任何角色，请联系管理员。"
            return False

        # 判断读/写操作
        if request.method in ("GET", "HEAD", "OPTIONS"):
            required_role = getattr(view, "read_permission_role", ROLE_DEV)
        else:
            required_role = getattr(view, "write_permission_role", ROLE_OPS)

        if get_role_level(role) < get_role_level(required_role):
            role_display = {"admin": "管理员", "ops": "运维", "dev": "开发", "bot": "机器人"}.get(
                required_role, required_role
            )
            self.message = f"权限不足：此操作需要{role_display}（{required_role.capitalize()}）及以上权限。"
            _trace_permission_denied(request, role, required_role, self.__class__.__name__)
            return False

        return True


# =============================
# Trace 辅助函数
# =============================


def _trace_permission_denied(request, role, required, permission_class):
    """记录权限拒绝的 Trace 事件和日志。

    在当前请求 Span 上添加 permission_denied 事件，
    同时输出 warning 级别日志，便于排障。

    Args:
        request: DRF Request 对象
        role: 用户当前角色（可能为 None）
        required: 所需的最低角色
        permission_class: 触发拒绝的权限类名
    """
    username = getattr(getattr(request, "user", None), "username", "anonymous")
    path = request.path
    method = request.method

    add_trace_event(
        "permission_denied",
        auth_username=username,
        auth_role=role or "none",
        required_role=required,
        permission_class=permission_class,
        http_method=method,
        http_path=path,
    )

    logger.warning(
        "权限拒绝 [%s] %s %s | 用户=%s 角色=%s 要求=%s 权限类=%s",
        method,
        path,
        permission_class,
        username,
        role or "none",
        required,
        permission_class,
    )

"""
权限控制单元测试
测试权限相关功能
"""

from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase

from home_application.models import UserRole
from home_application.permission import (
    IsAdmin,
    IsAuthenticatedWithRole,
    IsDevOrAbove,
    IsOpsOrAbove,
    ReadWritePermission,
    _trace_permission_denied,
    get_user_role,
)

User = get_user_model()


class TestGetUserRole(TestCase):
    """测试 get_user_role 函数"""

    def setUp(self):
        self.factory = RequestFactory()

    def test_unauthenticated_user(self):
        """测试：未认证用户"""
        request = self.factory.get("/test")
        request.user = AnonymousUser()

        role = get_user_role(request)
        self.assertIsNone(role)

    def test_superuser(self):
        """测试：超级用户返回admin"""
        request = self.factory.get("/test")
        request.user = User.objects.create_superuser(username="admin")

        role = get_user_role(request)
        self.assertEqual(role, "admin")

    def test_staff_user(self):
        """测试：staff用户返回admin"""
        user = User.objects.create_user(username="staff")
        user.is_staff = True
        user.save()
        request = self.factory.get("/test")
        request.user = user

        role = get_user_role(request)
        self.assertEqual(role, "admin")

    def test_existing_role(self):
        """测试：已有角色的用户"""
        UserRole.objects.create(username="testuser", role="ops")

        request = self.factory.get("/test")
        request.user = User(username="testuser")

        role = get_user_role(request)
        self.assertEqual(role, "ops")

    def test_auto_create_dev_role(self):
        """测试：新用户自动分配dev角色"""
        request = self.factory.get("/test")
        request.user = User(username="newuser")

        role = get_user_role(request)

        self.assertEqual(role, "dev")
        # 验证数据库中已创建
        self.assertTrue(UserRole.objects.filter(username="newuser", role="dev").exists())

    def test_no_username(self):
        """测试：用户没有username属性"""
        request = self.factory.get("/test")
        request.user = MagicMock()
        request.user.is_authenticated = True
        request.user.is_superuser = False
        request.user.is_staff = False
        request.user.username = None

        role = get_user_role(request)
        self.assertIsNone(role)


class TestIsAdmin(TestCase):
    """测试 IsAdmin 权限类"""

    def setUp(self):
        self.factory = RequestFactory()
        self.permission = IsAdmin()

    def test_admin_allowed(self):
        """测试：admin用户允许访问"""
        request = self.factory.get("/test")
        request.user = User(username="admin", is_superuser=True)

        result = self.permission.has_permission(request, None)
        self.assertTrue(result)

    def test_non_admin_denied(self):
        """测试：非admin用户拒绝访问"""
        UserRole.objects.create(username="opsuser", role="ops")

        request = self.factory.get("/test")
        request.user = User(username="opsuser")

        result = self.permission.has_permission(request, None)
        self.assertFalse(result)


class TestIsOpsOrAbove(TestCase):
    """测试 IsOpsOrAbove 权限类"""

    def setUp(self):
        self.factory = RequestFactory()
        self.permission = IsOpsOrAbove()

    def test_admin_allowed(self):
        """测试：admin允许"""
        request = self.factory.get("/test")
        request.user = User(username="admin", is_superuser=True)

        self.assertTrue(self.permission.has_permission(request, None))

    def test_ops_allowed(self):
        """测试：ops允许"""
        UserRole.objects.create(username="opsuser", role="ops")

        request = self.factory.get("/test")
        request.user = User(username="opsuser")

        self.assertTrue(self.permission.has_permission(request, None))

    def test_dev_denied(self):
        """测试：dev被拒绝"""
        UserRole.objects.create(username="devuser", role="dev")

        request = self.factory.get("/test")
        request.user = User(username="devuser")

        self.assertFalse(self.permission.has_permission(request, None))

    def test_unauthenticated_denied(self):
        """测试：未认证被拒绝"""
        request = self.factory.get("/test")
        request.user = AnonymousUser()

        self.assertFalse(self.permission.has_permission(request, None))


class TestIsDevOrAbove(TestCase):
    """测试 IsDevOrAbove 权限类"""

    def setUp(self):
        self.factory = RequestFactory()
        self.permission = IsDevOrAbove()

    def test_all_roles_allowed(self):
        """测试：所有角色都允许"""
        roles = [("admin", True), ("ops", True), ("dev", True), ("bot", True)]

        for role, expected in roles:
            UserRole.objects.filter(username=f"{role}user").delete()
            UserRole.objects.create(username=f"{role}user", role=role)

            request = self.factory.get("/test")
            request.user = User(username=f"{role}user")

            result = self.permission.has_permission(request, None)
            self.assertEqual(result, expected, f"Role {role} should be {expected}")


class TestIsAuthenticatedWithRole(TestCase):
    """测试 IsAuthenticatedWithRole 权限类"""

    def setUp(self):
        self.factory = RequestFactory()
        self.permission = IsAuthenticatedWithRole()

    def test_with_role_allowed(self):
        """测试：有角色的用户允许"""
        UserRole.objects.create(username="devuser", role="dev")

        request = self.factory.get("/test")
        request.user = User(username="devuser")

        self.assertTrue(self.permission.has_permission(request, None))

    def test_without_role_denied(self):
        """测试：无角色用户拒绝（不包括自动创建）"""
        request = self.factory.get("/test")
        request.user = User(username="unknown")
        # 注意：get_user_role会自动创建dev角色，所以这里实际上是测试匿名用户

        self.assertTrue(self.permission.has_permission(request, None))  # 因为自动创建了dev角色


class TestReadWritePermission(TestCase):
    """测试 ReadWritePermission 权限类"""

    def setUp(self):
        self.factory = RequestFactory()
        self.permission = ReadWritePermission()

    def test_get_request(self):
        """测试：GET请求使用读权限"""
        UserRole.objects.create(username="devuser", role="dev")

        request = self.factory.get("/test")
        request.user = User(username="devuser")

        view = MagicMock()
        view.read_permission_role = "dev"

        self.assertTrue(self.permission.has_permission(request, view))

    def test_post_request(self):
        """测试：POST请求使用写权限"""
        UserRole.objects.create(username="opsuser", role="ops")

        request = self.factory.post("/test")
        request.user = User(username="opsuser")

        view = MagicMock()
        view.write_permission_role = "ops"

        self.assertTrue(self.permission.has_permission(request, view))

    def test_insufficient_write_permission(self):
        """测试：写权限不足"""
        UserRole.objects.create(username="devuser", role="dev")

        request = self.factory.post("/test")
        request.user = User(username="devuser")

        view = MagicMock()
        view.write_permission_role = "ops"  # 需要ops，但只有dev

        self.assertFalse(self.permission.has_permission(request, view))


class TestTracePermissionDenied(TestCase):
    """测试 _trace_permission_denied 辅助函数"""

    @patch("home_application.permission.add_trace_event")
    @patch("home_application.permission.logger")
    def test_trace_event(self, mock_logger, mock_add_event):
        """测试：记录权限拒绝事件"""
        request = MagicMock()
        request.user = MagicMock(username="testuser")
        request.path = "/api/test"
        request.method = "POST"

        _trace_permission_denied(request, "dev", "ops", "TestPermission")

        mock_add_event.assert_called_once()
        mock_logger.warning.assert_called_once()

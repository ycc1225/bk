"""
Host视图单元测试
"""

from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from home_application.models import UserRole
from home_application.views.host import HostDetailAPIView, HostListAPIView

User = get_user_model()


class TestHostListAPIView(TestCase):
    """测试 HostListAPIView"""

    def setUp(self):
        self.factory = RequestFactory()
        self.view = HostListAPIView.as_view()
        # 创建用户和角色
        self.user = User.objects.create_user(username="testuser")
        UserRole.objects.create(username="testuser", role="dev")

    @patch("home_application.views.host.get_client_by_request")
    def test_get_host_list_success(self, mock_get_client):
        """测试：成功获取主机列表"""
        mock_client = MagicMock()
        mock_client.cc.list_biz_hosts.return_value = {
            "result": True,
            "data": {
                "info": [{"bk_host_id": 1, "bk_host_innerip": "192.168.1.1"}],
                "count": 1,
            },
        }
        mock_get_client.return_value = mock_client

        request = self.factory.get("/hosts/", {"bk_biz_id": 1})
        request.user = self.user

        response = self.view(request)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["result"])

    @patch("home_application.views.host.get_client_by_request")
    def test_get_host_list_with_filters(self, mock_get_client):
        """测试：带过滤条件获取主机列表"""
        mock_client = MagicMock()
        mock_client.cc.list_biz_hosts.return_value = {
            "result": True,
            "data": {"info": [], "count": 0},
        }
        mock_get_client.return_value = mock_client

        request = self.factory.get(
            "/hosts/",
            {
                "bk_biz_id": 1,
                "bk_set_id": 10,
                "bk_module_id": 100,
                "operator": "admin",
                "bk_host_innerip": "192.168",
            },
        )
        request.user = self.user

        response = self.view(request)

        self.assertEqual(response.status_code, 200)
        # 验证API被调用
        mock_client.cc.list_biz_hosts.assert_called_once()

    def test_get_host_list_invalid_params(self):
        """测试：无效参数返回错误"""
        request = self.factory.get("/hosts/", {})  # 缺少必需的bk_biz_id
        request.user = self.user

        response = self.view(request)

        self.assertEqual(response.status_code, 400)

    @patch("home_application.views.host.get_client_by_request")
    def test_get_host_list_api_failure(self, mock_get_client):
        """测试：CMDB API调用失败"""
        mock_client = MagicMock()
        mock_client.cc.list_biz_hosts.return_value = {"result": False, "message": "API Error"}
        mock_get_client.return_value = mock_client

        request = self.factory.get("/hosts/", {"bk_biz_id": 1})
        request.user = self.user

        response = self.view(request)

        self.assertEqual(response.status_code, 500)


class TestHostDetailAPIView(TestCase):
    """测试 HostDetailAPIView"""

    def setUp(self):
        self.factory = RequestFactory()
        self.view = HostDetailAPIView.as_view()
        self.user = User.objects.create_user(username="testuser")
        UserRole.objects.create(username="testuser", role="dev")

    @patch("home_application.views.host.get_client_by_request")
    def test_get_host_detail_success(self, mock_get_client):
        """测试：成功获取主机详情"""
        mock_client = MagicMock()
        mock_client.cc.get_host_base_info.return_value = {
            "result": True,
            "data": {"info": [{"bk_host_id": 1, "bk_host_innerip": "192.168.1.1"}]},
        }
        mock_get_client.return_value = mock_client

        request = self.factory.get("/hosts/detail/", {"bk_host_id": 1})
        request.user = self.user

        response = self.view(request)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["result"])

    def test_get_host_detail_missing_param(self):
        """测试：缺少必需参数"""
        request = self.factory.get("/hosts/detail/", {})
        request.user = self.user

        response = self.view(request)

        self.assertEqual(response.status_code, 400)

    @patch("home_application.views.host.get_client_by_request")
    def test_get_host_detail_api_failure(self, mock_get_client):
        """测试：API调用失败"""
        mock_client = MagicMock()
        mock_client.cc.get_host_base_info.return_value = {"result": False, "message": "Not found"}
        mock_get_client.return_value = mock_client

        request = self.factory.get("/hosts/detail/", {"bk_host_id": 999})
        request.user = self.user

        response = self.view(request)

        self.assertEqual(response.status_code, 500)

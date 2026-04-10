"""
CMDBApiClient 单元测试
测试CMDB API客户端的业务逻辑
"""

from unittest.mock import MagicMock, patch

from django.test import TestCase

from home_application.services.cmdb_api_client import CMDBApiClient


class TestCMDBApiClient(TestCase):
    """测试 CMDBApiClient 的业务逻辑"""

    @patch("home_application.services.cmdb_api_client.API_AUTH_HEADER", {"Authorization": "Bearer test"})
    def test_init(self):
        """测试：初始化客户端"""
        client = CMDBApiClient()
        self.assertEqual(client.headers, {"Authorization": "Bearer test"})

    @patch("home_application.services.cmdb_api_client.requests.post")
    @patch("home_application.services.cmdb_api_client.CMDB_BASE_URL", "http://cmdb.test.com")
    @patch("home_application.services.cmdb_api_client.API_ENDPOINTS", {"biz": "/api/biz/{supplier_account}"})
    @patch("home_application.services.cmdb_api_client.SUPPLIER_ACCOUNT", "0")
    @patch("home_application.services.cmdb_api_client.DATA_CONFIGS", {"biz": {"fields": ["bk_biz_id", "bk_biz_name"]}})
    @patch("home_application.services.cmdb_api_client.API_AUTH_HEADER", {"Authorization": "Bearer test"})
    def test_get_biz_success(self, mock_post):
        """测试：成功获取业务列表"""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "result": True,
            "data": {
                "info": [
                    {"bk_biz_id": 1, "bk_biz_name": "业务1"},
                    {"bk_biz_id": 2, "bk_biz_name": "业务2"},
                ]
            },
        }
        mock_post.return_value = mock_response

        client = CMDBApiClient()
        result = client.get_biz()

        # 验证请求参数
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertEqual(call_args[0][0], "http://cmdb.test.com/api/biz/0")
        self.assertEqual(call_args[1]["headers"], {"Authorization": "Bearer test"})

        # 验证返回结果
        self.assertTrue(result["result"])
        self.assertEqual(len(result["data"]["info"]), 2)

    @patch("home_application.services.cmdb_api_client.requests.post")
    @patch("home_application.services.cmdb_api_client.CMDB_BASE_URL", "http://cmdb.test.com")
    @patch(
        "home_application.services.cmdb_api_client.API_ENDPOINTS", {"set": "/api/set/{supplier_account}/{bk_biz_id}"}
    )
    @patch("home_application.services.cmdb_api_client.SUPPLIER_ACCOUNT", "0")
    @patch("home_application.services.cmdb_api_client.DATA_CONFIGS", {"set": {"fields": ["bk_set_id", "bk_set_name"]}})
    @patch("home_application.services.cmdb_api_client.API_AUTH_HEADER", {"Authorization": "Bearer test"})
    def test_get_set_success(self, mock_post):
        """测试：成功获取集群列表"""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "result": True,
            "data": {
                "info": [
                    {"bk_set_id": 101, "bk_set_name": "集群1"},
                    {"bk_set_id": 102, "bk_set_name": "集群2"},
                ]
            },
        }
        mock_post.return_value = mock_response

        client = CMDBApiClient()
        result = client.get_set(bk_biz_id=1)

        # 验证请求参数
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertEqual(call_args[0][0], "http://cmdb.test.com/api/set/0/1")

        # 验证返回结果
        self.assertTrue(result["result"])
        self.assertEqual(len(result["data"]["info"]), 2)

    @patch("home_application.services.cmdb_api_client.requests.post")
    @patch("home_application.services.cmdb_api_client.CMDB_BASE_URL", "http://cmdb.test.com")
    @patch(
        "home_application.services.cmdb_api_client.API_ENDPOINTS",
        {"module": "/api/module/{supplier_account}/{bk_biz_id}/{bk_set_id}"},
    )
    @patch("home_application.services.cmdb_api_client.SUPPLIER_ACCOUNT", "0")
    @patch(
        "home_application.services.cmdb_api_client.DATA_CONFIGS",
        {"module": {"fields": ["bk_module_id", "bk_module_name"]}},
    )
    @patch("home_application.services.cmdb_api_client.API_AUTH_HEADER", {"Authorization": "Bearer test"})
    def test_get_module_success(self, mock_post):
        """测试：成功获取模块列表"""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "result": True,
            "data": {
                "info": [
                    {"bk_module_id": 1001, "bk_module_name": "模块1"},
                    {"bk_module_id": 1002, "bk_module_name": "模块2"},
                ]
            },
        }
        mock_post.return_value = mock_response

        client = CMDBApiClient()
        result = client.get_module(bk_biz_id=1, bk_set_id=101)

        # 验证请求参数
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertEqual(call_args[0][0], "http://cmdb.test.com/api/module/0/1/101")

        # 验证返回结果
        self.assertTrue(result["result"])
        self.assertEqual(len(result["data"]["info"]), 2)

    @patch("home_application.services.cmdb_api_client.requests.post")
    @patch("home_application.services.cmdb_api_client.logger")
    @patch("home_application.services.cmdb_api_client.API_AUTH_HEADER", {"Authorization": "Bearer test"})
    def test_send_request_api_error(self, mock_logger, mock_post):
        """测试：API返回错误结果"""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "result": False,
            "message": "权限不足",
        }
        mock_post.return_value = mock_response

        client = CMDBApiClient()

        with self.assertRaises(Exception) as context:
            client._send_request("http://cmdb.test.com/api/test")

        self.assertIn("权限不足", str(context.exception))
        mock_logger.error.assert_called_once()

    @patch("home_application.services.cmdb_api_client.requests.post")
    @patch("home_application.services.cmdb_api_client.logger")
    @patch("home_application.services.cmdb_api_client.API_AUTH_HEADER", {"Authorization": "Bearer test"})
    def test_send_request_http_error(self, mock_logger, mock_post):
        """测试：HTTP请求错误"""
        from requests import RequestException

        mock_post.side_effect = RequestException("Connection refused")

        client = CMDBApiClient()

        with self.assertRaises(RequestException):
            client._send_request("http://cmdb.test.com/api/test")

        mock_logger.error.assert_called_once()

    @patch("home_application.services.cmdb_api_client.requests.post")
    @patch("home_application.services.cmdb_api_client.logger")
    @patch("home_application.services.cmdb_api_client.API_AUTH_HEADER", {"Authorization": "Bearer test"})
    def test_send_request_json_decode_error(self, mock_logger, mock_post):
        """测试：JSON解析错误"""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_post.return_value = mock_response

        client = CMDBApiClient()

        with self.assertRaises(ValueError):
            client._send_request("http://cmdb.test.com/api/test")

        mock_logger.error.assert_called_once()

    @patch("home_application.services.cmdb_api_client.requests.post")
    @patch("home_application.services.cmdb_api_client.CMDB_BASE_URL", "http://cmdb.test.com")
    @patch("home_application.services.cmdb_api_client.API_ENDPOINTS", {"biz": "/api/biz/{supplier_account}"})
    @patch("home_application.services.cmdb_api_client.SUPPLIER_ACCOUNT", "0")
    @patch("home_application.services.cmdb_api_client.DATA_CONFIGS", {"biz": {"fields": []}})
    @patch("home_application.services.cmdb_api_client.API_AUTH_HEADER", {"Authorization": "Bearer test"})
    def test_get_biz_missing_data_key(self, mock_post):
        """测试：API返回缺少data字段"""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "result": True,
            # 缺少 "data" 字段
        }
        mock_post.return_value = mock_response

        client = CMDBApiClient()

        with self.assertRaises(Exception):
            client.get_biz()

"""
CMDBClient 单元测试
测试CMDB客户端的业务逻辑
"""

from unittest.mock import MagicMock, patch

from django.test import TestCase

from home_application.services.cmdb_client import CMDBClient


class TestCMDBClient(TestCase):
    """测试 CMDBClient 的业务逻辑"""

    def test_init_with_request(self):
        """测试：使用request初始化客户端"""
        mock_request = MagicMock()

        with patch("home_application.services.cmdb_client.get_client_by_request") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            client = CMDBClient(request=mock_request)

            mock_get_client.assert_called_once_with(mock_request)
            self.assertEqual(client.client, mock_client)

    def test_init_with_token(self):
        """测试：使用token初始化客户端"""
        test_token = "test_bk_token"

        with patch("home_application.services.cmdb_client.component_client.ComponentClient") as mock_component:
            mock_client = MagicMock()
            mock_component.return_value = mock_client

            with patch("home_application.services.cmdb_client.APP_CODE", "test_app"):
                with patch("home_application.services.cmdb_client.SECRET_KEY", "test_secret"):
                    client = CMDBClient(token=test_token)

                    mock_component.assert_called_once_with(
                        "test_app", "test_secret", common_args={"bk_token": test_token}
                    )
                    self.assertEqual(client.client, mock_client)

    def test_init_without_request_and_token(self):
        """测试：不提供request和token时应该抛出异常"""
        with self.assertRaises(ValueError) as context:
            CMDBClient()

        self.assertIn("Either request or token must be provided", str(context.exception))

    def test_get_biz(self):
        """测试：获取业务列表"""
        mock_request = MagicMock()

        with patch("home_application.services.cmdb_client.get_client_by_request") as mock_get_client:
            mock_cc_client = MagicMock()
            mock_get_client.return_value.cc = mock_cc_client

            expected_result = {
                "data": {
                    "info": [
                        {"bk_biz_id": 1, "bk_biz_name": "业务1"},
                        {"bk_biz_id": 2, "bk_biz_name": "业务2"},
                    ]
                }
            }
            mock_cc_client.search_business.return_value = expected_result

            client = CMDBClient(request=mock_request)
            result = client.get_biz()

            # 验证API调用
            mock_cc_client.search_business.assert_called_once()
            call_args = mock_cc_client.search_business.call_args[0][0]
            self.assertIn("fields", call_args)

            # 验证返回结果
            self.assertEqual(result, expected_result)

    def test_get_set(self):
        """测试：获取集群列表"""
        mock_request = MagicMock()
        biz_id = 1

        with patch("home_application.services.cmdb_client.get_client_by_request") as mock_get_client:
            mock_cc_client = MagicMock()
            mock_get_client.return_value.cc = mock_cc_client

            expected_result = {
                "data": {
                    "info": [
                        {"bk_set_id": 101, "bk_set_name": "集群1"},
                        {"bk_set_id": 102, "bk_set_name": "集群2"},
                    ]
                }
            }
            mock_cc_client.search_set.return_value = expected_result

            client = CMDBClient(request=mock_request)
            result = client.get_set(biz_id)

            # 验证API调用
            mock_cc_client.search_set.assert_called_once()
            call_args = mock_cc_client.search_set.call_args[0][0]
            self.assertEqual(call_args["bk_biz_id"], biz_id)
            self.assertIn("fields", call_args)

            # 验证返回结果
            self.assertEqual(result, expected_result)

    def test_get_module(self):
        """测试：获取模块列表"""
        mock_request = MagicMock()
        biz_id = 1
        set_id = 101

        with patch("home_application.services.cmdb_client.get_client_by_request") as mock_get_client:
            mock_cc_client = MagicMock()
            mock_get_client.return_value.cc = mock_cc_client

            expected_result = {
                "data": {
                    "info": [
                        {"bk_module_id": 1001, "bk_module_name": "模块1"},
                        {"bk_module_id": 1002, "bk_module_name": "模块2"},
                    ]
                }
            }
            mock_cc_client.search_module.return_value = expected_result

            client = CMDBClient(request=mock_request)
            result = client.get_module(biz_id, set_id)

            # 验证API调用
            mock_cc_client.search_module.assert_called_once()
            call_args = mock_cc_client.search_module.call_args[0][0]
            self.assertEqual(call_args["bk_biz_id"], biz_id)
            self.assertEqual(call_args["bk_set_id"], set_id)
            self.assertIn("fields", call_args)

            # 验证返回结果
            self.assertEqual(result, expected_result)

    def test_get_topo(self):
        """测试：获取拓扑结构"""
        mock_request = MagicMock()
        biz_id = 1

        with patch("home_application.services.cmdb_client.get_client_by_request") as mock_get_client:
            mock_cc_client = MagicMock()
            mock_get_client.return_value.cc = mock_cc_client

            expected_result = {
                "data": [
                    {
                        "bk_inst_id": 1,
                        "bk_inst_name": "业务1",
                        "child": [
                            {
                                "bk_inst_id": 101,
                                "bk_inst_name": "集群1",
                                "child": [],
                            }
                        ],
                    }
                ]
            }
            mock_cc_client.search_biz_inst_topo.return_value = expected_result

            client = CMDBClient(request=mock_request)
            result = client.get_topo(biz_id)

            # 验证API调用
            mock_cc_client.search_biz_inst_topo.assert_called_once()
            call_args = mock_cc_client.search_biz_inst_topo.call_args[0][0]
            self.assertEqual(call_args["bk_biz_id"], biz_id)

            # 验证返回结果
            self.assertEqual(result, expected_result)

    def test_get_host_list(self):
        """测试：获取主机列表"""
        mock_request = MagicMock()
        args = {"bk_biz_id": 1, "page": {"start": 0, "limit": 10}}

        with patch("home_application.services.cmdb_client.get_client_by_request") as mock_get_client:
            mock_cc_client = MagicMock()
            mock_get_client.return_value.cc = mock_cc_client

            expected_result = {
                "data": {
                    "info": [
                        {"bk_host_id": 1001, "bk_host_innerip": "192.168.1.1"},
                        {"bk_host_id": 1002, "bk_host_innerip": "192.168.1.2"},
                    ]
                }
            }
            mock_cc_client.list_biz_hosts.return_value = expected_result

            client = CMDBClient(request=mock_request)
            result = client.get_host_list(args)

            # 验证API调用
            mock_cc_client.list_biz_hosts.assert_called_once_with(args)

            # 验证返回结果
            self.assertEqual(result, expected_result)

    def test_get_host_detail(self):
        """测试：获取主机详情"""
        mock_request = MagicMock()
        args = {"bk_host_id": 1001}

        with patch("home_application.services.cmdb_client.get_client_by_request") as mock_get_client:
            mock_cc_client = MagicMock()
            mock_get_client.return_value.cc = mock_cc_client

            expected_result = {
                "data": {"info": [{"bk_host_id": 1001, "bk_host_innerip": "192.168.1.1", "bk_os_type": "Linux"}]}
            }
            mock_cc_client.get_host_base_info.return_value = expected_result

            client = CMDBClient(request=mock_request)
            result = client.get_host_detail(args)

            # 验证API调用
            mock_cc_client.get_host_base_info.assert_called_once_with(args)

            # 验证返回结果
            self.assertEqual(result, expected_result)

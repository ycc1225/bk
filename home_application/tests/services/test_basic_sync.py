"""
BasicCMDBSyncService 单元测试
测试CMDB基础数据同步服务的业务逻辑
"""

from unittest.mock import MagicMock, patch

from django.test import TestCase

from home_application.models import BizInfo, ModuleInfo, SetInfo, SyncStatus
from home_application.services.basic_sync import BasicCMDBSyncService


class TestBasicCMDBSyncService(TestCase):
    """测试 BasicCMDBSyncService 的业务逻辑"""

    def setUp(self):
        """测试前置准备"""
        self.token = "test_token"

    @patch("home_application.services.basic_sync.CMDBClient")
    def test_init_with_token(self, mock_cmdb_client_class):
        """测试：使用token初始化服务"""
        mock_client = MagicMock()
        mock_cmdb_client_class.return_value = mock_client

        service = BasicCMDBSyncService(token=self.token)

        # 验证CMDBClient被正确初始化
        mock_cmdb_client_class.assert_called_once_with(token=self.token)
        self.assertEqual(service.client, mock_client)
        # 验证SyncStatus记录已创建
        self.assertIsNotNone(service.status)
        self.assertEqual(service.status.name, "basic_sync")

    @patch("home_application.services.basic_sync.CMDBApiClient")
    def test_init_without_token(self, mock_api_client_class):
        """测试：不使用token初始化服务（使用API客户端）"""
        mock_client = MagicMock()
        mock_api_client_class.return_value = mock_client

        service = BasicCMDBSyncService()

        # 验证CMDBApiClient被正确初始化
        mock_api_client_class.assert_called_once()
        self.assertEqual(service.client, mock_client)

    @patch("home_application.services.basic_sync.CMDBClient")
    def test_sync_success(self, mock_cmdb_client_class):
        """测试：成功执行完整同步流程"""
        mock_client = MagicMock()
        mock_cmdb_client_class.return_value = mock_client

        # 模拟API返回数据
        mock_client.get_biz.return_value = {"data": {"info": []}}
        mock_client.get_set.return_value = {"data": {"info": []}}
        mock_client.get_module.return_value = {"data": {"info": []}}

        service = BasicCMDBSyncService(token=self.token)

        # 执行同步
        service.sync()

        # 验证状态流转
        status = SyncStatus.objects.get(name="basic_sync")
        self.assertEqual(status.last_status, "success")

        # 验证各同步方法被调用
        mock_client.get_biz.assert_called_once()

    @patch("home_application.services.basic_sync.CMDBClient")
    def test_sync_failure(self, mock_cmdb_client_class):
        """测试：同步过程中发生异常"""
        mock_client = MagicMock()
        mock_cmdb_client_class.return_value = mock_client

        # 模拟API调用抛出异常
        mock_client.get_biz.side_effect = Exception("API Error")

        service = BasicCMDBSyncService(token=self.token)

        # 执行同步应该抛出异常
        with self.assertRaises(Exception) as context:
            service.sync()

        self.assertIn("API Error", str(context.exception))

        # 验证状态为失败
        status = SyncStatus.objects.get(name="basic_sync")
        self.assertEqual(status.last_status, "failed")
        self.assertIn("API Error", status.last_error)

    @patch("home_application.services.basic_sync.CMDBClient")
    def test_sync_biz(self, mock_cmdb_client_class):
        """测试：同步业务数据"""
        mock_client = MagicMock()
        mock_cmdb_client_class.return_value = mock_client

        # 模拟业务数据
        mock_client.get_biz.return_value = {
            "data": {
                "info": [
                    {"bk_biz_id": 1, "bk_biz_name": "业务1"},
                    {"bk_biz_id": 2, "bk_biz_name": "业务2"},
                ]
            }
        }

        service = BasicCMDBSyncService(token=self.token)
        result = service.sync_biz()

        # 验证结果
        self.assertTrue(result["success"])
        self.assertEqual(result["saved_count"], 2)

        # 验证数据库记录
        self.assertEqual(BizInfo.objects.count(), 2)
        self.assertTrue(BizInfo.objects.filter(bk_biz_id=1, bk_biz_name="业务1").exists())
        self.assertTrue(BizInfo.objects.filter(bk_biz_id=2, bk_biz_name="业务2").exists())

    @patch("home_application.services.basic_sync.CMDBClient")
    def test_sync_set(self, mock_cmdb_client_class):
        """测试：同步集群数据"""
        mock_client = MagicMock()
        mock_cmdb_client_class.return_value = mock_client

        # 先创建业务数据
        BizInfo.objects.create(bk_biz_id=1, bk_biz_name="业务1")
        BizInfo.objects.create(bk_biz_id=2, bk_biz_name="业务2")

        # 模拟集群数据 - 根据业务ID返回不同的数据
        def mock_get_set(biz_id):
            if biz_id == 1:
                return {
                    "data": {
                        "info": [
                            {"bk_set_id": 101, "bk_set_name": "集群1", "bk_biz_id": 1},
                            {"bk_set_id": 102, "bk_set_name": "集群2", "bk_biz_id": 1},
                        ]
                    }
                }
            else:
                return {
                    "data": {
                        "info": [
                            {"bk_set_id": 201, "bk_set_name": "集群3", "bk_biz_id": 2},
                        ]
                    }
                }

        mock_client.get_set.side_effect = mock_get_set

        service = BasicCMDBSyncService(token=self.token)
        result = service.sync_set()

        # 验证结果
        self.assertTrue(result["success"])
        self.assertEqual(result["saved_count"], 3)

        # 验证数据库记录
        self.assertEqual(SetInfo.objects.count(), 3)
        self.assertTrue(SetInfo.objects.filter(bk_set_id=101, bk_biz_id=1).exists())

    @patch("home_application.services.basic_sync.CMDBClient")
    def test_sync_module(self, mock_cmdb_client_class):
        """测试：同步模块数据"""
        mock_client = MagicMock()
        mock_cmdb_client_class.return_value = mock_client

        # 先创建业务和集群数据
        BizInfo.objects.create(bk_biz_id=1, bk_biz_name="业务1")
        SetInfo.objects.create(bk_set_id=101, bk_set_name="集群1", bk_biz_id=1)

        # 模拟模块数据
        mock_client.get_module.return_value = {
            "data": {
                "info": [
                    {"bk_module_id": 1001, "bk_module_name": "模块1", "bk_set_id": 101, "bk_biz_id": 1},
                    {"bk_module_id": 1002, "bk_module_name": "模块2", "bk_set_id": 101, "bk_biz_id": 1},
                ]
            }
        }

        service = BasicCMDBSyncService(token=self.token)
        result = service.sync_module()

        # 验证结果
        self.assertTrue(result["success"])
        self.assertEqual(result["saved_count"], 2)

        # 验证数据库记录
        self.assertEqual(ModuleInfo.objects.count(), 2)

    @patch("home_application.services.basic_sync.CMDBClient")
    def test_sync_biz_with_empty_data(self, mock_cmdb_client_class):
        """测试：同步空业务数据"""
        mock_client = MagicMock()
        mock_cmdb_client_class.return_value = mock_client

        mock_client.get_biz.return_value = {"data": {"info": []}}

        service = BasicCMDBSyncService(token=self.token)
        result = service.sync_biz()

        self.assertTrue(result["success"])
        self.assertEqual(result["saved_count"], 0)

    @patch("home_application.services.basic_sync.CMDBClient")
    def test_sync_biz_with_invalid_data(self, mock_cmdb_client_class):
        """测试：同步包含无效数据的业务数据"""
        mock_client = MagicMock()
        mock_cmdb_client_class.return_value = mock_client

        # 包含无效数据（缺少bk_biz_id）
        mock_client.get_biz.return_value = {
            "data": {
                "info": [
                    {"bk_biz_id": 1, "bk_biz_name": "业务1"},
                    {"bk_biz_name": "无效业务"},  # 缺少bk_biz_id
                    {"bk_biz_id": None, "bk_biz_name": "无效业务2"},  # bk_biz_id为None
                ]
            }
        }

        service = BasicCMDBSyncService(token=self.token)
        result = service.sync_biz()

        # 只有第一条有效数据被保存
        self.assertTrue(result["success"])
        self.assertEqual(result["saved_count"], 1)
        self.assertEqual(BizInfo.objects.count(), 1)

    @patch("home_application.services.basic_sync.CMDBClient")
    def test_save_to_database_failure(self, mock_cmdb_client_class):
        """测试：数据库保存失败"""
        mock_client = MagicMock()
        mock_cmdb_client_class.return_value = mock_client

        service = BasicCMDBSyncService(token=self.token)

        # 传入无效的数据触发异常（使用有效的模型但无效的数据）
        result = service._save_to_database(
            config={
                "model": BizInfo,  # 使用有效的模型
                "unique_field": "invalid_field",  # 无效字段会导致异常
                "defaults_map": {},
            },
            data_list=[{"invalid_field": 1}],  # 该字段不存在于BizInfo
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["saved_count"], 0)

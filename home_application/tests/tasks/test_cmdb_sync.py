"""
CMDB同步任务单元测试
"""

from unittest.mock import MagicMock, patch

from django.test import TestCase

from home_application.tasks.cmdb_sync import basic_sync_data_task, topo_sync_data_task


class TestBasicSyncDataTask(TestCase):
    """测试 basic_sync_data_task"""

    @patch("home_application.tasks.cmdb_sync.BasicCMDBSyncService")
    @patch("home_application.tasks.cmdb_sync.celery_tasks_total")
    @patch("home_application.tasks.cmdb_sync.cmdb_sync_last_success")
    def test_sync_success(self, mock_success_metric, mock_task_metric, mock_service_class):
        """测试：成功执行基础数据同步"""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        basic_sync_data_task(token="test_token")

        # 验证服务被正确初始化
        mock_service_class.assert_called_once_with("test_token")
        # 验证sync方法被调用
        mock_service.sync.assert_called_once()
        # 验证成功指标
        mock_task_metric.labels.assert_called_with(task_name="basic_sync_data", status="success")
        mock_success_metric.labels.assert_called_with(sync_type="basic")

    @patch("home_application.tasks.cmdb_sync.BasicCMDBSyncService")
    @patch("home_application.tasks.cmdb_sync.celery_tasks_total")
    def test_sync_failure(self, mock_task_metric, mock_service_class):
        """测试：同步失败时抛出异常"""
        mock_service = MagicMock()
        mock_service.sync.side_effect = Exception("Sync Error")
        mock_service_class.return_value = mock_service

        with self.assertRaises(Exception):
            basic_sync_data_task(token="test_token")

        # 验证失败指标
        mock_task_metric.labels.assert_called_with(task_name="basic_sync_data", status="failure")

    @patch("home_application.tasks.cmdb_sync.BasicCMDBSyncService")
    def test_sync_without_token(self, mock_service_class):
        """测试：不提供token（使用默认）"""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        basic_sync_data_task()

        # 验证服务被正确初始化（不传token）
        mock_service_class.assert_called_once_with(None)


class TestTopoSyncDataTask(TestCase):
    """测试 topo_sync_data_task"""

    @patch("home_application.tasks.cmdb_sync.TopoCMDBSyncService")
    @patch("home_application.tasks.cmdb_sync.celery_tasks_total")
    @patch("home_application.tasks.cmdb_sync.cmdb_sync_last_success")
    def test_sync_success(self, mock_success_metric, mock_task_metric, mock_service_class):
        """测试：成功执行拓扑同步"""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        topo_sync_data_task(token="test_token")

        mock_service_class.assert_called_once_with("test_token")
        mock_service.sync.assert_called_once()
        mock_task_metric.labels.assert_called_with(task_name="topo_sync_data", status="success")
        mock_success_metric.labels.assert_called_with(sync_type="topo")

    @patch("home_application.tasks.cmdb_sync.TopoCMDBSyncService")
    @patch("home_application.tasks.cmdb_sync.celery_tasks_total")
    def test_sync_failure(self, mock_task_metric, mock_service_class):
        """测试：拓扑同步失败"""
        mock_service = MagicMock()
        mock_service.sync.side_effect = Exception("Topo Sync Error")
        mock_service_class.return_value = mock_service

        with self.assertRaises(Exception):
            topo_sync_data_task(token="test_token")

        mock_task_metric.labels.assert_called_with(task_name="topo_sync_data", status="failure")

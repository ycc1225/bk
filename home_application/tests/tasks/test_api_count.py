"""
API计数同步任务单元测试
"""

from unittest.mock import patch

from django.test import TestCase

from home_application.models import ApiRequestCount
from home_application.tasks.api_count import sync_api_counts_task


class TestSyncApiCountsTask(TestCase):
    """测试 sync_api_counts_task"""

    @patch("home_application.tasks.api_count.fetch_api_counts_and_rename")
    @patch("home_application.tasks.api_count.delete_redis_key")
    @patch("home_application.tasks.api_count.celery_tasks_total")
    def test_sync_success(self, mock_metrics, mock_delete, mock_fetch):
        """测试：成功同步API计数"""
        # Mock Redis数据
        mock_fetch.return_value = (
            {
                ("2024-01-01", "backup", "create"): {"req": 10, "err": 2},
                ("2024-01-01", "sync", "biz"): {"req": 5, "err": 0},
            },
            "temp_key_123",
        )

        result = sync_api_counts_task()

        # 验证数据库记录
        self.assertEqual(ApiRequestCount.objects.count(), 2)

        # 验证第一条记录
        record1 = ApiRequestCount.objects.get(api_category="backup", api_name="create")
        self.assertEqual(record1.request_count, 10)
        self.assertEqual(record1.error_count, 2)

        # 验证第二条记录
        record2 = ApiRequestCount.objects.get(api_category="sync", api_name="biz")
        self.assertEqual(record2.request_count, 5)
        self.assertEqual(record2.error_count, 0)

        # 验证Redis key被删除
        mock_delete.assert_called_once_with("temp_key_123")

        # 验证指标记录
        mock_metrics.labels.assert_called_with(task_name="sync_api_counts", status="success")

        self.assertEqual(result, "Synced 2 records")

    @patch("home_application.tasks.api_count.fetch_api_counts_and_rename")
    @patch("home_application.tasks.api_count.delete_redis_key")
    def test_sync_empty_data(self, mock_delete, mock_fetch):
        """测试：没有数据需要同步"""
        mock_fetch.return_value = ({}, None)

        result = sync_api_counts_task()

        self.assertEqual(ApiRequestCount.objects.count(), 0)
        mock_delete.assert_not_called()
        self.assertEqual(result, "No data to sync")

    @patch("home_application.tasks.api_count.fetch_api_counts_and_rename")
    @patch("home_application.tasks.api_count.delete_redis_key")
    def test_sync_with_temp_key_but_no_data(self, mock_delete, mock_fetch):
        """测试：有temp_key但数据为空"""
        mock_fetch.return_value = ({}, "temp_key_123")

        result = sync_api_counts_task()

        self.assertEqual(ApiRequestCount.objects.count(), 0)
        mock_delete.assert_called_once_with("temp_key_123")
        self.assertEqual(result, "No data to sync")

    @patch("home_application.tasks.api_count.fetch_api_counts_and_rename")
    @patch("home_application.tasks.api_count.delete_redis_key")
    @patch("home_application.tasks.api_count.celery_tasks_total")
    def test_sync_skip_zero_counts(self, mock_metrics, mock_delete, mock_fetch):
        """测试：跳过计数为0的记录"""
        mock_fetch.return_value = (
            {
                ("2024-01-01", "test", "zero"): {"req": 0, "err": 0},
                ("2024-01-01", "test", "nonzero"): {"req": 1, "err": 0},
            },
            "temp_key_123",
        )

        sync_api_counts_task()

        # 只有非零记录被保存
        self.assertEqual(ApiRequestCount.objects.count(), 1)
        self.assertTrue(ApiRequestCount.objects.filter(api_name="nonzero").exists())
        self.assertFalse(ApiRequestCount.objects.filter(api_name="zero").exists())

    @patch("home_application.tasks.api_count.fetch_api_counts_and_rename")
    @patch("home_application.tasks.api_count.delete_redis_key")
    @patch("home_application.tasks.api_count.celery_tasks_total")
    def test_sync_db_exception(self, mock_metrics, mock_delete, mock_fetch):
        """测试：数据库异常处理"""
        mock_fetch.return_value = (
            {("2024-01-01", "test", "api"): {"req": 1, "err": 0}},
            "temp_key_123",
        )

        # Mock数据库操作抛出异常
        with patch.object(ApiRequestCount.objects, "get_or_create", side_effect=Exception("DB Error")):
            result = sync_api_counts_task()

        self.assertIn("Failed", result)
        mock_metrics.labels.assert_called_with(task_name="sync_api_counts", status="failure")
        # 异常时不应删除Redis key
        mock_delete.assert_not_called()

    @patch("home_application.tasks.api_count.fetch_api_counts_and_rename")
    @patch("home_application.tasks.api_count.celery_tasks_total")
    def test_sync_fetch_exception(self, mock_metrics, mock_fetch):
        """测试：获取Redis数据异常"""
        mock_fetch.side_effect = Exception("Redis Error")

        result = sync_api_counts_task()

        self.assertIn("Failed", result)
        mock_metrics.labels.assert_called_with(task_name="sync_api_counts", status="failure")

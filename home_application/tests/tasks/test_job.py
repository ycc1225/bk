"""
作业任务单元测试
测试poll_job_status、fetch_job_logs、process_backup_results等Celery任务
"""

from unittest.mock import MagicMock, patch

from django.test import TestCase

from home_application.models import BackupJob, BackupRecord
from home_application.tasks.job import fetch_job_logs, process_backup_results


class TestPollJobStatus(TestCase):
    """测试 poll_job_status 任务 - 直接测试内部逻辑"""

    def setUp(self):
        self.job_instance_id = 12345
        self.bk_biz_id = 1
        self.bk_token = "test_token"

    @patch("home_application.tasks.job.get_esb_client")
    def test_poll_success(self, mock_get_client):
        """测试：作业成功完成"""
        mock_client = MagicMock()
        mock_client.jobv3.get_job_instance_status.return_value = {
            "data": {
                "step_instance_list": [
                    {
                        "status": 3,  # SUCCESS_CODE = 3
                        "step_instance_id": 1001,
                    }
                ]
            }
        }
        mock_get_client.return_value = mock_client

        # 直接调用run方法绕过Celery绑定
        from home_application.tasks.job import poll_job_status

        result = poll_job_status.run(self.job_instance_id, self.bk_biz_id, self.bk_token)

        self.assertTrue(result["success"])
        self.assertTrue(result["is_finished"])
        self.assertTrue(result["is_success"])
        self.assertEqual(result["job_instance_id"], self.job_instance_id)

    @patch("home_application.tasks.job.get_esb_client")
    def test_poll_job_failed(self, mock_get_client):
        """测试：作业执行失败"""
        mock_client = MagicMock()
        mock_client.jobv3.get_job_instance_status.return_value = {
            "data": {
                "step_instance_list": [
                    {
                        "status": 4,  # 失败状态
                        "step_instance_id": 1001,
                    }
                ]
            }
        }
        mock_get_client.return_value = mock_client

        from home_application.tasks.job import poll_job_status

        result = poll_job_status.run(self.job_instance_id, self.bk_biz_id, self.bk_token)

        self.assertTrue(result["success"])
        self.assertTrue(result["is_finished"])
        self.assertFalse(result["is_success"])

    @patch("home_application.tasks.job.get_esb_client")
    def test_poll_empty_step_list(self, mock_get_client):
        """测试：返回空的step_instance_list"""
        mock_client = MagicMock()
        mock_client.jobv3.get_job_instance_status.return_value = {"data": {"step_instance_list": []}}
        mock_get_client.return_value = mock_client

        from home_application.tasks.job import poll_job_status

        # 空列表应该抛出异常
        with self.assertRaises(Exception):
            poll_job_status.run(self.job_instance_id, self.bk_biz_id, self.bk_token)

    @patch("home_application.tasks.job.get_esb_client")
    def test_poll_api_exception(self, mock_get_client):
        """测试：API调用异常"""
        mock_client = MagicMock()
        mock_client.jobv3.get_job_instance_status.side_effect = Exception("API Error")
        mock_get_client.return_value = mock_client

        from home_application.tasks.job import poll_job_status

        # 异常应该被抛出
        with self.assertRaises(Exception):
            poll_job_status.run(self.job_instance_id, self.bk_biz_id, self.bk_token)


class TestFetchJobLogs(TestCase):
    """测试 fetch_job_logs 任务"""

    def setUp(self):
        self.job_instance_id = 12345
        self.host_id_list = [1, 2, 3]
        self.bk_token = "test_token"

    def test_upstream_failed(self):
        """测试：上游任务失败"""
        job_status_result = {
            "success": False,
            "error": "上游任务失败",
            "job_instance_id": self.job_instance_id,
        }

        result = fetch_job_logs(job_status_result, self.host_id_list, self.bk_token)

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "上游任务失败")
        self.assertEqual(result["error_type"], "upstream_error")

    def test_job_execution_failed(self):
        """测试：作业执行失败（未成功完成）"""
        job_status_result = {
            "success": True,
            "is_success": False,
            "job_instance_id": self.job_instance_id,
        }

        result = fetch_job_logs(job_status_result, self.host_id_list, self.bk_token)

        self.assertTrue(result["success"])
        self.assertFalse(result["is_job_success"])

    @patch("home_application.tasks.job.get_esb_client")
    @patch("home_application.tasks.job.batch_get_job_logs")
    @patch("home_application.tasks.job.add_trace_attrs")
    @patch("home_application.tasks.job.celery_tasks_total")
    def test_fetch_logs_success(self, mock_metrics, mock_batch_logs, mock_get_client):
        """测试：成功获取作业日志"""
        job_status_result = {
            "success": True,
            "is_success": True,
            "job_instance_id": self.job_instance_id,
            "step_instance_id": 1001,
            "bk_biz_id": 1,
        }

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_batch_logs.return_value = [
            {"bk_host_id": 1, "log": "log1", "is_success": True},
            {"bk_host_id": 2, "log": "log2", "is_success": True},
        ]

        result = fetch_job_logs(job_status_result, self.host_id_list, self.bk_token)

        self.assertTrue(result["success"])
        self.assertTrue(result["is_job_success"])
        self.assertEqual(len(result["results"]), 2)
        mock_metrics.labels.assert_called_with(task_name="fetch_job_logs", status="success")

    @patch("home_application.tasks.job.get_esb_client")
    @patch("home_application.tasks.job.batch_get_job_logs")
    @patch("home_application.tasks.job.add_trace_attrs")
    @patch("home_application.tasks.job.celery_tasks_total")
    def test_fetch_logs_exception(self, mock_metrics, mock_batch_logs, mock_get_client):
        """测试：获取日志时抛出异常"""
        job_status_result = {
            "success": True,
            "is_success": True,
            "job_instance_id": self.job_instance_id,
            "step_instance_id": 1001,
            "bk_biz_id": 1,
        }

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_batch_logs.side_effect = Exception("Log fetch error")

        result = fetch_job_logs(job_status_result, self.host_id_list, self.bk_token)

        self.assertFalse(result["success"])
        self.assertIn("获取作业日志失败", result["error"])
        mock_metrics.labels.assert_called_with(task_name="fetch_job_logs", status="failure")


class TestProcessBackupResults(TestCase):
    """测试 process_backup_results 任务"""

    def setUp(self):
        self.job_instance_id = 12345

    def test_backup_job_not_found(self):
        """测试：BackupJob不存在"""
        fetch_logs_result = {
            "success": True,
            "job_instance_id": self.job_instance_id,
        }

        result = process_backup_results(fetch_logs_result)

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "BackupJob不存在")

    def test_fetch_logs_failed_poll_status_error(self):
        """测试：获取日志失败 - POLL_STATUS_ERROR"""
        backup_job = BackupJob.objects.create(
            job_instance_id=str(self.job_instance_id),
            operator="test_user",
            status=BackupJob.Status.PROCESSING,
        )

        fetch_logs_result = {
            "success": False,
            "error_type": "POLL_STATUS_ERROR",
            "error": "查询状态失败",
            "job_instance_id": self.job_instance_id,
        }

        process_backup_results(fetch_logs_result)

        backup_job.refresh_from_db()
        self.assertEqual(backup_job.status, BackupJob.Status.FAILED)

    def test_fetch_logs_failed_fetch_logs_error(self):
        """测试：获取日志失败 - FETCH_LOGS_ERROR"""
        backup_job = BackupJob.objects.create(
            job_instance_id=str(self.job_instance_id),
            operator="test_user",
            status=BackupJob.Status.PROCESSING,
        )

        fetch_logs_result = {
            "success": False,
            "error_type": "FETCH_LOGS_ERROR",
            "error": "获取日志失败",
            "job_instance_id": self.job_instance_id,
        }

        process_backup_results(fetch_logs_result)

        backup_job.refresh_from_db()
        self.assertEqual(backup_job.status, BackupJob.Status.FAILED)

    def test_fetch_logs_failed_upstream_error(self):
        """测试：获取日志失败 - UPSTREAM_ERROR"""
        backup_job = BackupJob.objects.create(
            job_instance_id=str(self.job_instance_id),
            operator="test_user",
            status=BackupJob.Status.PROCESSING,
        )

        fetch_logs_result = {
            "success": False,
            "error_type": "UPSTREAM_ERROR",
            "error": "上游失败",
            "job_instance_id": self.job_instance_id,
        }

        process_backup_results(fetch_logs_result)

        backup_job.refresh_from_db()
        self.assertEqual(backup_job.status, BackupJob.Status.FAILED)

    def test_job_execution_failed(self):
        """测试：作业执行失败（is_job_success=False）"""
        backup_job = BackupJob.objects.create(
            job_instance_id=str(self.job_instance_id),
            operator="test_user",
            status=BackupJob.Status.PROCESSING,
        )

        fetch_logs_result = {
            "success": True,
            "is_job_success": False,
            "job_instance_id": self.job_instance_id,
            "results": [],
        }

        process_backup_results(fetch_logs_result)

        backup_job.refresh_from_db()
        self.assertEqual(backup_job.status, BackupJob.Status.FAILED)

    def test_all_hosts_success(self):
        """测试：所有主机备份成功"""
        backup_job = BackupJob.objects.create(
            job_instance_id=str(self.job_instance_id),
            operator="test_user",
            status=BackupJob.Status.PROCESSING,
        )

        fetch_logs_result = {
            "success": True,
            "is_job_success": True,
            "job_instance_id": self.job_instance_id,
            "results": [
                {
                    "bk_host_id": 1,
                    "is_success": True,
                    "parsed_data": {"bk_backup_name": "backup1.tar"},
                },
                {
                    "bk_host_id": 2,
                    "is_success": True,
                    "parsed_data": {"bk_backup_name": "backup2.tar"},
                },
            ],
        }

        process_backup_results(fetch_logs_result)

        backup_job.refresh_from_db()
        self.assertEqual(backup_job.status, BackupJob.Status.SUCCESS)
        self.assertEqual(BackupRecord.objects.count(), 2)

    def test_all_hosts_failed(self):
        """测试：所有主机备份失败"""
        backup_job = BackupJob.objects.create(
            job_instance_id=str(self.job_instance_id),
            operator="test_user",
            status=BackupJob.Status.PROCESSING,
        )

        fetch_logs_result = {
            "success": True,
            "is_job_success": True,
            "job_instance_id": self.job_instance_id,
            "results": [
                {
                    "bk_host_id": 1,
                    "is_success": False,
                    "parsed_data": None,
                },
            ],
        }

        process_backup_results(fetch_logs_result)

        backup_job.refresh_from_db()
        self.assertEqual(backup_job.status, BackupJob.Status.FAILED)

    def test_partial_success(self):
        """测试：部分主机成功"""
        backup_job = BackupJob.objects.create(
            job_instance_id=str(self.job_instance_id),
            operator="test_user",
            status=BackupJob.Status.PROCESSING,
        )

        fetch_logs_result = {
            "success": True,
            "is_job_success": True,
            "job_instance_id": self.job_instance_id,
            "results": [
                {
                    "bk_host_id": 1,
                    "is_success": True,
                    "parsed_data": {"bk_backup_name": "backup1.tar"},
                },
                {
                    "bk_host_id": 2,
                    "is_success": False,
                    "parsed_data": None,
                },
            ],
        }

        process_backup_results(fetch_logs_result)

        backup_job.refresh_from_db()
        self.assertEqual(backup_job.status, BackupJob.Status.PARTIAL)
        self.assertEqual(BackupRecord.objects.count(), 2)

    def test_list_parsed_data(self):
        """测试：parsed_data是列表的情况"""
        BackupJob.objects.create(
            job_instance_id=str(self.job_instance_id),
            operator="test_user",
            status=BackupJob.Status.PROCESSING,
        )

        fetch_logs_result = {
            "success": True,
            "is_job_success": True,
            "job_instance_id": self.job_instance_id,
            "results": [
                {
                    "bk_host_id": 1,
                    "is_success": True,
                    "parsed_data": [
                        {"bk_backup_name": "backup1a.tar"},
                        {"bk_backup_name": "backup1b.tar"},
                    ],
                },
            ],
        }

        process_backup_results(fetch_logs_result)

        self.assertEqual(BackupRecord.objects.count(), 2)

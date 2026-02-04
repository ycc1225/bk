"""
Job 服务层单元测试
专注测试业务逻辑，不测试外部接口调用
"""

from django.test import TestCase

from home_application.models import BackupJob
from home_application.services.job import BackupJobService


class TestBackupJobService(TestCase):
    """测试 BackupJobService 的业务逻辑"""

    def test_create_backup_job_success(self):
        """测试：成功创建备份作业记录"""
        backup_job = BackupJobService.create_backup_job(
            job_instance_id="12345",
            operator="test_user",
            search_path="/app/logs",
            suffix="log",
            backup_path="/backup",
            bk_job_link="http://job.example.com/12345",
            host_count=10,
        )

        # 验证对象属性
        self.assertIsNotNone(backup_job)
        self.assertEqual(backup_job.job_instance_id, "12345")
        self.assertEqual(backup_job.operator, "test_user")
        self.assertEqual(backup_job.search_path, "/app/logs")
        self.assertEqual(backup_job.suffix, "log")
        self.assertEqual(backup_job.backup_path, "/backup")
        self.assertEqual(backup_job.status, BackupJob.Status.PENDING)
        self.assertEqual(backup_job.host_count, 10)
        self.assertEqual(backup_job.file_count, 0)

        # 验证数据库中存在
        self.assertTrue(BackupJob.objects.filter(job_instance_id="12345").exists())

    def test_create_backup_job_with_special_characters(self):
        """测试：创建包含特殊字符的备份作业"""
        backup_job = BackupJobService.create_backup_job(
            job_instance_id="67890",
            operator="admin@example.com",
            search_path="/var/log/app-2024",
            suffix="*.log",
            backup_path="/backup/2024-01-01",
            bk_job_link="http://job.example.com/67890?biz=3",
            host_count=5,
        )

        # 验证特殊字符正确保存
        self.assertEqual(backup_job.search_path, "/var/log/app-2024")
        self.assertEqual(backup_job.suffix, "*.log")
        self.assertEqual(backup_job.backup_path, "/backup/2024-01-01")


class TestBatchGetJobLogs(TestCase):
    """测试 batch_get_job_logs 的日志解析逻辑"""

    def test_parse_valid_json_logs(self):
        """测试：解析有效的 JSON 日志"""
        from unittest.mock import MagicMock

        from home_application.services.job import batch_get_job_logs

        mock_client = MagicMock()
        mock_client.jobv3.batch_get_job_instance_ip_log.return_value = {
            "data": {
                "script_task_logs": [
                    {"host_id": 1001, "log_content": '{"files": ["/app/test.log", "/app/test2.log"]}'},
                    {"host_id": 1002, "log_content": '{"files": ["/var/log/app.log"]}'},
                ]
            }
        }

        results = batch_get_job_logs(
            client=mock_client,
            job_instance_id=12345,
            step_instance_id=100,
            host_id_list=[1001, 1002],
            bk_biz_id=3,
        )

        # 验证解析结果
        self.assertEqual(len(results), 2)

        # 验证第一个主机
        self.assertEqual(results[0]["bk_host_id"], 1001)
        self.assertTrue(results[0]["is_success"])
        self.assertIsNotNone(results[0]["parsed_data"])
        self.assertEqual(len(results[0]["parsed_data"]["files"]), 2)

        # 验证第二个主机
        self.assertEqual(results[1]["bk_host_id"], 1002)
        self.assertTrue(results[1]["is_success"])

    def test_parse_invalid_json_logs(self):
        """测试：解析无效的 JSON 日志（业务逻辑：标记为失败）"""
        from unittest.mock import MagicMock

        from home_application.services.job import batch_get_job_logs

        mock_client = MagicMock()
        mock_client.jobv3.batch_get_job_instance_ip_log.return_value = {
            "data": {
                "script_task_logs": [
                    {"host_id": 1001, "log_content": "This is not JSON"},
                    {"host_id": 1002, "log_content": "Error: File not found"},
                ]
            }
        }

        results = batch_get_job_logs(
            client=mock_client,
            job_instance_id=12345,
            step_instance_id=100,
            host_id_list=[1001, 1002],
            bk_biz_id=3,
        )

        # 验证解析失败的处理
        self.assertEqual(len(results), 2)

        # 验证两个主机都标记为失败
        self.assertFalse(results[0]["is_success"])
        self.assertIsNone(results[0]["parsed_data"])
        self.assertFalse(results[1]["is_success"])
        self.assertIsNone(results[1]["parsed_data"])

    def test_parse_mixed_logs(self):
        """测试：解析混合的日志（部分成功，部分失败）"""
        from unittest.mock import MagicMock

        from home_application.services.job import batch_get_job_logs

        mock_client = MagicMock()
        mock_client.jobv3.batch_get_job_instance_ip_log.return_value = {
            "data": {
                "script_task_logs": [
                    {"host_id": 1001, "log_content": '{"files": ["/app/test.log"]}'},
                    {"host_id": 1002, "log_content": "Error: Permission denied"},
                    {"host_id": 1003, "log_content": '{"files": []}'},
                ]
            }
        }

        results = batch_get_job_logs(
            client=mock_client,
            job_instance_id=12345,
            step_instance_id=100,
            host_id_list=[1001, 1002, 1003],
            bk_biz_id=3,
        )

        # 验证混合结果
        self.assertEqual(len(results), 3)
        self.assertTrue(results[0]["is_success"])  # 成功
        self.assertFalse(results[1]["is_success"])  # 失败
        self.assertTrue(results[2]["is_success"])  # 成功（空列表也是有效 JSON）

    def test_parse_non_dict_json(self):
        """测试：解析非字典/列表的 JSON（业务逻辑：标记为失败）"""
        from unittest.mock import MagicMock

        from home_application.services.job import batch_get_job_logs

        mock_client = MagicMock()
        mock_client.jobv3.batch_get_job_instance_ip_log.return_value = {
            "data": {
                "script_task_logs": [
                    {"host_id": 1001, "log_content": '"just a string"'},  # JSON 字符串
                    {"host_id": 1002, "log_content": "123"},  # JSON 数字
                    {"host_id": 1003, "log_content": "true"},  # JSON 布尔值
                ]
            }
        }

        results = batch_get_job_logs(
            client=mock_client,
            job_instance_id=12345,
            step_instance_id=100,
            host_id_list=[1001, 1002, 1003],
            bk_biz_id=3,
        )

        # 验证：虽然是有效 JSON，但不是字典/列表，应标记为失败
        self.assertEqual(len(results), 3)
        self.assertFalse(results[0]["is_success"])
        self.assertFalse(results[1]["is_success"])
        self.assertFalse(results[2]["is_success"])

    def test_parse_empty_logs(self):
        """测试：解析空日志"""
        from unittest.mock import MagicMock

        from home_application.services.job import batch_get_job_logs

        mock_client = MagicMock()
        mock_client.jobv3.batch_get_job_instance_ip_log.return_value = {
            "data": {
                "script_task_logs": [
                    {"host_id": 1001, "log_content": ""},
                    {"host_id": 1002, "log_content": None},
                ]
            }
        }

        results = batch_get_job_logs(
            client=mock_client,
            job_instance_id=12345,
            step_instance_id=100,
            host_id_list=[1001, 1002],
            bk_biz_id=3,
        )

        # 验证空日志的处理
        self.assertEqual(len(results), 2)
        self.assertFalse(results[0]["is_success"])
        self.assertFalse(results[1]["is_success"])

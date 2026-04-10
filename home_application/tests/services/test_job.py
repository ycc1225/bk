"""
Job服务层单元测试
测试JobExecutionService和BackupJobService的业务逻辑
"""

from unittest.mock import MagicMock, patch

from django.test import TestCase

from home_application.exceptions.job import (
    JobExecutionError,
    JobStatusError,
    JobTimeoutError,
)
from home_application.models import BackupJob
from home_application.services.job import BackupJobService, JobExecutionService


class TestJobExecutionService(TestCase):
    """测试 JobExecutionService 的业务逻辑"""

    def setUp(self):
        """测试前置准备"""
        self.mock_client = MagicMock()
        self.bk_biz_id = 3
        self.service = JobExecutionService(client=self.mock_client, bk_biz_id=self.bk_biz_id)

    @patch("home_application.services.job.batch_get_job_logs")
    @patch("home_application.services.job.MAX_ATTEMPTS", 3)
    @patch("home_application.services.job.WAITING_CODE", 1)
    @patch("home_application.services.job.SUCCESS_CODE", 3)
    @patch("home_application.services.job.FAILED_CODE", 4)
    @patch("home_application.services.job.JOB_RESULT_ATTEMPTS_INTERVAL", 0)  # 不等待
    @patch("home_application.services.job.tracer")
    def test_execute_search_file_success(self, mock_tracer, mock_batch_get_logs):
        """测试：成功执行文件搜索作业"""
        # Mock追踪器
        mock_span = MagicMock()
        mock_tracer.start_as_current_session = MagicMock()
        mock_tracer.start_as_current_session.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_session.return_value.__exit__ = MagicMock(return_value=False)

        # Mock作业执行响应
        self.mock_client.jobv3.execute_job_plan.return_value = {"data": {"job_instance_id": 12345}}

        # Mock作业状态响应 - 立即成功
        self.mock_client.jobv3.get_job_instance_status.return_value = {
            "data": {"step_instance_list": [{"status": 3, "step_instance_id": 100}]}  # SUCCESS_CODE = 3
        }

        # Mock日志获取结果
        mock_batch_get_logs.return_value = [
            {"bk_host_id": 1001, "is_success": True, "parsed_data": {"files": ["/app/test.log"]}},
            {"bk_host_id": 1002, "is_success": True, "parsed_data": {"files": ["/app/test2.log"]}},
        ]

        # 执行测试
        results = self.service.execute_search_file(
            host_id_list=[1001, 1002],
            search_path="/app",
            suffix="log",
            plan_id=1000,
        )

        # 验证结果 - execute_search_file返回的是解析后的数据，不是原始结果
        # 成功时返回的是 parsed_data 加上 bk_host_id
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["bk_host_id"], 1001)
        self.assertIn("files", results[0])  # parsed_data的内容
        self.assertEqual(results[0]["files"], ["/app/test.log"])

        # 验证API调用
        self.mock_client.jobv3.execute_job_plan.assert_called_once()
        self.mock_client.jobv3.get_job_instance_status.assert_called()

    @patch("home_application.services.job.MAX_ATTEMPTS", 2)
    @patch("home_application.services.job.WAITING_CODE", 1)
    @patch("home_application.services.job.SUCCESS_CODE", 3)
    @patch("home_application.services.job.FAILED_CODE", 4)
    @patch("home_application.services.job.JOB_RESULT_ATTEMPTS_INTERVAL", 0)
    def test_execute_search_file_timeout(self):
        """测试：作业执行超时"""
        # Mock作业执行响应
        self.mock_client.jobv3.execute_job_plan.return_value = {"data": {"job_instance_id": 12345}}

        # Mock作业状态始终等待中
        self.mock_client.jobv3.get_job_instance_status.return_value = {
            "data": {"step_instance_list": [{"status": 1}]}  # WAITING_CODE = 1
        }

        # 执行测试应该抛出超时异常
        with self.assertRaises(JobTimeoutError) as context:
            self.service.execute_search_file(
                host_id_list=[1001],
                search_path="/app",
                suffix="log",
                plan_id=1000,
            )

        self.assertIn("超时", str(context.exception))

    def test_execute_search_file_no_job_instance_id(self):
        """测试：执行作业未返回job_instance_id"""
        # Mock作业执行响应 - 没有job_instance_id
        self.mock_client.jobv3.execute_job_plan.return_value = {"data": {}}

        # 执行测试应该抛出异常
        with self.assertRaises(JobExecutionError) as context:
            self.service.execute_search_file(
                host_id_list=[1001],
                search_path="/app",
                suffix="log",
                plan_id=1000,
            )

        self.assertIn("job_instance_id", str(context.exception))

    @patch("home_application.services.job.MAX_ATTEMPTS", 1)
    @patch("home_application.services.job.WAITING_CODE", 1)
    def test_execute_search_file_no_step_instance(self):
        """测试：未获取到步骤实例信息"""
        # Mock作业执行响应
        self.mock_client.jobv3.execute_job_plan.return_value = {"data": {"job_instance_id": 12345}}

        # Mock作业状态 - 没有step_instance_list
        self.mock_client.jobv3.get_job_instance_status.return_value = {"data": {}}

        # 执行测试应该抛出异常
        with self.assertRaises(JobStatusError) as context:
            self.service.execute_search_file(
                host_id_list=[1001],
                search_path="/app",
                suffix="log",
                plan_id=1000,
            )

        self.assertIn("步骤实例", str(context.exception))

    def test_execute_backup_file_success(self):
        """测试：成功执行文件备份作业（异步）"""
        self.mock_client.jobv3.execute_job_plan.return_value = {"data": {"job_instance_id": 67890}}

        job_instance_id, bk_job_link = self.service.execute_backup_file(
            host_id_list=[1001, 1002],
            search_path="/app/logs",
            suffix="log",
            backup_path="/backup",
            plan_id=2000,
            callback_url="http://example.com/callback",
        )

        # 验证返回结果
        self.assertEqual(job_instance_id, "67890")
        self.assertIn("67890", bk_job_link)

        # 验证API调用参数
        self.mock_client.jobv3.execute_job_plan.assert_called_once()
        call_kwargs = self.mock_client.jobv3.execute_job_plan.call_args[1]
        self.assertEqual(call_kwargs["bk_scope_type"], "biz")
        self.assertEqual(call_kwargs["bk_scope_id"], self.bk_biz_id)
        self.assertEqual(call_kwargs["job_plan_id"], 2000)
        self.assertEqual(call_kwargs["callback_url"], "http://example.com/callback")

        # 验证全局变量
        global_var_list = call_kwargs["global_var_list"]
        var_names = {var["name"] for var in global_var_list}
        self.assertIn("host_list", var_names)
        self.assertIn("search_path", var_names)
        self.assertIn("suffix", var_names)
        self.assertIn("backup_path", var_names)

    def test_execute_backup_file_no_instance_id(self):
        """测试：执行备份作业未返回job_instance_id"""
        self.mock_client.jobv3.execute_job_plan.return_value = {"data": {}}

        with self.assertRaises(JobExecutionError) as context:
            self.service.execute_backup_file(
                host_id_list=[1001],
                search_path="/app/logs",
                suffix="log",
                backup_path="/backup",
                plan_id=2000,
                callback_url="http://example.com/callback",
            )

        self.assertIn("job_instance_id", str(context.exception))

    def test_execute_backup_file_api_exception(self):
        """测试：执行备份作业API调用异常（非JobExecutionError类型的异常被捕获并记录）"""
        self.mock_client.jobv3.execute_job_plan.side_effect = Exception("API Error")

        # 原始代码中，非JobExecutionError类型的异常只记录日志，不重新抛出
        # 所以这里不会抛出异常
        result = self.service.execute_backup_file(
            host_id_list=[1001],
            search_path="/app/logs",
            suffix="log",
            backup_path="/backup",
            plan_id=2000,
            callback_url="http://example.com/callback",
        )

        # 由于异常被捕获，函数返回None
        self.assertIsNone(result)


class TestBackupJobService(TestCase):
    """测试 BackupJobService 的业务逻辑"""

    def test_create_backup_job(self):
        """测试：创建备份作业记录"""
        job = BackupJobService.create_backup_job(
            job_instance_id="12345",
            operator="test_user",
            search_path="/app/logs",
            suffix="log",
            backup_path="/backup",
            bk_job_link="http://job.example.com/12345",
            host_count=10,
        )

        # 验证对象属性
        self.assertIsNotNone(job)
        self.assertEqual(job.job_instance_id, "12345")
        self.assertEqual(job.operator, "test_user")
        self.assertEqual(job.search_path, "/app/logs")
        self.assertEqual(job.suffix, "log")
        self.assertEqual(job.backup_path, "/backup")
        self.assertEqual(job.bk_job_link, "http://job.example.com/12345")
        self.assertEqual(job.status, BackupJob.Status.PENDING)
        self.assertEqual(job.host_count, 10)
        self.assertEqual(job.file_count, 0)

        # 验证数据库中存在
        self.assertTrue(BackupJob.objects.filter(job_instance_id="12345").exists())

    @patch("home_application.services.job.chain")
    def test_start_async_processing(self, mock_chain):
        """测试：启动异步任务链"""
        mock_chain_instance = MagicMock()
        mock_chain.return_value = mock_chain_instance

        BackupJobService.start_async_processing(
            job_instance_id="12345",
            host_id_list=[1001, 1002],
            bk_biz_id=3,
            bk_token="test_token",
        )

        # 验证chain被调用
        mock_chain.assert_called_once()
        mock_chain_instance.apply_async.assert_called_once()

    @patch("home_application.services.job.chain")
    @patch("home_application.services.job.logger")
    def test_start_async_processing_exception(self, mock_logger, mock_chain):
        """测试：启动异步任务链失败"""
        mock_chain.side_effect = Exception("Celery Error")

        # 不应该抛出异常，而是记录日志
        BackupJobService.start_async_processing(
            job_instance_id="12345",
            host_id_list=[1001, 1002],
            bk_biz_id=3,
            bk_token="test_token",
        )

        # 验证错误被记录
        mock_logger.error.assert_called_once()

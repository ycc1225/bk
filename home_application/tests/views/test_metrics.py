"""
指标推送模块测试
"""

from django.test import TestCase

from home_application.views.metrics import (
    celery_tasks_total,
    cmdb_sync_last_success,
    job_execution_status,
    push_last_success,
    registry,
    requests_errors_total,
    requests_total,
)


class TestMetricsModule(TestCase):
    """指标模块基础测试"""

    def test_registry_exists(self):
        """测试registry存在"""
        self.assertIsNotNone(registry)

    def test_metrics_defined(self):
        """测试所有指标已定义"""
        self.assertIsNotNone(requests_total)
        self.assertIsNotNone(requests_errors_total)
        self.assertIsNotNone(celery_tasks_total)
        self.assertIsNotNone(job_execution_status)
        self.assertIsNotNone(cmdb_sync_last_success)
        self.assertIsNotNone(push_last_success)


class TestMetricsOperations(TestCase):
    """指标操作测试"""

    def test_requests_total_increment(self):
        """测试请求计数器递增"""
        # 获取初始值
        before = requests_total.labels(method="GET", endpoint="/test")._value.get()

        # 递增计数器
        requests_total.labels(method="GET", endpoint="/test").inc()

        # 获取新值
        after = requests_total.labels(method="GET", endpoint="/test")._value.get()

        self.assertEqual(after - before, 1)

    def test_requests_errors_total_increment(self):
        """测试错误计数器递增"""
        requests_errors_total.labels(method="POST", endpoint="/api", status_code="500").inc()

        # 验证计数器已递增（不比较具体值，因为可能有之前的值）
        value = requests_errors_total.labels(method="POST", endpoint="/api", status_code="500")._value.get()
        self.assertGreaterEqual(value, 1)

    def test_celery_tasks_total_increment(self):
        """测试Celery任务计数器递增"""
        celery_tasks_total.labels(task_name="test_task", status="success").inc()

        value = celery_tasks_total.labels(task_name="test_task", status="success")._value.get()
        self.assertGreaterEqual(value, 1)

    def test_job_execution_status_set(self):
        """测试JOB执行状态gauge设置"""
        job_execution_status.labels(job_name="test_job").set(1)

        value = job_execution_status.labels(job_name="test_job")._value.get()
        self.assertEqual(value, 1)

    def test_cmdb_sync_last_success_set(self):
        """测试CMDB同步时间gauge设置"""
        test_timestamp = 1234567890
        cmdb_sync_last_success.labels(sync_type="full").set(test_timestamp)

        value = cmdb_sync_last_success.labels(sync_type="full")._value.get()
        self.assertEqual(value, test_timestamp)

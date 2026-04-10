"""
指标推送任务单元测试
"""

from datetime import date
from unittest.mock import patch

from django.test import TestCase

from home_application.models import ApiRequestCount
from home_application.tasks.metrics_push import (
    _collect_api_request_metrics,
    push_metrics_task,
)


class TestCollectApiRequestMetrics(TestCase):
    """测试 _collect_api_request_metrics"""

    @patch("home_application.tasks.metrics_push.date")
    def test_collect_metrics_success(self, mock_date):
        """测试：成功收集指标（不mock指标对象，只验证不抛出异常）"""
        mock_date.today.return_value = date(2024, 1, 15)

        # 创建测试数据
        ApiRequestCount.objects.create(
            api_category="backup", api_name="create", date=date(2024, 1, 15), request_count=100, error_count=5
        )

        # 执行收集（不验证具体调用，因为Counter是全局对象）
        try:
            _collect_api_request_metrics()
        except Exception as e:
            self.fail(f"_collect_api_request_metrics raised {e}")

    @patch("home_application.tasks.metrics_push.date")
    def test_collect_no_records(self, mock_date):
        """测试：当天没有记录"""
        mock_date.today.return_value = date(2024, 1, 15)

        # 不应该抛出异常
        try:
            _collect_api_request_metrics()
        except Exception as e:
            self.fail(f"_collect_api_request_metrics raised {e}")

    @patch("home_application.tasks.metrics_push.logger")
    def test_collect_exception(self, mock_logger):
        """测试：收集过程中出现异常"""
        # Mock查询抛出异常
        with patch.object(ApiRequestCount.objects, "filter", side_effect=Exception("DB Error")):
            _collect_api_request_metrics()

        # 验证错误被记录
        mock_logger.error.assert_called()


class TestPushMetricsTask(TestCase):
    """测试 push_metrics_task"""

    @patch("home_application.tasks.metrics_push._collect_api_request_metrics")
    @patch("home_application.views.metrics.push_metrics")
    def test_push_success(self, mock_push, mock_collect):
        """测试：成功推送指标"""
        mock_push.return_value = True

        result = push_metrics_task()

        mock_collect.assert_called_once()
        mock_push.assert_called_once()
        self.assertEqual(result, "指标推送成功")

    @patch("home_application.tasks.metrics_push._collect_api_request_metrics")
    @patch("home_application.views.metrics.push_metrics")
    def test_push_failure(self, mock_push, mock_collect):
        """测试：推送失败"""
        mock_push.return_value = False

        result = push_metrics_task()

        self.assertEqual(result, "指标推送失败，请检查日志")

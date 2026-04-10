"""
异常处理器单元测试
测试自定义异常处理逻辑
"""

from unittest.mock import MagicMock, patch

from django.test import TestCase

from home_application.exceptions.exception_handler import (
    _extract_error_message,
    custom_exception_handler,
)


class TestCustomExceptionHandler(TestCase):
    """测试自定义异常处理器"""

    @patch("home_application.exceptions.exception_handler.exception_handler")
    @patch("home_application.exceptions.exception_handler.trace")
    def test_handler_with_response(self, mock_trace, mock_drf_handler):
        """测试：处理有响应的异常"""
        # Mock DRF的异常处理器返回响应
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.data = {"detail": "Bad Request"}
        mock_drf_handler.return_value = mock_response

        # Mock trace
        mock_span = MagicMock()
        mock_span.get_span_context.return_value = MagicMock(trace_id=12345)
        mock_trace.get_current_span.return_value = mock_span

        # 创建模拟异常和上下文
        exc = Exception("Test exception")
        context = {"request": MagicMock(path="/test", method="GET")}

        response = custom_exception_handler(exc, context)

        # 验证响应被修改
        self.assertIsNotNone(response)
        mock_drf_handler.assert_called_once_with(exc, context)

    @patch("home_application.exceptions.exception_handler.exception_handler")
    def test_handler_without_response(self, mock_drf_handler):
        """测试：处理无响应的异常（DRF处理器返回None）"""
        mock_drf_handler.return_value = None

        exc = Exception("Test exception")
        context = {"request": MagicMock()}

        response = custom_exception_handler(exc, context)

        # 验证返回None
        self.assertIsNone(response)

    @patch("home_application.exceptions.exception_handler.exception_handler")
    @patch("home_application.exceptions.exception_handler.trace")
    def test_handler_with_extra_context(self, mock_trace, mock_drf_handler):
        """测试：异常带有extra_context属性"""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.data = {"detail": "Error"}
        mock_drf_handler.return_value = mock_response

        mock_span = MagicMock()
        mock_span.get_span_context.return_value = MagicMock(trace_id=12345)
        mock_trace.get_current_span.return_value = mock_span

        # 创建带extra_context的异常
        exc = Exception("Test")
        exc.extra_context = {"user_id": 123, "action": "test"}
        context = {"request": MagicMock(path="/api/test", method="POST")}

        response = custom_exception_handler(exc, context)

        self.assertIsNotNone(response)

    @patch("home_application.exceptions.exception_handler.exception_handler")
    @patch("home_application.exceptions.exception_handler.trace")
    def test_handler_without_request(self, mock_trace, mock_drf_handler):
        """测试：上下文没有request对象"""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.data = {"detail": "Server Error"}
        mock_drf_handler.return_value = mock_response

        mock_span = MagicMock()
        mock_span.get_span_context.return_value = MagicMock(trace_id=0)
        mock_trace.get_current_span.return_value = mock_span

        exc = Exception("Test")
        context = {}  # 没有request

        response = custom_exception_handler(exc, context)

        self.assertIsNotNone(response)


class TestExtractErrorMessage(TestCase):
    """测试错误消息提取函数"""

    def test_extract_dict_with_detail(self):
        """测试：提取包含detail的字典"""
        data = {"detail": "Not found"}
        result = _extract_error_message(data)
        self.assertEqual(result, "Not found")

    def test_extract_dict_with_field_errors(self):
        """测试：提取字段校验错误"""
        data = {
            "username": ["This field is required."],
            "email": ["Invalid email format.", "Email already exists."],
        }
        result = _extract_error_message(data)
        self.assertIn("username:", result)
        self.assertIn("email:", result)
        self.assertIn("This field is required", result)
        self.assertIn("Invalid email format", result)

    def test_extract_dict_with_non_list_field(self):
        """测试：字段值不是列表"""
        data = {"count": "Must be a positive integer"}
        result = _extract_error_message(data)
        self.assertEqual(result, "count: Must be a positive integer")

    def test_extract_list(self):
        """测试：提取列表数据"""
        data = ["Error 1", "Error 2", "Error 3"]
        result = _extract_error_message(data)
        self.assertEqual(result, "Error 1; Error 2; Error 3")

    def test_extract_string(self):
        """测试：提取字符串"""
        data = "Simple error message"
        result = _extract_error_message(data)
        self.assertEqual(result, "Simple error message")

    def test_extract_number(self):
        """测试：提取数字"""
        data = 404
        result = _extract_error_message(data)
        self.assertEqual(result, "404")

    def test_extract_empty_dict(self):
        """测试：空字典"""
        data = {}
        result = _extract_error_message(data)
        self.assertEqual(result, "")

    def test_extract_nested_dict(self):
        """测试：嵌套字典（会被转换为字符串）"""
        data = {"nested": {"key": "value"}}
        result = _extract_error_message(data)
        self.assertIn("nested:", result)

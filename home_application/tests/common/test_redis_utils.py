"""
Redis 工具函数单元测试
测试 API 统计和缓存功能
"""

from datetime import date
from unittest.mock import MagicMock, patch

from django.test import TestCase

import home_application.utils.redis_utils as redis_utils
from home_application.utils.redis_utils import (
    delete_redis_key,
    fetch_api_counts_and_rename,
    get_last_sync_time,
    get_redis_client,
    increment_api_count,
    set_last_sync_time,
)


class TestRedisUtils(TestCase):
    """测试 Redis 工具函数"""

    @patch("home_application.utils.redis_utils.redis.from_url")
    def test_get_redis_client_success(self, mock_from_url):
        """测试：成功获取 Redis 客户端"""
        mock_client = MagicMock()
        mock_from_url.return_value = mock_client

        # 重置全局变量
        redis_utils._redis_client = None

        client = get_redis_client()
        self.assertIsNotNone(client)
        self.assertEqual(client, mock_client)

    @patch("home_application.utils.redis_utils.redis.from_url")
    def test_get_redis_client_failure(self, mock_from_url):
        """测试：Redis 连接失败"""
        mock_from_url.side_effect = Exception("Connection failed")

        # 重置全局变量
        redis_utils._redis_client = None

        client = get_redis_client()
        self.assertIsNone(client)

    @patch("home_application.utils.redis_utils.get_redis_client")
    def test_increment_api_count_request(self, mock_get_client):
        """测试：增加 API 请求计数"""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        increment_api_count("cmdb", "search_biz", "2024-01-01", is_error=False)

        # 验证调用
        mock_client.hincrby.assert_called_once_with("bk_api_request_stats", "2024-01-01:cmdb:search_biz:req", 1)

    @patch("home_application.utils.redis_utils.get_redis_client")
    def test_increment_api_count_error(self, mock_get_client):
        """测试：增加 API 错误计数"""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        increment_api_count("cmdb", "search_biz", "2024-01-01", is_error=True)

        # 验证调用
        mock_client.hincrby.assert_called_once_with("bk_api_request_stats", "2024-01-01:cmdb:search_biz:err", 1)

    @patch("home_application.utils.redis_utils.get_redis_client")
    def test_increment_api_count_with_date_object(self, mock_get_client):
        """测试：使用 date 对象增加计数"""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        test_date = date(2024, 1, 1)
        increment_api_count("cmdb", "search_biz", test_date, is_error=False)

        # 验证调用
        mock_client.hincrby.assert_called_once_with("bk_api_request_stats", "2024-01-01:cmdb:search_biz:req", 1)

    @patch("home_application.utils.redis_utils.get_redis_client")
    def test_increment_api_count_no_client(self, mock_get_client):
        """测试：Redis 客户端不可用时不抛异常"""
        mock_get_client.return_value = None

        # 不应该抛异常
        increment_api_count("cmdb", "search_biz", "2024-01-01", is_error=False)

    @patch("home_application.utils.redis_utils.get_redis_client")
    def test_fetch_api_counts_and_rename_success(self, mock_get_client):
        """测试：成功获取并重命名 API 计数"""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # 模拟 Redis 数据
        mock_client.exists.return_value = True
        mock_client.hgetall.return_value = {
            b"2024-01-01:cmdb:search_biz:req": b"100",
            b"2024-01-01:cmdb:search_biz:err": b"5",
            b"2024-01-01:job:execute_plan:req": b"50",
        }

        data, temp_key = fetch_api_counts_and_rename()

        # 验证数据解析
        self.assertIn(("2024-01-01", "cmdb", "search_biz"), data)
        self.assertEqual(data[("2024-01-01", "cmdb", "search_biz")]["req"], 105)  # req + err
        self.assertEqual(data[("2024-01-01", "cmdb", "search_biz")]["err"], 5)

        self.assertIn(("2024-01-01", "job", "execute_plan"), data)
        self.assertEqual(data[("2024-01-01", "job", "execute_plan")]["req"], 50)
        self.assertEqual(data[("2024-01-01", "job", "execute_plan")]["err"], 0)

        # 验证 rename 被调用
        self.assertTrue(mock_client.rename.called)
        self.assertIsNotNone(temp_key)

    @patch("home_application.utils.redis_utils.get_redis_client")
    def test_fetch_api_counts_and_rename_no_data(self, mock_get_client):
        """测试：Redis 中没有数据"""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.exists.return_value = False

        data, temp_key = fetch_api_counts_and_rename()

        self.assertEqual(data, {})
        self.assertIsNone(temp_key)

    @patch("home_application.utils.redis_utils.get_redis_client")
    def test_delete_redis_key_success(self, mock_get_client):
        """测试：成功删除 Redis Key"""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        delete_redis_key("test_key")

        mock_client.delete.assert_called_once_with("test_key")

    @patch("home_application.utils.redis_utils.get_redis_client")
    def test_set_last_sync_time_success(self, mock_get_client):
        """测试：成功设置同步时间"""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        set_last_sync_time("2024-01-01 12:00:00")

        mock_client.set.assert_called_once_with("cmdb_last_sync_time", "2024-01-01 12:00:00")

    @patch("home_application.utils.redis_utils.get_redis_client")
    def test_get_last_sync_time_success(self, mock_get_client):
        """测试：成功获取同步时间"""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.get.return_value = b"2024-01-01 12:00:00"

        result = get_last_sync_time()

        self.assertEqual(result, "2024-01-01 12:00:00")
        mock_client.get.assert_called_once_with("cmdb_last_sync_time")

    @patch("home_application.utils.redis_utils.get_redis_client")
    def test_get_last_sync_time_no_data(self, mock_get_client):
        """测试：没有同步时间数据"""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.get.return_value = None

        result = get_last_sync_time()

        self.assertIsNone(result)

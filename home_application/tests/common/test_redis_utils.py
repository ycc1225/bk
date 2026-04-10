"""
Redis工具函数单元测试
"""

from unittest.mock import MagicMock, patch

from django.test import TestCase

from home_application.utils.redis_utils import (
    API_STATS_KEY,
    delete_redis_key,
    fetch_and_clear_api_counts,
    fetch_api_counts_and_rename,
    get_last_sync_time,
    get_redis_client,
    increment_api_count,
    set_last_sync_time,
)


class TestGetRedisClient(TestCase):
    """测试 get_redis_client 函数"""

    @patch("home_application.utils.redis_utils.redis.from_url")
    def test_get_client_success(self, mock_from_url):
        """测试：成功获取Redis客户端"""
        mock_client = MagicMock()
        mock_from_url.return_value = mock_client

        # 清空缓存
        import home_application.utils.redis_utils as redis_utils

        redis_utils._redis_client = None

        client = get_redis_client()

        self.assertIsNotNone(client)
        mock_from_url.assert_called_once()

    @patch("home_application.utils.redis_utils.redis.from_url")
    @patch("home_application.utils.redis_utils.logger")
    def test_get_client_failure(self, mock_logger, mock_from_url):
        """测试：获取Redis客户端失败"""
        mock_from_url.side_effect = Exception("Connection refused")

        # 清空缓存
        import home_application.utils.redis_utils as redis_utils

        redis_utils._redis_client = None

        client = get_redis_client()

        self.assertIsNone(client)
        mock_logger.error.assert_called_once()


class TestIncrementApiCount(TestCase):
    """测试 increment_api_count 函数"""

    @patch("home_application.utils.redis_utils.get_redis_client")
    def test_increment_success(self, mock_get_client):
        """测试：成功增加计数"""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        increment_api_count("backup", "create", "2024-01-01", is_error=False)

        mock_client.hincrby.assert_called_once_with(API_STATS_KEY, "2024-01-01:backup:create:req", 1)

    @patch("home_application.utils.redis_utils.get_redis_client")
    def test_increment_error(self, mock_get_client):
        """测试：增加错误计数"""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        increment_api_count("backup", "create", "2024-01-01", is_error=True)

        mock_client.hincrby.assert_called_once_with(API_STATS_KEY, "2024-01-01:backup:create:err", 1)

    @patch("home_application.utils.redis_utils.get_redis_client")
    def test_increment_no_client(self, mock_get_client):
        """测试：Redis客户端不可用"""
        mock_get_client.return_value = None

        # 不应该抛出异常
        increment_api_count("backup", "create", "2024-01-01")


class TestFetchApiCountsAndRename(TestCase):
    """测试 fetch_api_counts_and_rename 函数"""

    @patch("home_application.utils.redis_utils.get_redis_client")
    def test_fetch_key_not_exists(self, mock_get_client):
        """测试：key不存在"""
        mock_client = MagicMock()
        mock_client.exists.return_value = False
        mock_get_client.return_value = mock_client

        data, temp_key = fetch_api_counts_and_rename()

        self.assertEqual(data, {})
        self.assertIsNone(temp_key)

    @patch("home_application.utils.redis_utils.get_redis_client")
    def test_fetch_no_client(self, mock_get_client):
        """测试：没有Redis客户端"""
        mock_get_client.return_value = None

        data, temp_key = fetch_api_counts_and_rename()

        self.assertEqual(data, {})
        self.assertIsNone(temp_key)


class TestDeleteRedisKey(TestCase):
    """测试 delete_redis_key 函数"""

    @patch("home_application.utils.redis_utils.get_redis_client")
    def test_delete_success(self, mock_get_client):
        """测试：成功删除key"""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        delete_redis_key("test_key")

        mock_client.delete.assert_called_once_with("test_key")

    @patch("home_application.utils.redis_utils.get_redis_client")
    def test_delete_no_client(self, mock_get_client):
        """测试：没有Redis客户端"""
        mock_get_client.return_value = None

        # 不应该抛出异常
        delete_redis_key("test_key")

    @patch("home_application.utils.redis_utils.get_redis_client")
    def test_delete_no_key(self, mock_get_client):
        """测试：key为None"""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        delete_redis_key(None)

        mock_client.delete.assert_not_called()


class TestSetAndGetLastSyncTime(TestCase):
    """测试设置和获取同步时间"""

    @patch("home_application.utils.redis_utils.get_redis_client")
    def test_set_and_get(self, mock_get_client):
        """测试：设置和获取同步时间"""
        mock_client = MagicMock()
        mock_client.get.return_value = b"2024-01-01 12:00:00"
        mock_get_client.return_value = mock_client

        set_last_sync_time("2024-01-01 12:00:00")
        result = get_last_sync_time()

        self.assertEqual(result, "2024-01-01 12:00:00")

    @patch("home_application.utils.redis_utils.get_redis_client")
    def test_get_no_value(self, mock_get_client):
        """测试：获取不存在的值"""
        mock_client = MagicMock()
        mock_client.get.return_value = None
        mock_get_client.return_value = mock_client

        result = get_last_sync_time()

        self.assertIsNone(result)


class TestFetchAndClearApiCounts(TestCase):
    """测试 fetch_and_clear_api_counts 函数（已弃用但仍需测试）"""

    @patch("home_application.utils.redis_utils.fetch_api_counts_and_rename")
    @patch("home_application.utils.redis_utils.delete_redis_key")
    def test_fetch_and_clear(self, mock_delete, mock_fetch):
        """测试：获取并清除计数"""
        mock_fetch.return_value = ({"data": "test"}, "temp_key_123")

        result = fetch_and_clear_api_counts()

        self.assertEqual(result, {"data": "test"})
        mock_delete.assert_called_once_with("temp_key_123")

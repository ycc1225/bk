"""
主机管理相关的序列化器单元测试
测试参数校验逻辑
"""

from django.test import TestCase

from home_application.serializers.cmdb import (
    HostDetailQuerySerializer,
    HostListQuerySerializer,
)


class TestHostListQuerySerializer(TestCase):
    """测试主机列表查询参数校验"""

    def test_valid_minimal_data(self):
        """测试：最小有效参数（只有 bk_biz_id）"""
        data = {"bk_biz_id": 1}
        serializer = HostListQuerySerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["bk_biz_id"], 1)
        self.assertEqual(serializer.validated_data["page"], 1)  # 默认值
        self.assertEqual(serializer.validated_data["page_size"], 10)  # 默认值

    def test_valid_full_data(self):
        """测试：完整的有效参数"""
        data = {
            "bk_biz_id": 1,
            "bk_set_id": 10,
            "bk_module_id": 100,
            "bk_host_id": 1001,
            "bk_host_innerip": "192.168.1.1",
            "operator": "admin",
            "page": 2,
            "page_size": 20,
        }
        serializer = HostListQuerySerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["bk_biz_id"], 1)
        self.assertEqual(serializer.validated_data["page"], 2)
        self.assertEqual(serializer.validated_data["page_size"], 20)

    def test_missing_bk_biz_id(self):
        """测试：缺少必填参数 bk_biz_id"""
        data = {"page": 1}
        serializer = HostListQuerySerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("bk_biz_id", serializer.errors)

    def test_invalid_bk_biz_id_negative(self):
        """测试：bk_biz_id 为负数"""
        data = {"bk_biz_id": -1}
        serializer = HostListQuerySerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("bk_biz_id", serializer.errors)

    def test_invalid_bk_biz_id_zero(self):
        """测试：bk_biz_id 为 0"""
        data = {"bk_biz_id": 0}
        serializer = HostListQuerySerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("bk_biz_id", serializer.errors)

    def test_invalid_page_zero(self):
        """测试：page 为 0"""
        data = {"bk_biz_id": 1, "page": 0}
        serializer = HostListQuerySerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("page", serializer.errors)

    def test_invalid_page_size_too_large(self):
        """测试：page_size 超过最大值"""
        data = {"bk_biz_id": 1, "page_size": 101}
        serializer = HostListQuerySerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("page_size", serializer.errors)

    def test_type_conversion(self):
        """测试：字符串自动转换为整数"""
        data = {"bk_biz_id": "1", "page": "2", "page_size": "20"}
        serializer = HostListQuerySerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["bk_biz_id"], 1)
        self.assertEqual(serializer.validated_data["page"], 2)
        self.assertEqual(serializer.validated_data["page_size"], 20)


class TestHostDetailQuerySerializer(TestCase):
    """测试主机详情查询参数校验"""

    def test_valid_data(self):
        """测试：有效的参数"""
        data = {"bk_host_id": 1001}
        serializer = HostDetailQuerySerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["bk_host_id"], 1001)

    def test_missing_bk_host_id(self):
        """测试：缺少必填参数"""
        data = {}
        serializer = HostDetailQuerySerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("bk_host_id", serializer.errors)

    def test_invalid_bk_host_id_negative(self):
        """测试：bk_host_id 为负数"""
        data = {"bk_host_id": -1}
        serializer = HostDetailQuerySerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("bk_host_id", serializer.errors)

    def test_type_conversion(self):
        """测试：字符串自动转换为整数"""
        data = {"bk_host_id": "1001"}
        serializer = HostDetailQuerySerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["bk_host_id"], 1001)

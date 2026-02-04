"""
CMDB 相关的序列化器单元测试
测试参数校验逻辑
"""

from django.test import TestCase

from home_application.serializers.cmdb import (
    ModuleInfoQuerySerializer,
    SetInfoQuerySerializer,
)


class TestSetInfoQuerySerializer(TestCase):
    """测试集群信息查询参数校验"""

    def test_valid_data(self):
        """测试：有效的参数"""
        data = {"bk_biz_id": 1}
        serializer = SetInfoQuerySerializer(data=data)
        self.assertTrue(serializer.is_valid())

    def test_missing_bk_biz_id(self):
        """测试：缺少必填参数"""
        data = {}
        serializer = SetInfoQuerySerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("bk_biz_id", serializer.errors)

    def test_invalid_bk_biz_id(self):
        """测试：bk_biz_id 为 0"""
        data = {"bk_biz_id": 0}
        serializer = SetInfoQuerySerializer(data=data)
        self.assertFalse(serializer.is_valid())


class TestModuleInfoQuerySerializer(TestCase):
    """测试模块信息查询参数校验"""

    def test_valid_data(self):
        """测试：有效的参数"""
        data = {"bk_biz_id": 1, "bk_set_id": 10}
        serializer = ModuleInfoQuerySerializer(data=data)
        self.assertTrue(serializer.is_valid())

    def test_missing_bk_biz_id(self):
        """测试：缺少 bk_biz_id"""
        data = {"bk_set_id": 10}
        serializer = ModuleInfoQuerySerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("bk_biz_id", serializer.errors)

    def test_missing_bk_set_id(self):
        """测试：缺少 bk_set_id"""
        data = {"bk_biz_id": 1}
        serializer = ModuleInfoQuerySerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("bk_set_id", serializer.errors)

    def test_both_fields_invalid(self):
        """测试：两个字段都无效"""
        data = {"bk_biz_id": 0, "bk_set_id": -1}
        serializer = ModuleInfoQuerySerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("bk_biz_id", serializer.errors)
        self.assertIn("bk_set_id", serializer.errors)

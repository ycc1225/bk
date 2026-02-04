"""
Job 备份相关的序列化器单元测试
测试参数校验逻辑
"""

from django.test import TestCase

from home_application.serializers.job import (
    BackupJobSubmitSerializer,
    SearchFileSubmitSerializer,
)


class TestBackupJobSubmitSerializer(TestCase):
    """测试备份作业提交参数校验"""

    def test_valid_data(self):
        """测试：有效的参数"""
        data = {
            "search_path": "/project",
            "suffix": "log",
            "backup_path": "/project",
            "host_list": [1001, 1002, 1003],
        }
        serializer = BackupJobSubmitSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["search_path"], "/project")
        self.assertEqual(serializer.validated_data["host_list"], [1001, 1002, 1003])

    def test_missing_required_field(self):
        """测试：缺少必填字段"""
        data = {
            "search_path": "/project",
            "suffix": "log",
            # 缺少 backup_path
            "host_list": [1001],
        }
        serializer = BackupJobSubmitSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("backup_path", serializer.errors)

    def test_invalid_suffix(self):
        """测试：不合法的文件后缀"""
        data = {
            "search_path": "/project",
            "suffix": "exe",  # 不在允许列表中
            "backup_path": "/project",
            "host_list": [1001],
        }
        serializer = BackupJobSubmitSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("suffix", serializer.errors)

    def test_invalid_search_path_with_double_dots(self):
        """测试：搜索路径包含 '..'"""
        data = {
            "search_path": "/data/../etc",  # 包含 ..
            "suffix": "log",
            "backup_path": "/project",
            "host_list": [1001],
        }
        serializer = BackupJobSubmitSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("search_path", serializer.errors)

    def test_invalid_search_path_prefix(self):
        """测试：搜索路径不以允许的前缀开头"""
        data = {
            "search_path": "/etc/passwd",  # 不以允许的前缀开头
            "suffix": "log",
            "backup_path": "/project",
            "host_list": [1001],
        }
        serializer = BackupJobSubmitSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("search_path", serializer.errors)

    def test_invalid_backup_path_with_double_dots(self):
        """测试：备份路径包含 '..'"""
        data = {
            "search_path": "/project",
            "suffix": "log",
            "backup_path": "/data/../backup",  # 包含 ..
            "host_list": [1001],
        }
        serializer = BackupJobSubmitSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("backup_path", serializer.errors)

    def test_empty_host_list(self):
        """测试：主机列表为空"""
        data = {
            "search_path": "/project",
            "suffix": "log",
            "backup_path": "/project",
            "host_list": [],  # 空列表
        }
        serializer = BackupJobSubmitSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("host_list", serializer.errors)

    def test_invalid_host_id_negative(self):
        """测试：主机ID为负数"""
        data = {
            "search_path": "/project",
            "suffix": "log",
            "backup_path": "/project",
            "host_list": [1001, -1],  # 负数
        }
        serializer = BackupJobSubmitSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("host_list", serializer.errors)

    def test_invalid_host_id_zero(self):
        """测试：主机ID为0"""
        data = {
            "search_path": "/project",
            "suffix": "log",
            "backup_path": "/project",
            "host_list": [0],  # 0
        }
        serializer = BackupJobSubmitSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("host_list", serializer.errors)

    def test_too_many_hosts(self):
        """测试：主机数量超过限制"""
        data = {
            "search_path": "/project",
            "suffix": "log",
            "backup_path": "/project",
            "host_list": list(range(1, 102)),  # 101个主机，超过100
        }
        serializer = BackupJobSubmitSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("host_list", serializer.errors)


class TestSearchFileSubmitSerializer(TestCase):
    """测试搜索文件提交参数校验"""

    def test_valid_data(self):
        """测试：有效的参数"""
        data = {
            "search_path": "/project",
            "suffix": "log",
            "host_list": [1001, 1002],
        }
        serializer = SearchFileSubmitSerializer(data=data)
        self.assertTrue(serializer.is_valid())

    def test_missing_suffix(self):
        """测试：缺少文件后缀"""
        data = {
            "search_path": "/project",
            "host_list": [1001],
        }
        serializer = SearchFileSubmitSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("suffix", serializer.errors)

    def test_invalid_suffix(self):
        """测试：不合法的文件后缀"""
        data = {
            "search_path": "/project",
            "suffix": "sh",  # 不在允许列表中
            "host_list": [1001],
        }
        serializer = SearchFileSubmitSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("suffix", serializer.errors)

    def test_invalid_search_path(self):
        """测试：不合法的搜索路径"""
        data = {
            "search_path": "/tmp/logs",  # 不以允许的前缀开头
            "suffix": "log",
            "host_list": [1001],
        }
        serializer = SearchFileSubmitSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("search_path", serializer.errors)

"""
CMDB 相关的模型单元测试
测试 BizInfo, SetInfo, ModuleInfo, SyncStatus 模型
"""

from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from home_application.models import BizInfo, ModuleInfo, SetInfo, SyncStatus


class TestSyncStatusModel(TestCase):
    """测试 SyncStatus 模型的状态管理方法"""

    def setUp(self):
        """每个测试前创建测试数据"""
        self.sync_status = SyncStatus.objects.create(
            name="test_sync", last_status="pending", last_error=None, last_sync_at=None
        )

    def test_mark_success(self):
        """测试：标记同步成功"""
        before_time = timezone.now()
        self.sync_status.mark_success()
        self.sync_status.refresh_from_db()

        self.assertEqual(self.sync_status.last_status, "success")
        self.assertIsNone(self.sync_status.last_error)
        self.assertIsNotNone(self.sync_status.last_sync_at)
        self.assertGreaterEqual(self.sync_status.last_sync_at, before_time)

    def test_mark_running(self):
        """测试：标记同步运行中"""
        before_time = timezone.now()
        self.sync_status.mark_running()
        self.sync_status.refresh_from_db()

        self.assertEqual(self.sync_status.last_status, "running")
        self.assertGreaterEqual(self.sync_status.updated_at, before_time)

    def test_mark_failed(self):
        """测试：标记同步失败"""
        error_message = "Connection timeout"
        before_time = timezone.now()

        self.sync_status.mark_failed(error_message)
        self.sync_status.refresh_from_db()

        self.assertEqual(self.sync_status.last_status, "failed")
        self.assertEqual(self.sync_status.last_error, error_message)
        self.assertGreaterEqual(self.sync_status.updated_at, before_time)

    def test_mark_failed_with_long_error(self):
        """测试：标记失败时错误信息过长会被截断"""
        long_error = "x" * 3000  # 超过 2000 字符
        self.sync_status.mark_failed(long_error)
        self.sync_status.refresh_from_db()

        self.assertEqual(self.sync_status.last_status, "failed")
        self.assertEqual(len(self.sync_status.last_error), 2000)  # 被截断到 2000

    def test_sync_flow_pending_to_running_to_success(self):
        """测试：完整的同步流程 pending -> running -> success"""
        # 初始状态
        self.assertEqual(self.sync_status.last_status, "pending")

        # 标记为运行中
        self.sync_status.mark_running()
        self.sync_status.refresh_from_db()
        self.assertEqual(self.sync_status.last_status, "running")

        # 标记为成功
        self.sync_status.mark_success()
        self.sync_status.refresh_from_db()
        self.assertEqual(self.sync_status.last_status, "success")
        self.assertIsNone(self.sync_status.last_error)

    def test_unique_name_constraint(self):
        """测试：name 字段的唯一性约束"""
        with self.assertRaises(IntegrityError):
            SyncStatus.objects.create(name="test_sync", last_status="pending")


class TestBizInfoModel(TestCase):
    """测试 BizInfo 模型"""

    def test_create_biz_info(self):
        """测试：创建业务信息"""
        biz = BizInfo.objects.create(bk_biz_id=1, bk_biz_name="测试业务")
        self.assertEqual(biz.bk_biz_id, 1)
        self.assertEqual(biz.bk_biz_name, "测试业务")

    def test_unique_bk_biz_id(self):
        """测试：bk_biz_id 唯一性约束"""
        BizInfo.objects.create(bk_biz_id=1, bk_biz_name="业务1")
        with self.assertRaises(IntegrityError):
            BizInfo.objects.create(bk_biz_id=1, bk_biz_name="业务2")


class TestSetInfoModel(TestCase):
    """测试 SetInfo 模型"""

    def setUp(self):
        """创建测试数据"""
        self.biz = BizInfo.objects.create(bk_biz_id=1, bk_biz_name="测试业务")

    def test_create_set_info(self):
        """测试：创建集群信息"""
        set_info = SetInfo.objects.create(bk_set_id=10, bk_set_name="测试集群", bk_biz_id=1)
        self.assertEqual(set_info.bk_set_id, 10)
        self.assertEqual(set_info.bk_set_name, "测试集群")
        self.assertEqual(set_info.bk_biz_id, 1)


class TestModuleInfoModel(TestCase):
    """测试 ModuleInfo 模型"""

    def setUp(self):
        """创建测试数据"""
        self.biz = BizInfo.objects.create(bk_biz_id=1, bk_biz_name="测试业务")
        self.set_info = SetInfo.objects.create(bk_set_id=10, bk_set_name="测试集群", bk_biz_id=1)

    def test_create_module_info(self):
        """测试：创建模块信息"""
        module = ModuleInfo.objects.create(bk_module_id=100, bk_module_name="测试模块", bk_set_id=10, bk_biz_id=1)
        self.assertEqual(module.bk_module_id, 100)
        self.assertEqual(module.bk_module_name, "测试模块")
        self.assertEqual(module.bk_set_id, 10)
        self.assertEqual(module.bk_biz_id, 1)

"""
Job 备份相关的模型单元测试
测试 BackupJob 和 BackupRecord 模型的核心方法
"""

from django.test import TestCase

from home_application.models import BackupJob, BackupRecord


class TestBackupJobModel(TestCase):
    """测试 BackupJob 模型的状态流转方法"""

    def setUp(self):
        """每个测试前创建测试数据"""
        self.backup_job = BackupJob.objects.create(
            job_instance_id="12345",
            operator="test_user",
            search_path="/project/logs",
            suffix="log",
            backup_path="/project/backup",
            bk_job_link="http://job.example.com/12345",
            status=BackupJob.Status.PENDING,
            host_count=5,
            file_count=0,
        )

    def test_initial_status_is_pending(self):
        """测试：初始状态应该是 pending"""
        self.assertEqual(self.backup_job.status, BackupJob.Status.PENDING)

    def test_mark_processing(self):
        """测试：标记为处理中"""
        self.backup_job.mark_processing()
        self.backup_job.refresh_from_db()
        self.assertEqual(self.backup_job.status, BackupJob.Status.PROCESSING)

    def test_mark_success_without_file_count(self):
        """测试：标记为成功（不更新文件数）"""
        self.backup_job.mark_success()
        self.backup_job.refresh_from_db()
        self.assertEqual(self.backup_job.status, BackupJob.Status.SUCCESS)
        self.assertEqual(self.backup_job.file_count, 0)  # 未更新

    def test_mark_success_with_file_count(self):
        """测试：标记为成功（更新文件数）"""
        self.backup_job.mark_success(file_count=100)
        self.backup_job.refresh_from_db()
        self.assertEqual(self.backup_job.status, BackupJob.Status.SUCCESS)
        self.assertEqual(self.backup_job.file_count, 100)

    def test_mark_failed(self):
        """测试：标记为失败"""
        self.backup_job.mark_failed()
        self.backup_job.refresh_from_db()
        self.assertEqual(self.backup_job.status, BackupJob.Status.FAILED)

    def test_mark_partial_without_file_count(self):
        """测试：标记为部分成功（不更新文件数）"""
        self.backup_job.mark_partial()
        self.backup_job.refresh_from_db()
        self.assertEqual(self.backup_job.status, BackupJob.Status.PARTIAL)
        self.assertEqual(self.backup_job.file_count, 0)

    def test_mark_partial_with_file_count(self):
        """测试：标记为部分成功（更新文件数）"""
        self.backup_job.mark_partial(file_count=50)
        self.backup_job.refresh_from_db()
        self.assertEqual(self.backup_job.status, BackupJob.Status.PARTIAL)
        self.assertEqual(self.backup_job.file_count, 50)

    def test_status_flow_pending_to_processing_to_success(self):
        """测试：完整的状态流转 pending -> processing -> success"""
        # 初始状态
        self.assertEqual(self.backup_job.status, BackupJob.Status.PENDING)

        # 标记为处理中
        self.backup_job.mark_processing()
        self.backup_job.refresh_from_db()
        self.assertEqual(self.backup_job.status, BackupJob.Status.PROCESSING)

        # 标记为成功
        self.backup_job.mark_success(file_count=200)
        self.backup_job.refresh_from_db()
        self.assertEqual(self.backup_job.status, BackupJob.Status.SUCCESS)
        self.assertEqual(self.backup_job.file_count, 200)

    def test_backup_records_relationship(self):
        """测试：BackupJob 与 BackupRecord 的关联关系"""
        # 创建备份记录
        BackupRecord.objects.create(
            backup_job=self.backup_job, bk_host_id=1001, status="success", bk_backup_name="/backup/file1.log"
        )
        BackupRecord.objects.create(
            backup_job=self.backup_job, bk_host_id=1002, status="success", bk_backup_name="/backup/file2.log"
        )

        # 验证关联
        self.assertEqual(self.backup_job.records.count(), 2)
        self.assertEqual(self.backup_job.records.filter(status="success").count(), 2)

    def test_backup_job_ordering(self):
        """测试：BackupJob 按 ID 倒序排列"""
        job2 = BackupJob.objects.create(
            job_instance_id="67890",
            operator="test_user",
            search_path="/project/logs",
            suffix="log",
            backup_path="/project/backup",
            bk_job_link="http://job.example.com/67890",
        )

        jobs = list(BackupJob.objects.all())
        self.assertEqual(jobs[0].id, job2.id)  # 最新的在前面
        self.assertEqual(jobs[1].id, self.backup_job.id)

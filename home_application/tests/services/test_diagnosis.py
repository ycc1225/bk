"""
DiagnosisService 单元测试
测试备份失败诊断服务的业务逻辑
"""

from django.test import TestCase

from home_application.models import BackupJob, BackupRecord, DiagnosisRecord
from home_application.services.diagnosis import DiagnosisService


class TestDiagnosisService(TestCase):
    """测试 DiagnosisService 的诊断逻辑"""

    def setUp(self):
        """测试前置准备"""
        self.service = DiagnosisService()

        # 创建一个失败的备份作业
        self.failed_job = BackupJob.objects.create(
            job_instance_id="job_001",
            operator="test_user",
            search_path="/app/logs",
            suffix="log",
            backup_path="/backup",
            bk_job_link="http://job.example.com/001",
            status=BackupJob.Status.FAILED,
            host_count=3,
        )

        # 创建失败的备份记录
        self.record1 = BackupRecord.objects.create(
            backup_job=self.failed_job,
            bk_host_id=1001,
            status="failed",
            bk_backup_name="permission denied: cannot access /app/logs",
        )
        self.record2 = BackupRecord.objects.create(
            backup_job=self.failed_job,
            bk_host_id=1002,
            status="failed",
            bk_backup_name="no space left on device",
        )
        self.record3 = BackupRecord.objects.create(
            backup_job=self.failed_job,
            bk_host_id=1003,
            status="success",
            bk_backup_name="backup_success.log",
        )

    def test_diagnose_backup_job_success(self):
        """测试：成功诊断失败的备份作业"""
        diagnosis = self.service.diagnose_backup_job(self.failed_job)

        # 验证诊断记录已创建
        self.assertIsNotNone(diagnosis)
        self.assertIsInstance(diagnosis, DiagnosisRecord)
        self.assertEqual(diagnosis.backup_job, self.failed_job)

        # 验证主要失败类型（出现次数最多的）
        # 由于每条记录匹配不同类别，需要看具体规则
        self.assertIn(diagnosis.top_category, [c[0] for c in DiagnosisRecord.FailureCategory.choices])

        # 验证摘要中包含主机数量
        self.assertIn("2 台主机备份失败", diagnosis.summary)

        # 验证详细信息
        self.assertIn("category_counter", diagnosis.detail)
        self.assertIn("host_diagnoses", diagnosis.detail)

    def test_diagnose_success_job(self):
        """测试：成功的作业不需要诊断"""
        success_job = BackupJob.objects.create(
            job_instance_id="job_002",
            operator="test_user",
            search_path="/app/logs",
            suffix="log",
            backup_path="/backup",
            bk_job_link="http://job.example.com/002",
            status=BackupJob.Status.SUCCESS,
            host_count=1,
        )

        result = self.service.diagnose_backup_job(success_job)
        self.assertIsNone(result)

    def test_diagnose_duplicate(self):
        """测试：重复诊断应该返回已有记录"""
        # 第一次诊断
        first_diagnosis = self.service.diagnose_backup_job(self.failed_job)
        self.assertIsNotNone(first_diagnosis)

        # 第二次诊断应该返回已有记录
        second_diagnosis = self.service.diagnose_backup_job(self.failed_job)
        self.assertEqual(first_diagnosis.id, second_diagnosis.id)

    def test_diagnose_no_failed_records(self):
        """测试：没有失败记录时跳过诊断"""
        failed_job_no_records = BackupJob.objects.create(
            job_instance_id="job_003",
            operator="test_user",
            search_path="/app/logs",
            suffix="log",
            backup_path="/backup",
            bk_job_link="http://job.example.com/003",
            status=BackupJob.Status.FAILED,
            host_count=1,
        )
        # 不创建任何失败记录

        result = self.service.diagnose_backup_job(failed_job_no_records)
        self.assertIsNone(result)


class TestMatchRule(TestCase):
    """测试诊断规则匹配逻辑"""

    def test_match_permission_denied(self):
        """测试：匹配权限不足"""
        category, suggestion = DiagnosisService.match_rule("Error: permission denied when accessing /var/log")
        self.assertEqual(category, DiagnosisRecord.FailureCategory.PERMISSION_DENIED)
        self.assertIn("权限", suggestion)

    def test_match_disk_full(self):
        """测试：匹配磁盘满"""
        category, suggestion = DiagnosisService.match_rule("Fatal: no space left on device /backup")
        self.assertEqual(category, DiagnosisRecord.FailureCategory.DISK_FULL)
        self.assertIn("磁盘", suggestion)

    def test_match_path_not_found(self):
        """测试：匹配路径不存在"""
        category, suggestion = DiagnosisService.match_rule("Error: no such file or directory: /app/notexist")
        self.assertEqual(category, DiagnosisRecord.FailureCategory.PATH_NOT_FOUND)
        self.assertIn("路径", suggestion)

    def test_match_timeout(self):
        """测试：匹配超时"""
        category, suggestion = DiagnosisService.match_rule("Job execution timeout after 300 seconds")
        self.assertEqual(category, DiagnosisRecord.FailureCategory.TIMEOUT)
        self.assertIn("超时", suggestion)

    def test_match_agent_offline(self):
        """测试：匹配Agent离线"""
        category, suggestion = DiagnosisService.match_rule("Error: gse agent is not available")
        self.assertEqual(category, DiagnosisRecord.FailureCategory.AGENT_OFFLINE)
        self.assertIn("Agent", suggestion)

    def test_match_network_error(self):
        """测试：匹配网络错误"""
        category, suggestion = DiagnosisService.match_rule("Connection refused by target host")
        self.assertEqual(category, DiagnosisRecord.FailureCategory.NETWORK_ERROR)
        self.assertIn("网络", suggestion)

    def test_match_unknown(self):
        """测试：未知错误类型"""
        category, suggestion = DiagnosisService.match_rule("Some random error message")
        self.assertEqual(category, DiagnosisRecord.FailureCategory.UNKNOWN)
        self.assertIn("无法自动识别", suggestion)

    def test_match_empty_content(self):
        """测试：空日志内容"""
        category, suggestion = DiagnosisService.match_rule("")
        self.assertEqual(category, DiagnosisRecord.FailureCategory.UNKNOWN)
        self.assertIn("日志内容为空", suggestion)

        category, suggestion = DiagnosisService.match_rule(None)
        self.assertEqual(category, DiagnosisRecord.FailureCategory.UNKNOWN)

    def test_match_case_insensitive(self):
        """测试：关键词匹配不区分大小写"""
        category, suggestion = DiagnosisService.match_rule("ERROR: PERMISSION DENIED")
        self.assertEqual(category, DiagnosisRecord.FailureCategory.PERMISSION_DENIED)

        category, suggestion = DiagnosisService.match_rule("Disk FULL Error")
        self.assertEqual(category, DiagnosisRecord.FailureCategory.DISK_FULL)

    def test_match_chinese_keywords(self):
        """测试：中文关键词匹配"""
        category, suggestion = DiagnosisService.match_rule("错误：磁盘满，无法写入")
        self.assertEqual(category, DiagnosisRecord.FailureCategory.DISK_FULL)

        category, suggestion = DiagnosisService.match_rule("失败：路径不存在")
        self.assertEqual(category, DiagnosisRecord.FailureCategory.PATH_NOT_FOUND)


class TestGetSuggestionForCategory(TestCase):
    """测试获取修复建议"""

    def test_get_suggestion_permission_denied(self):
        """测试：获取权限不足的建议"""
        suggestion = DiagnosisService._get_suggestion_for_category(DiagnosisRecord.FailureCategory.PERMISSION_DENIED)
        self.assertIn("权限", suggestion)

    def test_get_suggestion_disk_full(self):
        """测试：获取磁盘满的建议"""
        suggestion = DiagnosisService._get_suggestion_for_category(DiagnosisRecord.FailureCategory.DISK_FULL)
        self.assertIn("磁盘", suggestion)

    def test_get_suggestion_unknown(self):
        """测试：获取未知类型的建议"""
        suggestion = DiagnosisService._get_suggestion_for_category("nonexistent_category")
        self.assertIn("JOB 平台", suggestion)


class TestBuildSummary(TestCase):
    """测试生成诊断摘要"""

    def test_build_summary_single_category(self):
        """测试：单一失败类型摘要"""
        category_counter = {
            DiagnosisRecord.FailureCategory.PERMISSION_DENIED: 3,
        }
        summary = DiagnosisService._build_summary(category_counter)

        self.assertIn("共 3 台主机备份失败", summary)
        self.assertIn("权限不足", summary)
        self.assertIn("3 台", summary)

    def test_build_summary_multiple_categories(self):
        """测试：多种失败类型摘要"""
        category_counter = {
            DiagnosisRecord.FailureCategory.PERMISSION_DENIED: 5,
            DiagnosisRecord.FailureCategory.DISK_FULL: 3,
            DiagnosisRecord.FailureCategory.UNKNOWN: 1,
        }
        summary = DiagnosisService._build_summary(category_counter)

        self.assertIn("共 9 台主机备份失败", summary)
        # 验证按数量排序
        lines = summary.split("\n")
        # 第一行是总数
        self.assertIn("9 台", lines[0])

    def test_build_summary_empty(self):
        """测试：空计数器"""
        category_counter = {}
        summary = DiagnosisService._build_summary(category_counter)

        self.assertIn("共 0 台主机备份失败", summary)

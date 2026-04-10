"""
Backup视图单元测试
"""

from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from home_application.models import BackupJob, BackupRecord, UserRole
from home_application.views.backup import BackupJobDetailAPIView, BackupJobListAPIView

User = get_user_model()


class TestBackupJobListAPIView(TestCase):
    """测试 BackupJobListAPIView"""

    def setUp(self):
        self.factory = RequestFactory()
        self.view = BackupJobListAPIView.as_view()
        self.user = User.objects.create_user(username="testuser")
        UserRole.objects.create(username="testuser", role="dev")

        # 创建测试数据
        for i in range(5):
            BackupJob.objects.create(
                job_instance_id=f"job_{i}",
                operator="testuser" if i % 2 == 0 else "other",
                search_path="/app",
                suffix="log",
                backup_path="/backup",
                bk_job_link=f"http://example.com/{i}",
                status=BackupJob.Status.SUCCESS if i < 3 else BackupJob.Status.FAILED,
            )

    def test_list_all_jobs(self):
        """测试：获取所有作业列表"""
        request = self.factory.get("/backup/")
        request.user = self.user

        response = self.view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["data"]), 5)
        self.assertIn("pagination", response.data)

    def test_list_with_status_filter(self):
        """测试：按状态过滤"""
        request = self.factory.get("/backup/", {"status": "success"})
        request.user = self.user

        response = self.view(request)

        self.assertEqual(response.status_code, 200)
        # 只有3个成功的作业
        self.assertEqual(len(response.data["data"]), 3)

    def test_list_with_operator_filter(self):
        """测试：按操作人过滤"""
        request = self.factory.get("/backup/", {"operator": "testuser"})
        request.user = self.user

        response = self.view(request)

        self.assertEqual(response.status_code, 200)
        # 3个testuser的作业
        self.assertEqual(len(response.data["data"]), 3)

    def test_list_with_time_range(self):
        """测试：按时间范围过滤"""
        start_time = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        end_time = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")

        request = self.factory.get("/backup/", {"created_at_start": start_time, "created_at_end": end_time})
        request.user = self.user

        response = self.view(request)

        self.assertEqual(response.status_code, 200)

    def test_list_pagination(self):
        """测试：分页功能"""
        request = self.factory.get("/backup/", {"page": 1, "page_size": 2})
        request.user = self.user

        response = self.view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["data"]), 2)
        self.assertEqual(response.data["pagination"]["page_size"], 2)

    def test_list_invalid_params(self):
        """测试：无效参数"""
        request = self.factory.get("/backup/", {"page": "invalid"})
        request.user = self.user

        response = self.view(request)

        self.assertEqual(response.status_code, 400)


class TestBackupJobDetailAPIView(TestCase):
    """测试 BackupJobDetailAPIView"""

    def setUp(self):
        self.factory = RequestFactory()
        self.view = BackupJobDetailAPIView.as_view()
        self.user = User.objects.create_user(username="testuser")
        UserRole.objects.create(username="testuser", role="dev")

        self.job = BackupJob.objects.create(
            job_instance_id="job_123",
            operator="testuser",
            search_path="/app",
            suffix="log",
            backup_path="/backup",
            bk_job_link="http://example.com/123",
            status=BackupJob.Status.SUCCESS,
        )

        # 创建关联记录
        BackupRecord.objects.create(backup_job=self.job, bk_host_id=1, status="success", bk_backup_name="file1.log")
        BackupRecord.objects.create(backup_job=self.job, bk_host_id=2, status="success", bk_backup_name="file2.log")

    def test_get_detail_success(self):
        """测试：成功获取详情"""
        request = self.factory.get(f"/backup/{self.job.id}/")
        request.user = self.user

        response = self.view(request, pk=self.job.id)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["id"], self.job.id)
        self.assertEqual(response.data["data"]["job_instance_id"], "job_123")

    def test_get_detail_not_found(self):
        """测试：不存在的作业ID"""
        request = self.factory.get("/backup/99999/")
        request.user = self.user

        with self.assertRaises(BackupJob.DoesNotExist):
            self.view(request, pk=99999)

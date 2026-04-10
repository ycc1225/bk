"""
Job视图单元测试
"""

import json

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from home_application.models import BackupJob, UserRole
from home_application.views.job import (
    BackupFileAPIView,
    BackupJobCallbackAPIView,
    SearchFileAPIView,
)

User = get_user_model()


class TestSearchFileAPIView(TestCase):
    """测试 SearchFileAPIView"""

    def setUp(self):
        self.factory = RequestFactory()
        self.view = SearchFileAPIView.as_view()
        self.user = User.objects.create_user(username="testuser")
        UserRole.objects.create(username="testuser", role="dev")

    def test_search_file_invalid_host_id(self):
        """测试：无效的主机ID"""
        request = self.factory.get("/job/search/", {"host_id_list": "invalid", "search_path": "/app"})
        request.user = self.user

        response = self.view(request)

        self.assertEqual(response.status_code, 400)

    def test_search_file_missing_params(self):
        """测试：缺少参数"""
        request = self.factory.get("/job/search/", {})
        request.user = self.user

        response = self.view(request)

        self.assertEqual(response.status_code, 400)


class TestBackupFileAPIView(TestCase):
    """测试 BackupFileAPIView"""

    def setUp(self):
        self.factory = RequestFactory()
        self.view = BackupFileAPIView.as_view()
        self.user = User.objects.create_user(username="testuser")
        UserRole.objects.create(username="testuser", role="ops")


class TestBackupJobCallbackAPIView(TestCase):
    """测试 BackupJobCallbackAPIView"""

    def setUp(self):
        self.factory = RequestFactory()
        self.view = BackupJobCallbackAPIView.as_view()

    def test_callback_success(self):
        """测试：成功的回调"""
        job = BackupJob.objects.create(
            job_instance_id="12345",
            operator="test",
            search_path="/app",
            suffix="log",
            backup_path="/backup",
            bk_job_link="http://example.com",
            status=BackupJob.Status.PENDING,
        )

        data = {"job_instance_id": "12345", "status": 3, "step_instances": [{"status": 3}]}
        request = self.factory.post("/job/callback/", data=json.dumps(data), content_type="application/json")

        response = self.view(request)

        self.assertEqual(response.status_code, 200)
        job.refresh_from_db()
        self.assertEqual(job.status, BackupJob.Status.SUCCESS)

    def test_callback_failure(self):
        """测试：失败的回调"""
        job = BackupJob.objects.create(
            job_instance_id="12345",
            operator="test",
            search_path="/app",
            suffix="log",
            backup_path="/backup",
            bk_job_link="http://example.com",
            status=BackupJob.Status.PENDING,
        )

        data = {"job_instance_id": "12345", "status": 4, "step_instances": [{"status": 4}]}
        request = self.factory.post("/job/callback/", data=json.dumps(data), content_type="application/json")

        response = self.view(request)

        self.assertEqual(response.status_code, 200)
        job.refresh_from_db()
        self.assertEqual(job.status, BackupJob.Status.FAILED)

    def test_callback_job_not_found(self):
        """测试：作业不存在"""
        data = {"job_instance_id": "99999", "status": 3}
        request = self.factory.post("/job/callback/", data=json.dumps(data), content_type="application/json")

        response = self.view(request)

        self.assertEqual(response.status_code, 404)

    def test_callback_missing_params(self):
        """测试：缺少必要参数"""
        request = self.factory.post("/job/callback/", data=json.dumps({}), content_type="application/json")

        response = self.view(request)

        self.assertEqual(response.status_code, 400)

    def test_callback_already_processed(self):
        """测试：已处理的作业不重复更新"""
        job = BackupJob.objects.create(
            job_instance_id="12345",
            operator="test",
            search_path="/app",
            suffix="log",
            backup_path="/backup",
            bk_job_link="http://example.com",
            status=BackupJob.Status.SUCCESS,  # 已经成功了
        )

        data = {"job_instance_id": "12345", "status": 4, "step_instances": [{"status": 4}]}
        request = self.factory.post("/job/callback/", data=json.dumps(data), content_type="application/json")

        response = self.view(request)

        self.assertEqual(response.status_code, 200)
        job.refresh_from_db()
        # 状态不应该改变
        self.assertEqual(job.status, BackupJob.Status.SUCCESS)

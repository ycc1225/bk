"""
Tencent is pleased to support the open source community by making 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community
Edition) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at
http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.db import models
from django.utils import timezone

# Create your models here.


class BizInfo(models.Model):
    """
    业务信息
    """

    bk_biz_id = models.IntegerField(unique=True, db_index=True)
    bk_biz_name = models.CharField(max_length=50)


class SetInfo(models.Model):
    """
    集群信息
    """

    bk_set_id = models.IntegerField(unique=True, db_index=True)
    bk_set_name = models.CharField(max_length=100)
    bk_biz_id = models.IntegerField(db_index=True)


class ModuleInfo(models.Model):
    """
    模块信息
    """

    bk_module_id = models.IntegerField(unique=True, db_index=True)
    bk_module_name = models.CharField(max_length=100)
    bk_set_id = models.IntegerField(db_index=True)
    bk_biz_id = models.IntegerField(db_index=True)


class SyncStatus(models.Model):
    name = models.CharField(max_length=50, unique=True)
    last_sync_at = models.DateTimeField(null=True)
    last_status = models.CharField(
        max_length=20,
        choices=(("success", "success"), ("failed", "failed"), ("pending", "pending"), ("running", "running")),
        null=True,
    )
    last_error = models.TextField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def mark_success(self):
        self.last_sync_at = timezone.now()
        self.last_status = "success"
        self.last_error = None
        self.save(update_fields=["last_sync_at", "last_status", "last_error"])

    def mark_running(self):
        self.last_status = "running"
        self.updated_at = timezone.now()
        self.save(update_fields=["last_status", "updated_at"])

    def mark_failed(self, error: str):
        self.last_status = "failed"
        self.last_error = error[:2000]
        self.updated_at = timezone.now()
        self.save(update_fields=["last_status", "last_error", "updated_at"])


class BackupJob(models.Model):
    """
    状态转移
    pending -> processing -> success/partial/failed
    """

    class Status:
        PENDING = "pending"
        PROCESSING = "processing"
        SUCCESS = "success"
        FAILED = "failed"
        PARTIAL = "partial"

        CHOICES = (
            (PENDING, "pending"),
            (PROCESSING, "processing"),
            (SUCCESS, "success"),
            (FAILED, "failed"),
            (PARTIAL, "partial"),
        )

    job_instance_id = models.CharField(max_length=255, unique=True)  # 作业平台实例ID
    operator = models.CharField(max_length=255)  # 操作人
    search_path = models.TextField()  # 搜索路径
    suffix = models.CharField(max_length=255)  # 文件后缀
    backup_path = models.TextField()  # 备份路径
    bk_job_link = models.TextField()  # 作业链接
    status = models.CharField(
        max_length=50, choices=Status.CHOICES, default=Status.PENDING
    )  # 整体状态：success/failed/pending/processing
    host_count = models.IntegerField(default=0)  # 主机数量
    file_count = models.IntegerField(default=0)  # 文件总数
    created_at = models.DateTimeField(auto_now_add=True)  # 创建时间

    class Meta:
        ordering = ["-id"]

    def mark_processing(self):
        self.status = self.Status.PROCESSING
        self.save(update_fields=["status"])

    def mark_success(self, file_count=None):
        self.status = self.Status.SUCCESS
        if file_count is not None:
            self.file_count = file_count
            self.save(update_fields=["status", "file_count"])
        else:
            self.save(update_fields=["status"])

    def mark_failed(self):
        self.status = self.Status.FAILED
        self.save(update_fields=["status"])

    def mark_partial(self, file_count=None):
        self.status = self.Status.PARTIAL
        if file_count is not None:
            self.file_count = file_count
            self.save(update_fields=["status", "file_count"])
        else:
            self.save(update_fields=["status"])


# 从表：备份记录（主机+文件）
class BackupRecord(models.Model):
    backup_job = models.ForeignKey(BackupJob, on_delete=models.CASCADE, related_name="records")
    bk_host_id = models.IntegerField()  # 主机ID
    status = models.CharField(max_length=50)  # 文件状态
    bk_backup_name = models.CharField(max_length=1024)

    class Meta:
        ordering = ["-id"]


class ApiRequestCount(models.Model):
    """
    API请求次数记录模型，用于运营分析
    """

    api_category = models.CharField(verbose_name="API类别", max_length=255)
    api_name = models.CharField(verbose_name="API名称", max_length=255)
    date = models.DateField(verbose_name="统计日期", auto_now_add=True)
    request_count = models.IntegerField(verbose_name="请求次数", default=0)
    error_count = models.IntegerField(verbose_name="错误请求次数", default=0)

    class Meta:
        unique_together = ("api_category", "api_name", "date")  # 联合唯一索引
        verbose_name = "API请求次数"
        verbose_name_plural = "API请求次数"

    def __str__(self):
        return f"{self.date}-{self.api_category}-{self.api_name}"


class UserRole(models.Model):
    """
    用户角色映射表，用于 RBAC 权限控制
    """

    ROLE_CHOICES = (
        ("admin", "管理员"),
        ("ops", "运维"),
        ("dev", "开发"),
        ("bot", "机器人"),
    )

    username = models.CharField(verbose_name="用户名", max_length=128, unique=True, db_index=True)
    role = models.CharField(verbose_name="角色", max_length=16, choices=ROLE_CHOICES)
    created_at = models.DateTimeField(verbose_name="创建时间", auto_now_add=True)
    updated_at = models.DateTimeField(verbose_name="更新时间", auto_now=True)

    class Meta:
        verbose_name = "用户角色"
        verbose_name_plural = "用户角色"

    def __str__(self):
        return f"{self.username} - {self.get_role_display()}"

# -*- coding: utf-8 -*-
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


# Create your models here.

class BizInfo(models.Model):
    """
    业务信息
    """
    bk_biz_id = models.IntegerField(unique=True)
    bk_biz_name = models.CharField(max_length=50)


class SetInfo(models.Model):
    """
    集群信息
    """
    bk_set_id = models.IntegerField(unique=True)
    bk_set_name = models.CharField(max_length=100)
    bk_biz_id = models.IntegerField()


class ModuleInfo(models.Model):
    """
    模块信息
    """
    bk_module_id = models.IntegerField(unique=True)
    bk_module_name = models.CharField(max_length=100)
    bk_set_id = models.IntegerField()
    bk_biz_id = models.IntegerField()


class BackupJob(models.Model):
    job_instance_id = models.CharField(max_length=255, unique=True)  # 作业平台实例ID
    operator = models.CharField(max_length=255)  # 操作人
    search_path = models.TextField()  # 搜索路径
    suffix = models.CharField(max_length=255)  # 文件后缀
    backup_path = models.TextField()  # 备份路径
    bk_job_link = models.TextField()  # 作业链接
    status = models.CharField(max_length=50)  # 整体状态：success/failed/partial
    host_count = models.IntegerField(default=0)  # 主机数量
    file_count = models.IntegerField(default=0)  # 文件总数
    created_at = models.DateTimeField(auto_now_add=True)  # 创建时间

    class Meta:
        ordering = ['-id']

# 从表：备份记录（主机+文件）
class BackupRecord(models.Model):
    backup_job = models.ForeignKey(BackupJob, on_delete=models.CASCADE, related_name='records')
    bk_host_id = models.IntegerField()  # 主机ID
    status = models.CharField(max_length=50)  # 文件状态
    bk_backup_name = models.CharField(max_length=1024)

    class Meta:
        ordering = ['-id']

class ApiRequestCount(models.Model):
    """
    API请求次数记录模型，用于运营分析
    """

    api_category = models.CharField(verbose_name="API类别", max_length=255)
    api_name = models.CharField(verbose_name="API名称", max_length=255)
    request_count = models.IntegerField(verbose_name="请求次数", default=0)

    class Meta:
        unique_together = ("api_category", "api_name")  # 联合唯一索引
        verbose_name = "API请求次数"
        verbose_name_plural = "API请求次数"

    def __str__(self):
        return f"{self.api_category}-{self.api_name}"



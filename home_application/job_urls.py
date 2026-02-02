"""
JOB 相关 API 路由配置
"""

from django.urls import path

from home_application.views.backup import BackupJobDetailAPIView, BackupJobListAPIView
from home_application.views.job import BackupFileAPIView, SearchFileAPIView

urlpatterns = (
    # 文件操作
    path("search-file/", SearchFileAPIView.as_view(), name="api-search-file"),
    path("backup-file/", BackupFileAPIView.as_view(), name="api-backup-file"),
    # 备份作业
    path("backup-jobs/", BackupJobListAPIView.as_view(), name="api-backup-jobs"),
    path("backup-job-detail/<int:pk>/", BackupJobDetailAPIView.as_view(), name="api-backup-job-detail"),
)

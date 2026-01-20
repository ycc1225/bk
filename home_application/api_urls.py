# -*- coding: utf-8 -*-
"""
DRF API URL路由配置
"""
import os

from django.urls import path

from .api_views import (
    BizInfoAPIView, SetInfoAPIView, ModuleInfoAPIView,
    BackupJobListAPIView, BackupJobDetailAPIView, BackupJobCreateAPIView,
    DataSyncAPIView, HostListAPIView, HostDetailAPIView,
    SearchFileAPIView, BackupFileAPIView, BackupJobCallbackAPIView
)
from .swagger_config import schema_view

# API视图路由
urlpatterns = [
    # Swagger API文档
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    
    # 业务、集群、模块数据
    path('biz-list/', BizInfoAPIView.as_view(), name='api-biz-list'),
    path('set-list/', SetInfoAPIView.as_view(), name='api-set-list'),
    path('module-list/', ModuleInfoAPIView.as_view(), name='api-module-list'),
    
    # 数据同步
    path('sync/', DataSyncAPIView.as_view(), name='api-sync'),
    
    # 主机相关
    path('host-list/', HostListAPIView.as_view(), name='api-host-list'),
    path('host-detail/', HostDetailAPIView.as_view(), name='api-host-detail'),
    
    # 文件操作
    path('search-file/', SearchFileAPIView.as_view(), name='api-search-file'),
    path('backup-file/', BackupFileAPIView.as_view(), name='api-backup-file'),
    
    # 备份作业
    path('backup-jobs/', BackupJobListAPIView.as_view(), name='api-backup-jobs'),
    path('backup-job-detail/<int:pk>/', BackupJobDetailAPIView.as_view(), name='api-backup-job-detail'),
    
    # 回调
    path('backup-callback/', BackupJobCallbackAPIView.as_view(), name='api-backup-callback'),
]
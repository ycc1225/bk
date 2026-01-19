# -*- coding: utf-8 -*-
"""
DRF API URL路由配置
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .api_views import (
    BizInfoViewSet, SetInfoViewSet, ModuleInfoViewSet,
    BackupJobViewSet, ApiRequestCountViewSet,
    DataSyncAPIView, HostListAPIView, HostDetailAPIView,
    SearchFileAPIView, BackupFileAPIView
)
from .swagger_config import schema_view

# 创建路由器
router = DefaultRouter()
router.register(r'biz-info', BizInfoViewSet, basename='biz-info')
router.register(r'set-info', SetInfoViewSet, basename='set-info')
router.register(r'module-info', ModuleInfoViewSet, basename='module-info')
router.register(r'backup-jobs', BackupJobViewSet, basename='backup-jobs')
router.register(r'api-stats', ApiRequestCountViewSet, basename='api-stats')

# API视图路由
urlpatterns = [
    # Swagger API文档
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    
    # 数据同步
    path('sync/', DataSyncAPIView.as_view(), name='api-sync'),
    
    # 主机相关
    path('hosts/', HostListAPIView.as_view(), name='api-host-list'),
    path('host-detail/', HostDetailAPIView.as_view(), name='api-host-detail'),
    
    # 文件操作
    path('search-file/', SearchFileAPIView.as_view(), name='api-search-file'),
    path('backup-file/', BackupFileAPIView.as_view(), name='api-backup-file'),
    
    # ViewSet路由
    path('', include(router.urls)),
]
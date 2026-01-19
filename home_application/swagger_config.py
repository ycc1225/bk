# -*- coding: utf-8 -*-
"""
DRF Swagger 配置文件
"""
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

# 创建schema视图
schema_view = get_schema_view(
    openapi.Info(
        title="Job Backup API",
        default_version='v1',
        description="文件备份管理系统 REST API 文档",
        terms_of_service="",
        contact=openapi.Contact(email=""),
        license=openapi.License(name="MIT License"),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)
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

from django.conf.urls import url
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from home_application.views.sync import TopoSyncAPIView
from .views.host import HostDetailAPIView, HostListAPIView
from .views.biz import BizInfoViewSet
from .views.job import SearchFileAPIView, BackupFileAPIView
from .views.backup import BackupJobListAPIView, BackupJobDetailAPIView
from .views.module import ModuleInfoViewSet
from .views.set import SetInfoViewSet

router = DefaultRouter()
router.register(r"biz-list", BizInfoViewSet, basename="biz-list")
router.register(r"set-list", SetInfoViewSet, basename="set-list")
router.register(r"module-list", ModuleInfoViewSet, basename="module-list")

urlpatterns = (
    path("", include(router.urls)),
    url(r"^sync/$",TopoSyncAPIView.as_view()),
    url(r"^host-list/$", HostListAPIView.as_view()),
    url(r"^host-detail/$", HostDetailAPIView.as_view()),
    # 文件操作
    path('search-file/', SearchFileAPIView.as_view(), name='api-search-file'),
    path('backup-file/', BackupFileAPIView.as_view(), name='api-backup-file'),

    # 备份作业
    path('backup-jobs/', BackupJobListAPIView.as_view(), name='api-backup-jobs'),
    path('backup-job-detail/<int:pk>/', BackupJobDetailAPIView.as_view(), name='api-backup-job-detail'),
)

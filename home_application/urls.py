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

from django.conf.urls import include, url
from django.urls import re_path

from home_application.views.health import HealthCheckAPIView
from home_application.views.metrics import MetricsAPIView

urlpatterns = (
    # CMDB 相关 API
    url(r"^cmdb/", include("home_application.cmdb_urls")),
    # JOB 相关 API
    url(r"^job/", include("home_application.job_urls")),
    re_path(r"health/$", HealthCheckAPIView.as_view(), name="health"),
    re_path(r"custom_metrics/$", MetricsAPIView.as_view(), name="custom_metrics"),
)

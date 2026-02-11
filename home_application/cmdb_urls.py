"""
CMDB 相关 API 路由配置
"""

from django.conf.urls import url
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from home_application.views.sync import SyncStatusAPIView, TopoSyncAPIView
from home_application.views.topo_search import TopoSearchAPIView

from .views.biz import BizInfoViewSet
from .views.host import HostDetailAPIView, HostListAPIView
from .views.module import ModuleInfoViewSet
from .views.set import SetInfoViewSet

router = DefaultRouter()
router.register(r"biz-list", BizInfoViewSet, basename="biz-list")
router.register(r"set-list", SetInfoViewSet, basename="set-list")
router.register(r"module-list", ModuleInfoViewSet, basename="module-list")

urlpatterns = (
    path("", include(router.urls)),
    url(r"^sync/$", TopoSyncAPIView.as_view()),
    url(r"^sync-status/$", SyncStatusAPIView.as_view()),
    url(r"^host-list/$", HostListAPIView.as_view()),
    url(r"^host-detail/$", HostDetailAPIView.as_view()),
    url(r"^topo-search/$", TopoSearchAPIView.as_view()),
)

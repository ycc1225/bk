from django.urls import re_path

from home_application.views.chat import ChatOpsView

urlpatterns = [
    re_path(r"^chat/$", ChatOpsView.as_view(), name="chatops-chat"),
]

"""
ServVia 3.0 API URL Configuration
==================================

Routes all chat traffic through the new ServVia pipeline (api/views.py).
Legacy agricultural endpoints are preserved under a separate namespace.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from api.views import ServViaChatViewSet, stream_chat_view
from api.lab_views import LabReportViewSet

router = DefaultRouter()
router.register(r"chat", ServViaChatViewSet, basename="chat")
router.register(r"labs", LabReportViewSet, basename="labs")

urlpatterns = [
    path("chat/stream/", stream_chat_view, name="chat_stream"),
    path("", include(router.urls)),
]

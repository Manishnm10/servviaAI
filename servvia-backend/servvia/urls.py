from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . views import (
    UserMedicalProfileViewSet, 
    ChatViewSet, 
    MedicalImageViewSet,
    LabReportViewSet
)

router = DefaultRouter()
router.register(r'profiles', UserMedicalProfileViewSet, basename='profile')
router.register(r'chats', ChatViewSet, basename='chat')
router.register(r'images', MedicalImageViewSet, basename='image')
router.register(r'lab-reports', LabReportViewSet, basename='lab-report')

urlpatterns = [
    path('', include(router.urls)),
]
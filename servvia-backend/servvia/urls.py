from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserMedicalProfileViewSet, ChatViewSet, MedicalImageViewSet

router = DefaultRouter()
router.register(r'profiles', UserMedicalProfileViewSet, basename='profile')
router.register(r'chats', ChatViewSet, basename='chat')
router.register(r'images', MedicalImageViewSet, basename='image')

urlpatterns = [
    path('', include(router.urls)),
]

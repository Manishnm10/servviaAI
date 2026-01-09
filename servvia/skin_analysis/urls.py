from django.urls import path
from . import views

urlpatterns = [
    path('analyze/', views.analyze_skin_image, name='analyze_skin'),
    path('history/', views.get_skin_analysis_history, name='skin_history'),
]


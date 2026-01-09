from django.urls import path
from . import views

urlpatterns = [
    path('analyze/', views.analyze_lab_report, name='analyze_lab_report'),
    path('history/', views.get_lab_report_history, name='lab_report_history'),
]


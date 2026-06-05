from django.urls import path
from . import views

urlpatterns = [
    # Legacy endpoints (unchanged)
    path('analyze/', views.analyze_lab_report_view, name='analyze_lab_report'),
    path('analyze/stream/', views.stream_lab_report_view, name='stream_lab_report'),
    path('history/', views.get_lab_report_history, name='lab_report_history'),

    # Co-Pilot endpoints (new)
    path('identify/', views.identify_lab_report_view, name='identify_lab_report'),
    path('confirm/', views.confirm_and_analyze_view, name='confirm_lab_report'),
    path('profiles/', views.patient_profiles_view, name='patient_profiles'),
]

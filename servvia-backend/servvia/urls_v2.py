"""
ServVia 2.0 - URL Configuration
"""
from django.urls import path
from .  import views_v2

urlpatterns = [
    path('v2/chat/', views_v2.agentic_chat, name='agentic_chat'),
    path('v2/remedies/', views_v2.get_remedies, name='get_remedies'),
    path('v2/safety/', views_v2.check_safety, name='check_safety'),
    path('v2/environment/', views_v2.get_environmental_context, name='environment'),
    path('v2/stats/', views_v2.knowledge_graph_stats, name='kg_stats'),
]

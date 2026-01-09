from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from django.conf.urls.static import static


def favicon_view(request):
    return HttpResponse(status=204)


def api_ping(request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),

    # API Modules
    path("api/", include("api.urls")),
    path("api/profile/", include("user_profile.urls")),

    # ServVia CV Modules
    path("api/skin/", include("skin_analysis.urls")),
    path("api/lab-report/", include("lab_report.urls")),

    # Frontend
    path("", TemplateView.as_view(template_name="index.html"), name="index"),

    # Health check
    path("api/ping/", api_ping),

    # Favicon
    path("favicon.ico", favicon_view),
]


# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


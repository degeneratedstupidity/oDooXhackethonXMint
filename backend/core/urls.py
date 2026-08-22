from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("accounts.urls")),
    path("api/", include("attendance.urls")),
    path("api/", include("timeoff.urls")),
    path("api/", include("payroll.urls")),
]

if settings.DEBUG:
    # Development only. In production these are served by the web server, not Django.
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

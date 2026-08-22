from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("accounts.urls")),
    path("api/", include("attendance.urls")),
    path("api/", include("timeoff.urls")),
    path("api/", include("payroll.urls")),
]

from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    ChangePasswordView,
    EmployeeViewSet,
    MeView,
    SignUpView,
    ThrottledLoginView,
    health,
)

router = DefaultRouter()
router.register("employees", EmployeeViewSet, basename="employee")

urlpatterns = [
    path("health/", health, name="health"),
    path("auth/signup/", SignUpView.as_view(), name="signup"),
    path("auth/login/", ThrottledLoginView.as_view(), name="login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("auth/change-password/", ChangePasswordView.as_view(), name="change-password"),
    path("me/", MeView.as_view(), name="me"),
    path("", include(router.urls)),
]

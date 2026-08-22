from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import PayslipView, SalaryStructureViewSet

router = DefaultRouter()
router.register("salary", SalaryStructureViewSet, basename="salary")

urlpatterns = [
    path("payslip/<int:user_id>/", PayslipView.as_view(), name="payslip"),
    *router.urls,
]

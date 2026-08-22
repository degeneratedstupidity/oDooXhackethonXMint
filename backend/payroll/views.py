from dataclasses import asdict

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdmin
from accounts.tenancy import TenantScopedViewSetMixin, set_current_company

from .models import SalaryComponent, SalaryStructure
from .payslip import compute_payslip
from .serializers import SalaryComponentSerializer, SalaryStructureSerializer


class SalaryStructureViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    """Salary information.

    Admin-only, per the specification's note that the Salary Info tab is visible to
    administrators alone — HR Officers manage people and leave, but not pay.
    """

    serializer_class = SalaryStructureSerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    http_method_names = ["get", "patch", "put", "head", "options"]

    def get_queryset(self):
        queryset = SalaryStructure.objects.select_related("user").prefetch_related("components")
        if employee := self.request.query_params.get("user"):
            queryset = queryset.filter(user_id=employee)
        return queryset

    @action(detail=True, methods=["patch"], url_path="components/(?P<component_id>[^/.]+)")
    def update_component(self, request, pk=None, component_id=None):
        """Change one component's definition, then rebalance the whole structure."""
        structure = self.get_object()
        component = SalaryComponent.objects.get(pk=component_id, structure=structure)

        serializer = SalaryComponentSerializer(component, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        structure.recompute()
        structure.refresh_from_db()
        return Response(SalaryStructureSerializer(structure).data)


class PayslipView(APIView):
    """A month's payslip for one employee, derived from attendance and approved leave.

    Administrator-only, like the rest of the salary API.
    """

    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request, user_id):
        set_current_company(request.user.company_id)

        today = timezone.localdate()
        try:
            year = int(request.query_params.get("year", today.year))
            month = int(request.query_params.get("month", today.month))
        except ValueError:
            return Response(
                {"detail": "Year and month must be numbers."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not 1 <= month <= 12:
            return Response(
                {"detail": "Month must be between 1 and 12."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        structure = get_object_or_404(
            SalaryStructure.objects.select_related("user").prefetch_related("components"),
            user_id=user_id,
        )
        payslip = compute_payslip(structure, year, month)

        return Response(
            {
                "employee": structure.user.full_name,
                "login_id": structure.user.login_id,
                "monthly_wage": structure.monthly_wage,
                **asdict(payslip),
            }
        )

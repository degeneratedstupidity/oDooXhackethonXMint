from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import IsAdmin
from accounts.tenancy import TenantScopedViewSetMixin

from .models import SalaryComponent, SalaryStructure
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

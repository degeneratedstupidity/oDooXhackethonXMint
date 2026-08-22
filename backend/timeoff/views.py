from django.utils import timezone
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import CanManagePeople
from accounts.tenancy import TenantScopedViewSetMixin

from .models import TimeOffRequest, TimeOffStatus, TimeOffType
from .serializers import TimeOffRequestSerializer, TimeOffTypeSerializer


class TimeOffTypeViewSet(TenantScopedViewSetMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = TimeOffTypeSerializer
    permission_classes = [IsAuthenticated]
    queryset = TimeOffType.objects.all()


class TimeOffRequestViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    """Leave requests.

    Employees see and create only their own; Admin and HR Officers see everyone's and are
    the only ones who can approve or refuse.
    """

    serializer_class = TimeOffRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = TimeOffRequest.objects.select_related("user", "type")

        if not user.can_manage_people:
            queryset = queryset.filter(user=user)
        elif employee := self.request.query_params.get("user"):
            queryset = queryset.filter(user_id=employee)

        if state := self.request.query_params.get("status"):
            queryset = queryset.filter(status=state)
        return queryset

    def get_permissions(self):
        if self.action in ("approve", "refuse"):
            return [IsAuthenticated(), CanManagePeople()]
        return super().get_permissions()

    def perform_destroy(self, instance):
        # Withdrawing is only meaningful before a decision has been made.
        if instance.status != TimeOffStatus.TO_APPROVE:
            raise serializers.ValidationError("A reviewed request cannot be withdrawn.")
        instance.delete()

    def _review(self, request, pk, decision):
        instance = self.get_object()
        if instance.status != TimeOffStatus.TO_APPROVE:
            return Response(
                {"detail": "This request has already been reviewed."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance.status = decision
        instance.reviewed_by = request.user
        instance.reviewed_at = timezone.now()
        instance.save(update_fields=["status", "reviewed_by", "reviewed_at"])
        return Response(self.get_serializer(instance).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        return self._review(request, pk, TimeOffStatus.APPROVED)

    @action(detail=True, methods=["post"])
    def refuse(self, request, pk=None):
        return self._review(request, pk, TimeOffStatus.REFUSED)

    @action(detail=False, methods=["get"])
    def balances(self, request):
        """Days remaining per type for the calling employee, this calendar year.

        Allowance comes from the type's yearly default; anything approved this year is
        deducted. Uncapped types report a null balance rather than a misleading number.
        """
        year = timezone.localdate().year
        balances = []

        for leave_type in TimeOffType.objects.filter(company=request.user.company):
            # Counts days, not requests.
            used_days = sum(
                item.days
                for item in TimeOffRequest.objects.filter(
                    user=request.user,
                    type=leave_type,
                    status=TimeOffStatus.APPROVED,
                    start_date__year=year,
                )
            )
            allowance = float(leave_type.default_days_per_year)
            balances.append(
                {
                    "type": leave_type.id,
                    "name": leave_type.name,
                    "is_paid": leave_type.is_paid,
                    "allowance": allowance if allowance else None,
                    "used": used_days,
                    "available": round(allowance - used_days, 1) if allowance else None,
                }
            )
        return Response(balances)

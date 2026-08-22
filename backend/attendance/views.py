from django.db import transaction
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.tenancy import TenantScopedViewSetMixin

from .models import Attendance
from .serializers import AttendanceSerializer


class AttendanceViewSet(TenantScopedViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """Attendance records, plus the check-in/check-out actions.

    Employees see only their own rows; Admin and HR Officers see everyone's. Row-level
    security already confines results to the caller's company, so this only has to
    enforce the within-company rule.
    """

    serializer_class = AttendanceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = Attendance.objects.select_related("user")

        if not user.can_manage_people:
            queryset = queryset.filter(user=user)
        elif employee := self.request.query_params.get("user"):
            queryset = queryset.filter(user_id=employee)

        if date := self.request.query_params.get("date"):
            queryset = queryset.filter(date=date)
        if month := self.request.query_params.get("month"):
            # Expected as YYYY-MM.
            year, _, month_number = month.partition("-")
            queryset = queryset.filter(date__year=year, date__month=month_number)

        return queryset

    @action(detail=False, methods=["get"])
    def today(self, request):
        """The caller's own open or completed record for today, for the systray control."""
        record = Attendance.objects.filter(
            user=request.user, date=timezone.localdate()
        ).first()
        return Response(AttendanceSerializer(record).data if record else None)

    @action(detail=False, methods=["post"])
    @transaction.atomic
    def check_in(self, request):
        today = timezone.localdate()
        record, created = Attendance.objects.get_or_create(
            company=request.user.company,
            user=request.user,
            date=today,
            defaults={"check_in": timezone.now()},
        )
        if not created:
            return Response(
                {"detail": "You have already checked in today."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(AttendanceSerializer(record).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"])
    @transaction.atomic
    def check_out(self, request):
        record = Attendance.objects.filter(
            user=request.user, date=timezone.localdate()
        ).first()
        if not record:
            return Response(
                {"detail": "You have not checked in today."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if record.check_out:
            return Response(
                {"detail": "You have already checked out today."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        record.check_out = timezone.now()
        record.save(update_fields=["check_out"])
        return Response(AttendanceSerializer(record).data)

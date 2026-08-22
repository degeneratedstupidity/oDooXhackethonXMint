from django.utils import timezone
from rest_framework import serializers

from accounts.fields import RelativeFileField

from .models import PublicHoliday, TimeOffRequest, TimeOffStatus, TimeOffType


class TimeOffTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimeOffType
        fields = ["id", "name", "is_paid", "default_days_per_year", "requires_attachment"]
        read_only_fields = fields


class PublicHolidaySerializer(serializers.ModelSerializer):
    class Meta:
        model = PublicHoliday
        fields = ["id", "name", "date"]
        read_only_fields = fields


class TimeOffRequestSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="user.full_name", read_only=True)
    login_id = serializers.CharField(source="user.login_id", read_only=True)
    type_name = serializers.CharField(source="type.name", read_only=True)
    days = serializers.IntegerField(read_only=True)
    attachment = RelativeFileField(required=False, allow_null=True)

    class Meta:
        model = TimeOffRequest
        fields = [
            "id",
            "user",
            "employee_name",
            "login_id",
            "type",
            "type_name",
            "start_date",
            "end_date",
            "days",
            "reason",
            "attachment",
            "status",
            "created_at",
        ]
        read_only_fields = ["id", "user", "status", "created_at"]

    def validate(self, attrs):
        start = attrs.get("start_date")
        end = attrs.get("end_date")
        leave_type = attrs.get("type")
        user = self.context["request"].user

        if start and end and end < start:
            raise serializers.ValidationError(
                {"end_date": "The end date cannot be before the start date."}
            )

        if leave_type:
            # Guards against passing a type id belonging to another company.
            if leave_type.company_id != user.company_id:
                raise serializers.ValidationError({"type": "Unknown time off type."})
            if leave_type.requires_attachment and not attrs.get("attachment"):
                raise serializers.ValidationError(
                    {"attachment": f"{leave_type.name} requires a supporting document."}
                )

        # Reject overlaps with a request that is already approved or awaiting review,
        # so the same days cannot be booked twice.
        if start and end:
            clash = TimeOffRequest.objects.filter(
                user=user,
                status__in=[TimeOffStatus.TO_APPROVE, TimeOffStatus.APPROVED],
                start_date__lte=end,
                end_date__gte=start,
            )
            if self.instance:
                clash = clash.exclude(pk=self.instance.pk)
            if clash.exists():
                raise serializers.ValidationError(
                    "You already have a time off request covering some of those dates."
                )

        return attrs

    def create(self, validated_data):
        user = self.context["request"].user
        return TimeOffRequest.objects.create(
            company=user.company, user=user, **validated_data
        )

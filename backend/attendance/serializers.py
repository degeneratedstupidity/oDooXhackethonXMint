from rest_framework import serializers

from .models import Attendance


class AttendanceSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="user.full_name", read_only=True)
    login_id = serializers.CharField(source="user.login_id", read_only=True)
    work_hours = serializers.FloatField(read_only=True)
    extra_hours = serializers.FloatField(read_only=True)

    class Meta:
        model = Attendance
        fields = [
            "id",
            "user",
            "employee_name",
            "login_id",
            "date",
            "check_in",
            "check_out",
            "work_hours",
            "extra_hours",
        ]
        read_only_fields = fields

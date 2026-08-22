from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers

from .models import BankDetail, Company, EmployeeProfile, Role, User
from .tenancy import set_current_company


class CompanySignUpSerializer(serializers.Serializer):
    """Creates a company and its first Admin.

    This is the only way an account is created without an existing user: everyone else is
    added by an Admin or HR Officer through the employee endpoints.
    """

    company_name = serializers.CharField(max_length=120)
    logo = serializers.ImageField(required=False, allow_null=True)
    name = serializers.CharField(max_length=120)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate_name(self, value):
        if len(value.split()) < 2:
            raise serializers.ValidationError(
                "Enter both a first and last name — the login ID is built from them."
            )
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        from django.utils import timezone

        first_name, _, last_name = validated_data["name"].partition(" ")
        company = Company.objects.create(
            name=validated_data["company_name"],
            code=Company.derive_code(validated_data["company_name"]),
            logo=validated_data.get("logo"),
        )
        # The profile and bank rows below are covered by row-level security, so the
        # company scope has to be in place before they are inserted or the policy's
        # WITH CHECK will reject them.
        set_current_company(company.id)

        today = timezone.localdate()
        login_id = User.generate_login_id(company, first_name, last_name.strip(), today.year)

        user = User.objects.create_user(
            login_id=login_id,
            email=validated_data["email"],
            password=validated_data["password"],
            company=company,
            first_name=first_name,
            last_name=last_name.strip(),
            phone=validated_data.get("phone", ""),
            role=Role.ADMIN,
            date_of_joining=today,
        )
        EmployeeProfile.objects.create(company=company, user=user)
        BankDetail.objects.create(company=company, user=user)
        return user


class UserSummarySerializer(serializers.ModelSerializer):
    """The shape the frontend needs to render the current user and the directory cards."""

    full_name = serializers.CharField(read_only=True)
    company_name = serializers.CharField(source="company.name", read_only=True)
    job_position = serializers.CharField(source="profile.job_position", read_only=True, default="")
    department = serializers.CharField(source="profile.department", read_only=True, default="")

    class Meta:
        model = User
        fields = [
            "id",
            "login_id",
            "first_name",
            "last_name",
            "full_name",
            "email",
            "phone",
            "role",
            "avatar",
            "date_of_joining",
            "must_change_password",
            "company_name",
            "job_position",
            "department",
        ]
        read_only_fields = fields


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate_current_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate_new_password(self, value):
        validate_password(value, self.context["request"].user)
        return value

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        return attrs

    def save(self, **kwargs):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.must_change_password = False
        user.save(update_fields=["password", "must_change_password"])
        return user

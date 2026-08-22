from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers

from .fields import RelativeImageField
from .models import BankDetail, Company, EmployeeProfile, Role, User
from .tenancy import set_current_company
from .seed import create_salary_structure, seed_default_time_off_types


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
        create_salary_structure(company, user)
        seed_default_time_off_types(company)
        return user


class UserSummarySerializer(serializers.ModelSerializer):
    """The shape the frontend needs to render the current user and the directory cards."""

    full_name = serializers.CharField(read_only=True)
    avatar = RelativeImageField(read_only=True)
    work_status = serializers.SerializerMethodField()
    company_name = serializers.CharField(source="company.name", read_only=True)
    company_logo = RelativeImageField(source="company.logo", read_only=True)
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
            "is_active",
            "deactivated_on",
            "must_change_password",
            "company_name",
            "company_logo",
            "job_position",
            "department",
            "work_status",
        ]
        read_only_fields = fields

    def get_work_status(self, user):
        """The status dot on each directory card.

        Present if they are checked in today, on leave if an approved request covers
        today, otherwise absent.
        """
        from django.utils import timezone

        from timeoff.models import TimeOffStatus

        today = timezone.localdate()

        if user.attendances.filter(date=today).exists():
            return "present"
        if user.time_off_requests.filter(
            status=TimeOffStatus.APPROVED, start_date__lte=today, end_date__gte=today
        ).exists():
            return "leave"
        return "absent"


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


class EmployeeCreateSerializer(serializers.Serializer):
    """Admin/HR add an employee.

    The employee does not choose their own credentials: the system generates both the
    login ID and a first password, and flags the account so they are asked to change it.
    """

    first_name = serializers.CharField(max_length=60)
    last_name = serializers.CharField(max_length=60)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    role = serializers.ChoiceField(choices=Role.choices, default=Role.EMPLOYEE)
    date_of_joining = serializers.DateField()
    job_position = serializers.CharField(max_length=120, required=False, allow_blank=True)
    department = serializers.CharField(max_length=120, required=False, allow_blank=True)
    manager = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), required=False, allow_null=True
    )

    def validate_email(self, value):
        company = self.context["request"].user.company
        if User.objects.filter(company=company, email__iexact=value).exists():
            raise serializers.ValidationError("Someone in your company already uses this email.")
        return value

    def validate_manager(self, value):
        # Guards against assigning a manager from another company by passing a raw id.
        if value and value.company_id != self.context["request"].user.company_id:
            raise serializers.ValidationError("That manager is not in your company.")
        return value

    @transaction.atomic
    def create(self, validated_data):
        company = self.context["request"].user.company
        joining = validated_data["date_of_joining"]

        login_id = User.generate_login_id(
            company, validated_data["first_name"], validated_data["last_name"], joining.year
        )
        password = User.generate_password()

        user = User.objects.create_user(
            login_id=login_id,
            email=validated_data["email"],
            password=password,
            company=company,
            first_name=validated_data["first_name"],
            last_name=validated_data["last_name"],
            phone=validated_data.get("phone", ""),
            role=validated_data["role"],
            date_of_joining=joining,
            must_change_password=True,
        )
        EmployeeProfile.objects.create(
            company=company,
            user=user,
            job_position=validated_data.get("job_position", ""),
            department=validated_data.get("department", ""),
            manager=validated_data.get("manager"),
        )
        BankDetail.objects.create(company=company, user=user)
        create_salary_structure(company, user)

        # Surfaced once, so the administrator can pass the credentials on.
        self.generated_password = password
        return user


class BankDetailSerializer(serializers.ModelSerializer):
    """Bank and statutory identifiers. Stored encrypted; see accounts/fields.py."""

    class Meta:
        model = BankDetail
        fields = ["bank_name", "account_number", "ifsc_code", "pan_number", "uan_number"]

    def validate_ifsc_code(self, value):
        if value and len(value) != 11:
            raise serializers.ValidationError("An IFSC code is 11 characters long.")
        return value.upper()

    def validate_pan_number(self, value):
        if value and len(value) != 10:
            raise serializers.ValidationError("A PAN is 10 characters long.")
        return value.upper()

    def validate_account_number(self, value):
        if value and not value.isdigit():
            raise serializers.ValidationError("An account number contains digits only.")
        return value


class EmployeeProfileSerializer(serializers.ModelSerializer):
    manager_name = serializers.CharField(source="manager.full_name", read_only=True, default="")

    class Meta:
        model = EmployeeProfile
        fields = [
            "job_position",
            "department",
            "manager",
            "manager_name",
            "location",
            "date_of_birth",
            "residing_address",
            "nationality",
            "personal_email",
            "gender",
            "marital_status",
            "about",
            "what_i_love_about_my_job",
            "interests_and_hobbies",
            "skills",
            "certifications",
        ]

    def validate_manager(self, value):
        if value and value.company_id != self.context["request"].user.company_id:
            raise serializers.ValidationError("That manager is not in your company.")
        return value

    def validate_skills(self, value):
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise serializers.ValidationError("Skills must be a list of text values.")
        return value

    validate_certifications = validate_skills


class EmployeeDetailSerializer(serializers.ModelSerializer):
    """The full profile page: identity, work info, private info and bank details."""

    full_name = serializers.CharField(read_only=True)
    company_name = serializers.CharField(source="company.name", read_only=True)
    avatar = RelativeImageField(read_only=True)
    profile = EmployeeProfileSerializer()
    bank_detail = BankDetailSerializer()

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
            "company_name",
            "profile",
            "bank_detail",
        ]
        read_only_fields = ["id", "login_id", "full_name", "company_name", "date_of_joining"]

    def update(self, instance, validated_data):
        profile_data = validated_data.pop("profile", None)
        bank_data = validated_data.pop("bank_detail", None)

        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()

        if profile_data:
            for field, value in profile_data.items():
                setattr(instance.profile, field, value)
            instance.profile.save()

        if bank_data:
            for field, value in bank_data.items():
                setattr(instance.bank_detail, field, value)
            instance.bank_detail.save()

        return instance

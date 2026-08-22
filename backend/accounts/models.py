import secrets
import string

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models, transaction

from .fields import EncryptedCharField


class Company(models.Model):
    """A tenant. Every other record in the system belongs to exactly one company."""

    name = models.CharField(max_length=120)
    # Two-letter prefix used to build employee login IDs, e.g. "OI" for Odoo India.
    code = models.CharField(max_length=2)
    logo = models.ImageField(upload_to="company-logos/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "companies"

    def __str__(self):
        return self.name

    @staticmethod
    def derive_code(name):
        """Build a two-letter code from a company name.

        "Odoo India" -> "OI"; a single-word name falls back to its first two letters.
        """
        words = [w for w in name.split() if w]
        if not words:
            return "XX"
        if len(words) == 1:
            return words[0][:2].upper().ljust(2, "X")
        return (words[0][0] + words[1][0]).upper()


class TenantScopedModel(models.Model):
    """Base class for every table that holds company-owned data.

    Carrying `company` on a single abstract base means one Row-Level Security policy
    template applies uniformly to every table that inherits it — see
    `accounts/migrations/0002_enable_rls.py`.
    """

    company = models.ForeignKey(Company, on_delete=models.CASCADE)

    class Meta:
        abstract = True


class Role(models.TextChoices):
    ADMIN = "admin", "Admin"
    HR_OFFICER = "hr_officer", "HR Officer"
    EMPLOYEE = "employee", "Employee"


class UserManager(BaseUserManager):
    def create_user(self, login_id, email, password=None, **extra):
        if not login_id:
            raise ValueError("Users must have a login ID.")
        user = self.model(login_id=login_id, email=self.normalize_email(email), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, login_id, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("role", Role.ADMIN)
        return self.create_user(login_id, email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    """An employee. Login is by generated login ID, not by email.

    Employees never self-register: an Admin or HR Officer creates them, and the system
    generates both the login ID and a first password.
    """

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="users")
    login_id = models.CharField(max_length=32, unique=True)
    first_name = models.CharField(max_length=60)
    last_name = models.CharField(max_length=60)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.EMPLOYEE)
    date_of_joining = models.DateField()
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)

    # True until the employee replaces the system-generated password.
    must_change_password = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "login_id"
    REQUIRED_FIELDS = ["email"]

    def __str__(self):
        return f"{self.full_name} ({self.login_id})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def is_admin(self):
        return self.role == Role.ADMIN

    @property
    def can_manage_people(self):
        """Admins and HR Officers both administer attendance and time off."""
        return self.role in (Role.ADMIN, Role.HR_OFFICER)

    @classmethod
    @transaction.atomic
    def generate_login_id(cls, company, first_name, last_name, joining_year):
        """Build a login ID like OIJODO20220001.

        [company code][first 2 of first name][first 2 of last name][join year][sequence],
        where the sequence counts joiners for that company in that year, starting at 1.

        Locks the company row so two people created at the same moment cannot be handed
        the same sequence number.
        """
        Company.objects.select_for_update().get(pk=company.pk)

        initials = (first_name[:2] + last_name[:2]).upper().ljust(4, "X")
        prefix = f"{company.code}{initials}{joining_year}"

        sequence = (
            cls.objects.filter(company=company, date_of_joining__year=joining_year).count() + 1
        )

        # Skip over any ID already in use (possible if employees were removed and re-added).
        while cls.objects.filter(login_id=f"{prefix}{sequence:04d}").exists():
            sequence += 1

        return f"{prefix}{sequence:04d}"

    @staticmethod
    def generate_password(length=12):
        """A readable but random first-login password."""
        alphabet = string.ascii_letters + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(length))


class EmployeeProfile(TenantScopedModel):
    """The employee's HR record: everything on the profile page that is not credentials."""

    class Gender(models.TextChoices):
        MALE = "male", "Male"
        FEMALE = "female", "Female"
        OTHER = "other", "Other"

    class MaritalStatus(models.TextChoices):
        SINGLE = "single", "Single"
        MARRIED = "married", "Married"
        OTHER = "other", "Other"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")

    # Work information — shown to everyone in the directory.
    job_position = models.CharField(max_length=120, blank=True)
    department = models.CharField(max_length=120, blank=True)
    manager = models.ForeignKey(
        User, on_delete=models.SET_NULL, blank=True, null=True, related_name="reports"
    )
    location = models.CharField(max_length=120, blank=True)

    # Private information — visible to the employee themselves, and to Admin/HR.
    date_of_birth = models.DateField(blank=True, null=True)
    residing_address = models.TextField(blank=True)
    nationality = models.CharField(max_length=60, blank=True)
    personal_email = models.EmailField(blank=True)
    gender = models.CharField(max_length=10, choices=Gender.choices, blank=True)
    marital_status = models.CharField(
        max_length=10, choices=MaritalStatus.choices, blank=True
    )

    # Resume tab.
    about = models.TextField(blank=True)
    what_i_love_about_my_job = models.TextField(blank=True)
    interests_and_hobbies = models.TextField(blank=True)
    skills = models.JSONField(default=list, blank=True)
    certifications = models.JSONField(default=list, blank=True)

    def __str__(self):
        return f"Profile of {self.user.full_name}"


class BankDetail(TenantScopedModel):
    """Bank and statutory identity numbers.

    These columns are encrypted at rest: they are sensitive, and nothing in the product
    needs to search or sort by them.
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="bank_detail")
    bank_name = models.CharField(max_length=120, blank=True)
    account_number = EncryptedCharField(max_length=34, blank=True)
    ifsc_code = EncryptedCharField(max_length=11, blank=True)
    pan_number = EncryptedCharField(max_length=10, blank=True)
    uan_number = EncryptedCharField(max_length=12, blank=True)

    def __str__(self):
        return f"Bank details of {self.user.full_name}"

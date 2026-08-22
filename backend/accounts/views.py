from django.db import connection
from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User
from .permissions import CanManagePeople
from .serializers import (
    ChangePasswordSerializer,
    CompanySignUpSerializer,
    EmployeeCreateSerializer,
    EmployeeDetailSerializer,
    UserSummarySerializer,
)
from .tenancy import TenantScopedMixin, TenantScopedViewSetMixin


def tokens_for(user):
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    """Confirms the API is up and can reach Postgres."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT version()")
        version = cursor.fetchone()[0]
    return Response({"status": "ok", "database": version.split(",")[0]})


class SignUpView(APIView):
    """Company sign-up: creates the company and its first Admin, then logs them in."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = CompanySignUpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {"user": UserSummarySerializer(user).data, "tokens": tokens_for(user)},
            status=status.HTTP_201_CREATED,
        )


class MeView(TenantScopedMixin, APIView):
    """The signed-in user, for bootstrapping the frontend session.

    Scoped like every other view: without it row-level security hides the caller's own
    profile row and the response comes back with the profile fields empty.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSummarySerializer(request.user).data)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "Password updated."})


class EmployeeViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    """The employee directory.

    Everyone in a company can see the directory — the wireframes show it as the landing
    page for all roles — but only Admin and HR Officers can add people.
    """

    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        # The list is the directory grid; a single record is the full profile page.
        if self.action in ("retrieve", "update", "partial_update"):
            return EmployeeDetailSerializer
        return UserSummarySerializer

    def get_queryset(self):
        """Scoped to the caller's company.

        Row-level security does not cover the user table (authentication has to resolve a
        user before their company is known), so this filter is the boundary, not a
        convenience.
        """
        queryset = (
            User.objects.filter(company=self.request.user.company)
            .select_related("company", "profile", "bank_detail")
            .order_by("first_name", "last_name")
        )

        search = self.request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(login_id__icontains=search)
                | Q(email__icontains=search)
                | Q(profile__job_position__icontains=search)
                | Q(profile__department__icontains=search)
            )
        return queryset

    def get_permissions(self):
        if self.action in ("create", "destroy"):
            return [IsAuthenticated(), CanManagePeople()]
        return super().get_permissions()

    def update(self, request, *args, **kwargs):
        """Employees may edit their own profile; Admin and HR may edit anyone's."""
        target = self.get_object()
        if target.id != request.user.id and not request.user.can_manage_people:
            raise PermissionDenied("You can only edit your own profile.")
        # Only Admin and HR decide someone's role, and nobody changes their own.
        if "role" in request.data and (
            not request.user.is_admin or target.id == request.user.id
        ):
            raise PermissionDenied("You cannot change this role.")
        return super().update(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        serializer = EmployeeCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {
                "user": UserSummarySerializer(user).data,
                # Shown to the administrator once; never stored in readable form.
                "credentials": {
                    "login_id": user.login_id,
                    "password": serializer.generated_password,
                },
            },
            status=status.HTTP_201_CREATED,
        )

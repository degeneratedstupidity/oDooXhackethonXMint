from django.db import connection
from django.db.models import Q
from rest_framework import status, viewsets
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
    UserSummarySerializer,
)
from .tenancy import TenantScopedViewSetMixin


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


class MeView(APIView):
    """The signed-in user, for bootstrapping the frontend session."""

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

    serializer_class = UserSummarySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Scoped to the caller's company.

        Row-level security does not cover the user table (authentication has to resolve a
        user before their company is known), so this filter is the boundary, not a
        convenience.
        """
        queryset = (
            User.objects.filter(company=self.request.user.company)
            .select_related("company", "profile")
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

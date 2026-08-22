from django.db import connection
from django.db.models import Q
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import User
from .permissions import CanManagePeople
from .serializers import (
    ChangePasswordSerializer,
    CompanySignUpSerializer,
    EmployeeCreateSerializer,
    EmployeeDetailSerializer,
    EmployeePublicSerializer,
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
    throttle_scope = "signup"

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
    throttle_scope = "password_change"

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
        if self.action in ("update", "partial_update"):
            return EmployeeDetailSerializer
        if self.action == "retrieve":
            # Everyone can open a colleague's profile, but private information and bank
            # details belong to the employee themselves and to the people who administer
            # them. Anyone else gets the trimmed serializer, which never loads those
            # fields at all rather than blanking them after the fact.
            return (
                EmployeeDetailSerializer
                if self._may_see_private(self.get_object())
                else EmployeePublicSerializer
            )
        return UserSummarySerializer

    def _may_see_private(self, target):
        return target.id == self.request.user.id or self.request.user.can_manage_people

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

        # Former employees are hidden from the directory listing but stay reachable by
        # id, so their history can be opened and they can be reactivated. Filtering them
        # out of a detail lookup would make reactivation impossible.
        hide_inactive = (
            self.action == "list"
            and self.request.query_params.get("include_inactive") != "true"
        )
        if hide_inactive:
            queryset = queryset.filter(is_active=True)

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

    @action(detail=True, methods=["post"], parser_classes=[MultiPartParser])
    def avatar(self, request, pk=None):
        """Upload a profile picture. Same rule as editing: yourself, or Admin/HR."""
        target = self.get_object()
        if target.id != request.user.id and not request.user.can_manage_people:
            raise PermissionDenied("You can only change your own picture.")

        image = request.FILES.get("avatar")
        if not image:
            return Response(
                {"avatar": ["No image was uploaded."]}, status=status.HTTP_400_BAD_REQUEST
            )
        if image.size > 5 * 1024 * 1024:
            return Response(
                {"avatar": ["Images must be 5 MB or smaller."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        target.avatar = image
        target.save(update_fields=["avatar"])
        return Response(UserSummarySerializer(target).data)

    def destroy(self, request, *args, **kwargs):
        """Deactivate rather than delete.

        Attendance records underpin past payslips and leave records are part of an
        employee's history, so removing the row would erase the evidence for pay already
        made. Deactivating keeps all of it and stops the account being used.
        """
        target = self.get_object()
        if target.id == request.user.id:
            raise PermissionDenied("You cannot deactivate your own account.")

        target.is_active = False
        target.deactivated_on = timezone.localdate()
        target.save(update_fields=["is_active", "deactivated_on"])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def reactivate(self, request, pk=None):
        """Undo a deactivation, for someone who returns or was deactivated by mistake."""
        if not request.user.can_manage_people:
            raise PermissionDenied("Only an administrator or HR officer can do this.")

        target = self.get_object()
        target.is_active = True
        target.deactivated_on = None
        target.save(update_fields=["is_active", "deactivated_on"])
        return Response(UserSummarySerializer(target).data)

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


class ThrottledLoginView(TokenObtainPairView):
    """Sign-in, rate limited.

    Login IDs are generated to a published format, so anyone can enumerate plausible
    ones. Without a limit, the only thing standing between an attacker and an account is
    the password itself.
    """

    throttle_scope = "login"

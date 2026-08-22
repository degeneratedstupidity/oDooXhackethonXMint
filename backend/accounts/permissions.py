from rest_framework import permissions


class IsAdmin(permissions.BasePermission):
    """Admin only. Salary information is the main thing behind this gate."""

    message = "Only an administrator can perform this action."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_admin)


class CanManagePeople(permissions.BasePermission):
    """Admins and HR Officers: creating employees, approving time off, viewing all attendance."""

    message = "Only an administrator or HR officer can perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.can_manage_people
        )


class IsSelfOrCanManagePeople(permissions.BasePermission):
    """Employees may read and edit their own record; Admin/HR may act on anyone's."""

    def has_object_permission(self, request, view, obj):
        owner_id = getattr(obj, "user_id", None) or getattr(obj, "id", None)
        if owner_id == request.user.id:
            return True
        return request.user.can_manage_people

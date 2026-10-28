from rest_framework.permissions import SAFE_METHODS, BasePermission

from apps.accounts.models import Role


def is_privileged(user) -> bool:
    """Managers and admins see and manage all CRM data."""
    return bool(user and user.is_authenticated and (user.is_superuser or user.role in (Role.ADMIN, Role.MANAGER)))


class IsAdminRole(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and (u.is_superuser or u.role == Role.ADMIN))


class IsPrivileged(BasePermission):
    def has_permission(self, request, view):
        return is_privileged(request.user)


class CrmObjectPermission(BasePermission):
    """Object-level rules shared by CRM viewsets.

    View attributes:
      owner_field            attribute holding the record owner (default "owner")
      rep_can_delete_own     sales reps may delete records they own (default False)
      rep_edit_own_only      sales reps may only edit records they own (default False)
    Managers/admins can do everything. Reads are open to any authenticated user
    (viewsets narrow the queryset where records are private to their owner).
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS or is_privileged(request.user):
            return True
        owned = getattr(obj, f"{getattr(view, 'owner_field', 'owner')}_id", None) == request.user.id
        if request.method == "DELETE":
            return bool(getattr(view, "rep_can_delete_own", False) and owned)
        if getattr(view, "rep_edit_own_only", False):
            return owned
        return True


class OwnerScopedMixin:
    """Sales reps only see records they own; managers and admins see everything."""

    owner_field = "owner"

    def scope(self, queryset):
        if getattr(self, "swagger_fake_view", False):  # OpenAPI generation has no real user
            return queryset.none()
        user = self.request.user
        return queryset if is_privileged(user) else queryset.filter(**{self.owner_field: user})

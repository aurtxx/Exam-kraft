from rest_framework.permissions import BasePermission, SAFE_METHODS
from apps.organizations.context import set_current_tenant
from .models import UserRole


class IsSuperAdmin(BasePermission):
    """Allows access only to Platform Super Admins."""
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            (request.user.role == UserRole.SUPERADMIN or request.user.is_superuser)
        )


class IsOrgAdmin(BasePermission):
    """Allows access to Platform Super Admins and Organization Admins."""
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role in (UserRole.SUPERADMIN, UserRole.ORG_ADMIN)
        )


class IsFaculty(BasePermission):
    """Allows access to Faculty, Org Admins, and Super Admins."""
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role in (UserRole.SUPERADMIN, UserRole.ORG_ADMIN, UserRole.FACULTY)
        )


class IsStudent(BasePermission):
    """Allows access to authenticated Students."""
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role == UserRole.STUDENT
        )


class IsOrgAdminOrReadOnly(BasePermission):
    """
    Allows read-only access (GET, HEAD, OPTIONS) to authenticated tenant members,
    but restricts write operations (POST, PUT, PATCH, DELETE) to
    Organization Admins and Platform Super Admins.
    """
    message = "Only organization administrators can create or modify this resource."
    code = "PERMISSION_DENIED"

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(
            request.user and
            request.user.is_authenticated and
            (request.user.role in (UserRole.SUPERADMIN, UserRole.ORG_ADMIN) or request.user.is_superuser)
        )


class IsTenantMember(BasePermission):
    """
    Enforces that the user belongs to the active tenant organization,
    or is a global SUPERADMIN.
    """
    message = "User does not belong to the active tenant organization."
    code = "PERMISSION_DENIED"

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.user.role == UserRole.SUPERADMIN or request.user.is_superuser:
            return True

        active_tenant = getattr(request, 'tenant', None)
        if not active_tenant and getattr(request.user, 'organization', None):
            active_tenant = request.user.organization
            request.tenant = active_tenant
            set_current_tenant(active_tenant)

        if not active_tenant:
            return False

        if request.user.organization_id != active_tenant.id:
            return False

        return True

    def has_object_permission(self, request, view, obj):
        if request.user.role == UserRole.SUPERADMIN or request.user.is_superuser:
            return True
        target_org_id = getattr(obj, 'organization_id', None)
        if target_org_id:
            return str(request.user.organization_id) == str(target_org_id)
        return True

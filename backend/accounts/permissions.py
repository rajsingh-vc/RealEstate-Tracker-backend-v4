from rest_framework.permissions import SAFE_METHODS, BasePermission

from .constants import Perms


class IsSuperAdmin(BasePermission):
    """Only users with is_superuser=True."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_superuser)


class HasDynamicPermission(BasePermission):
    """
    Generic permission class: reads a `required_perm` codename off the view
    and checks it against the user's Role.permissions. SuperAdmin always passes.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        required_perm = getattr(view, 'required_perm', None)
        if required_perm is None:
            return False
        return request.user.has_perm_codename(required_perm)


class IsCompanyAdminOrCEO(BasePermission):
    """
    Write access for anyone whose Role carries 'can_manage_users'
    (SuperAdmin included). Read access for any authenticated user.
    """
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.has_perm_codename(Perms.MANAGE_USERS)


class CanManageRoles(BasePermission):
    """Read for any authenticated user. Write requires 'can_manage_roles' (SuperAdmin included)."""
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.has_perm_codename(Perms.MANAGE_ROLES)


class CanManageDepartments(BasePermission):
    """Read for any authenticated user. Write requires SuperAdmin OR 'can_manage_departments'."""
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.is_superuser or request.user.has_perm_codename(Perms.MANAGE_DEPARTMENTS)


class OrganizationPermission(BasePermission):
    """
    Organizations, per current requirements:
    - Any authenticated user can read (list/retrieve) — scoped further at the
      queryset level so non-superadmins only ever see their own company.
    - ONLY SuperAdmin (is_superuser) can create/update/delete. No admin role
      or permission grants this, by design — organization creation is
      SuperAdmin-exclusive.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_superuser

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_superuser


class CanManageInvitations(BasePermission):
    """
    Used by both invite flows (SuperAdmin -> Admin, Admin -> User) — the
    scoping of *who* gets invited into *which* company happens in the
    serializer/view, this just gates who may use the endpoint at all.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return request.user.is_superuser or request.user.has_perm_codename(Perms.MANAGE_USERS)
        return request.user.is_superuser or request.user.has_perm_codename(Perms.MANAGE_USERS)


class IsAuthenticatedReadOnly(BasePermission):
    """Allows any authenticated user to read; write is not allowed."""
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        return False


# ---- Legacy aliases for projects that still import old names ----
IsAdminOrCEO = IsCompanyAdminOrCEO
ReadOnlyOrAuthenticated = IsAuthenticatedReadOnly
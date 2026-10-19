"""
Backend authorization enforcement guards for Konstruct Tracker modules.
Enforces module-level access control on protected APIs and viewsets.
"""
from django.http import JsonResponse
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied

from .module_registry import is_module_enabled_for_user


ROUTE_TO_MODULE_MAP = {
    "/api/hurdles/": "hurdles",
    "/api/resources/": "resources",
    "/api/checklists/": "checklists",
    "/api/categories/": "category-management",
    "/api/subcategories/": "category-management",
    "/api/compliance/": "compliance",
    "/api/handover/": "handover",
    "/api/documents/": "documents",
}


class HasModuleAccess(permissions.BasePermission):
    """
    DRF Permission class to enforce module access on a ViewSet or APIView.
    Usage on ViewSet:
        module_key = "hurdles"
        permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    """
    message = "You do not have permission to access this module."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_superuser:
            return True

        module_key = getattr(view, "module_key", None)
        if not module_key:
            # Fallback to route mapping if view doesn't explicitly specify module_key
            for path_prefix, m_key in ROUTE_TO_MODULE_MAP.items():
                if request.path.startswith(path_prefix):
                    module_key = m_key
                    break

        if not module_key:
            return True

        project_id = None
        # Check query params or body for project scoping if available
        pid = request.query_params.get("project") or request.query_params.get("project_id")
        if pid and str(pid).isdigit():
            project_id = int(pid)

        allowed = is_module_enabled_for_user(request.user, module_key, project_id=project_id)
        if not allowed:
            self.message = f"Access Denied: You do not have permission to access the '{module_key}' module."
            return False

        return True


class ModuleAuthorizationMiddleware:
    """
    Django middleware layer to block unauthorized requests to module endpoints.
    Handles both standard session-authenticated users and JWT Bearer tokens.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        # Identify target module key for this path
        target_module = None
        for prefix, key in ROUTE_TO_MODULE_MAP.items():
            if path.startswith(prefix):
                target_module = key
                break

        if target_module:
            # If user is not yet authenticated on request (e.g. JWT Bearer auth)
            user = getattr(request, "user", None)
            if not user or not user.is_authenticated:
                auth_header = request.headers.get("Authorization", "")
                if auth_header.startswith("Bearer "):
                    try:
                        from rest_framework_simplejwt.authentication import JWTAuthentication
                        jwt_auth = JWTAuthentication()
                        validated_token = jwt_auth.get_validated_token(auth_header.split(" ")[1])
                        user = jwt_auth.get_user(validated_token)
                        request.user = user
                    except Exception:
                        user = None

            if user and user.is_authenticated and not user.is_superuser:
                project_id = None
                pid = request.GET.get("project") or request.GET.get("project_id")
                if pid and str(pid).isdigit():
                    project_id = int(pid)

                if not is_module_enabled_for_user(user, target_module, project_id=project_id):
                    return JsonResponse(
                        {
                            "detail": f"Access Denied: You do not have permission to access the '{target_module}' module.",
                            "module": target_module,
                            "code": "module_access_denied",
                        },
                        status=403,
                    )

        return self.get_response(request)

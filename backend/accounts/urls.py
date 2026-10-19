from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    LoginView, LogoutView, MeView, CustomTokenRefreshView,
    ForgotPasswordView, VerifyOTPView, ResetPasswordView,
    UserViewSet, CompanyViewSet, RoleViewSet, DepartmentViewSet,
    OrganizationCompanyViewSet, EntityViewSet, EscalationRuleViewSet,
    InvitationViewSet, AcceptInvitationView, InvitationPreviewView,
)
from .module_views import (
    AppModuleViewSet,
    BulkUserModuleConfigView,
    ModuleAuditLogListView,
    ModuleMatrixView,
    MyModulePermissionsView,
    ResetUserModuleConfigView,
    RoleModuleConfigView,
    ToggleGlobalModuleView,
    UserModuleConfigView,
)

router = DefaultRouter()
router.register("users", UserViewSet, basename="user")
router.register("organizations", CompanyViewSet, basename="organization")
router.register("companies", OrganizationCompanyViewSet, basename="organization-company")
router.register("entities", EntityViewSet, basename="entity")
router.register("escalation-rules", EscalationRuleViewSet, basename="escalation-rule")
router.register("roles", RoleViewSet, basename="role")
router.register("departments", DepartmentViewSet, basename="department")
router.register("invitations", InvitationViewSet, basename="invitation")
router.register("modules", AppModuleViewSet, basename="module")
# Note: router auto-generates POST /invitations/{id}/resend/ from the
# @action on InvitationViewSet — no manual path needed here.

urlpatterns = [
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/refresh/", CustomTokenRefreshView.as_view(), name="token_refresh"),
    path("auth/me/", MeView.as_view(), name="me"),
    path("auth/forgot-password/", ForgotPasswordView.as_view(), name="forgot-password"),
    path("auth/verify-otp/", VerifyOTPView.as_view(), name="verify-otp"),
    path("auth/reset-password/", ResetPasswordView.as_view(), name="reset-password"),
    path("auth/invitations/<str:token>/", InvitationPreviewView.as_view(), name="invitation-preview"),
    path("auth/accept-invite/", AcceptInvitationView.as_view(), name="accept-invite"),

    # Module Visibility & Access Management
    path("modules/my-permissions/", MyModulePermissionsView.as_view(), name="my-module-permissions"),
    path("modules/toggle-global/", ToggleGlobalModuleView.as_view(), name="toggle-global-module"),
    path("modules/matrix/", ModuleMatrixView.as_view(), name="module-matrix"),
    path("modules/audit-logs/", ModuleAuditLogListView.as_view(), name="module-audit-logs"),
    path("modules/users/bulk/", BulkUserModuleConfigView.as_view(), name="bulk-user-module-config"),
    path("modules/users/<int:user_id>/", UserModuleConfigView.as_view(), name="user-module-config"),
    path("modules/users/<int:user_id>/reset/", ResetUserModuleConfigView.as_view(), name="reset-user-module-config"),
    path("modules/roles/<int:role_id>/", RoleModuleConfigView.as_view(), name="role-module-config"),

    path("", include(router.urls)),
]
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    LoginView, LogoutView, MeView,
    UserViewSet, CompanyViewSet, RoleViewSet, DepartmentViewSet,
    OrganizationCompanyViewSet, EntityViewSet, EscalationRuleViewSet,
    InvitationViewSet, AcceptInvitationView, InvitationPreviewView,
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
# Note: router auto-generates POST /invitations/{id}/resend/ from the
# @action on InvitationViewSet — no manual path needed here.

urlpatterns = [
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/me/", MeView.as_view(), name="me"),
    path("auth/invitations/<str:token>/", InvitationPreviewView.as_view(), name="invitation-preview"),
    path("auth/accept-invite/", AcceptInvitationView.as_view(), name="accept-invite"),
    path("", include(router.urls)),
]
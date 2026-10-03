from datetime import timedelta
from urllib.parse import urlparse

from django.conf import settings
from django.db import models as db_models
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import (
    Company, Department, Entity, EscalationRule, Invitation, OrganizationCompany,
    PasswordResetOTP, Role, User,
)
from .notifications import send_invitation_email, send_invitation_sms, send_password_reset_otp_email
from notifications.utils import notify, notify_superadmins
from .permissions import (
    CanManageDepartments,
    CanManageInvitations,
    CanManageRoles,
    IsCompanyAdminOrCEO,
    OrganizationPermission,
)
from .serializers import (
    AcceptInvitationSerializer,
    CompanySerializer,
    DepartmentSerializer,
    EntitySerializer,
    EscalationRuleSerializer,
    ForgotPasswordSerializer,
    InvitationSerializer,
    InvitationPreviewSerializer,
    LoginSerializer,
    OrganizationCompanySerializer,
    ResetPasswordSerializer,
    RoleSerializer,
    UserCreateSerializer,
    UserSerializer,
    UserUpdateSerializer,
    VerifyOTPSerializer,
)


def _tokens_for(user):
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        return Response({**_tokens_for(user), "user": UserSerializer(user, context={'request': request}).data})


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            if refresh_token:
                RefreshToken(refresh_token).blacklist()
        except Exception:
            pass
        return Response(status=status.HTTP_205_RESET_CONTENT)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user, context={'request': request}).data)


class CompanyViewSet(viewsets.ModelViewSet):
    """
    Organizations (frontend naming) / tenants (backend naming).
    - Read: any authenticated user; non-superadmins only ever see their own company.
    - Write (create/update/delete): SuperAdmin only.
    Accepts multipart since the frontend posts this as FormData (logo upload).
    """
    serializer_class = CompanySerializer
    permission_classes = [OrganizationPermission]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Company.objects.all().order_by('-created_at')
        if user.company_id:
            return Company.objects.filter(id=user.company_id)
        return Company.objects.none()

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

class ForgotPasswordView(APIView):
    """
    POST /auth/forgot-password/  {email}

    Public. Always returns 200 with a generic message — whether or not the
    email matches an account — so this endpoint can't be used to enumerate
    registered users. If it does match an active user, an OTP is created
    and emailed to that user's own address.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]

        if user:
            expiry_minutes = getattr(settings, "PASSWORD_RESET_OTP_EXPIRY_MINUTES", 10)
            record = PasswordResetOTP.objects.create(
                user=user,
                otp_code=PasswordResetOTP.generate_code(),
                expires_at=timezone.now() + timedelta(minutes=expiry_minutes),
            )
            send_password_reset_otp_email(user, record.otp_code, expiry_minutes)

        return Response({"detail": "If an account exists for that email, a verification code has been sent."})


class VerifyOTPView(APIView):
    """POST /auth/verify-otp/  {email, otp} — confirms the code before the reset-password step unlocks."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        record = serializer.validated_data["record"]
        record.is_verified = True
        record.save(update_fields=["is_verified"])
        return Response({"detail": "Code verified. You can now set a new password."})


class ResetPasswordView(APIView):
    """POST /auth/reset-password/  {email, otp, new_password, confirm_password}"""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        record = serializer.validated_data["record"]

        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])

        record.is_used = True
        record.save(update_fields=["is_used"])

        return Response({"detail": "Your password has been reset. You can now log in."})


class OrganizationCompanyViewSet(viewsets.ModelViewSet):
    """The frontend's nested "Company" record one level under an Organization."""
    serializer_class = OrganizationCompanySerializer
    permission_classes = [CanManageDepartments]

    def get_queryset(self):
        qs = OrganizationCompany.objects.all()
        org_id = self.request.query_params.get('organization')
        if org_id:
            qs = qs.filter(organization_id=org_id)
        if not self.request.user.is_superuser and self.request.user.company_id:
            qs = qs.filter(organization_id=self.request.user.company_id)
        return qs.order_by('company_name')


class EntityViewSet(viewsets.ModelViewSet):
    serializer_class = EntitySerializer
    permission_classes = [CanManageDepartments]

    def get_queryset(self):
        qs = Entity.objects.all()
        org_id = self.request.query_params.get('organization')
        if org_id:
            qs = qs.filter(organization_id=org_id)
        if not self.request.user.is_superuser and self.request.user.company_id:
            qs = qs.filter(organization_id=self.request.user.company_id)
        return qs.order_by('entity_name')


class EscalationRuleViewSet(viewsets.ModelViewSet):
    serializer_class = EscalationRuleSerializer
    permission_classes = [IsCompanyAdminOrCEO]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return EscalationRule.objects.all()
        return EscalationRule.objects.filter(company=user.company)

    def perform_create(self, serializer):
        user = self.request.user
        serializer.save(company=None if user.is_superuser else user.company)


class DepartmentViewSet(viewsets.ModelViewSet):
    """
    - Read: any authenticated user, scoped to their own company (SuperAdmin
      sees all, or a single company if `?company=<id>` is passed — this is
      how the Edit User dialog scopes the dropdown per selected organization).
    - Write: SuperAdmin (any company, must specify `company`) or an Admin with
      'can_manage_departments' (forced to their own company).
    """
    serializer_class = DepartmentSerializer
    permission_classes = [CanManageDepartments]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            qs = Department.objects.all().order_by('company_id', 'name')
            company_id = self.request.query_params.get('company')
            if company_id:
                qs = qs.filter(company_id=company_id)
            return qs
        if user.company_id:
            return Department.objects.filter(company=user.company)
        return Department.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        if user.is_superuser:
            serializer.save()  # `company` is required in the payload for superadmin
        else:
            serializer.save(company=user.company)


class RoleViewSet(viewsets.ModelViewSet):
    """
    Same `?company=<id>` scoping as DepartmentViewSet for superadmins, used
    by the Edit User dialog's Role dropdown.
    """
    serializer_class = RoleSerializer
    permission_classes = [CanManageRoles]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            qs = Role.objects.all().order_by('company_id', 'name')
            company_id = self.request.query_params.get('company')
            if company_id:
                qs = qs.filter(
                    db_models.Q(company_id=company_id) | db_models.Q(company__isnull=True)
                )
            return qs
        return Role.objects.filter(
            db_models.Q(company=user.company) | db_models.Q(company__isnull=True)
        )

    def perform_create(self, serializer):
        user = self.request.user
        if user.is_superuser:
            serializer.save()
        else:
            serializer.save(company=user.company)


class UserViewSet(viewsets.ModelViewSet):
    """
    - Read: SuperAdmin sees everyone; Admins see only their own company's users.
    - Create: UserCreateSerializer — role/department as free text, resolved-
      or-created scoped to the target company.
    - Update: UserUpdateSerializer — role/department as existing FK ids
      (Edit User dialog dropdowns), with company reassignment allowed for
      superadmins.
    """
    permission_classes = [IsCompanyAdminOrCEO]

    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        if self.action in ('update', 'partial_update'):
            return UserUpdateSerializer
        return UserSerializer

    def get_queryset(self):
        user = self.request.user
        base = User.objects.select_related('company', 'role', 'department').order_by('-date_joined')
        if user.is_superuser:
            return base
        if user.company_id:
            return base.filter(company=user.company)
        return User.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        if user.is_superuser:
            serializer.save()
        else:
            serializer.save(company=user.company)


class InvitationViewSet(viewsets.ModelViewSet):
    """
    Same endpoint/mechanism for both:
    - SuperAdmin inviting a new Admin into any organization
    - Admin inviting a new User into their own organization
    Scoping of who can invite into which company is entirely dynamic —
    see InvitationSerializer.validate() and get_queryset() below. role/
    department are free text here (not FK dropdowns) and are resolved-or-
    created against the selected company at save time. PATCH is allowed
    so a pending invite's details can be corrected before it's accepted.
    """
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']
    serializer_class = InvitationSerializer
    permission_classes = [CanManageInvitations]

    @staticmethod
    def _resolve_accept_base_url(request):
        """
        Build the "/accept-invite" base URL dynamically instead of relying on
        a hardcoded/env-pinned value, so invite links automatically point at
        whatever domain the app is actually deployed on.

        The browser that called this endpoint (the admin creating/resending
        the invite) sends an Origin header equal to the live frontend's
        origin — that's the same origin CORS_ALLOWED_ORIGINS already has to
        trust for the request to have succeeded at all, so it's safe to
        reuse here rather than asking a human to type the domain into .env.
        Falls back to FRONTEND_ACCEPT_INVITE_URL (or localhost) only if no
        usable Origin/Referer is present, e.g. invites triggered outside a
        browser context (management command, server-to-server call, etc).
        """
        origin = request.headers.get("Origin") or request.headers.get("Referer")
        if origin:
            parsed = urlparse(origin)
            if parsed.scheme and parsed.netloc:
                candidate = f"{parsed.scheme}://{parsed.netloc}"
                allowed_origins = getattr(settings, "CORS_ALLOWED_ORIGINS", [])
                if candidate in allowed_origins:
                    return f"{candidate}/accept-invite"

        return getattr(settings, "FRONTEND_ACCEPT_INVITE_URL", "http://localhost:5173/accept-invite")

    def get_queryset(self):
        user = self.request.user
        base = Invitation.objects.select_related('company', 'role', 'department', 'invited_by').order_by('-created_at')
        if user.is_superuser:
            return base
        if user.company_id:
            return base.filter(company=user.company)
        return Invitation.objects.none()

    def perform_create(self, serializer):
        invitation = serializer.save()
        accept_base_url = self._resolve_accept_base_url(self.request)
        accept_url = f"{accept_base_url}?token={invitation.token}"
        send_invitation_email(invitation, accept_url)
        send_invitation_sms(invitation, accept_url)

    @action(detail=True, methods=['post'])
    def resend(self, request, pk=None):
        """
        POST /invitations/{id}/resend/

        Re-sends the invite email/sms using the same token, pushes
        expires_at out to another INVITATION_EXPIRY_DAYS from *now*, and
        resets status back to pending if it had lapsed to expired. Invites
        that were already accepted or revoked can't be resent.
        """
        invitation = self.get_object()
        if invitation.status not in (Invitation.Status.PENDING, Invitation.Status.EXPIRED):
            return Response(
                {"detail": f"Cannot resend an invitation that is already {invitation.get_status_display()}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        days = getattr(settings, "INVITATION_EXPIRY_DAYS", 7)
        invitation.expires_at = timezone.now() + timedelta(days=days)
        invitation.status = Invitation.Status.PENDING
        invitation.save(update_fields=['expires_at', 'status'])

        accept_base_url = self._resolve_accept_base_url(request)
        accept_url = f"{accept_base_url}?token={invitation.token}"
        send_invitation_email(invitation, accept_url)
        send_invitation_sms(invitation, accept_url)

        return Response(InvitationSerializer(invitation, context={'request': request}).data)


class InvitationPreviewView(APIView):
    """
    Public — the invitee isn't authenticated yet. Lets the Accept Invite
    landing page show who/what the invite is for (organization, prefilled
    username) before anything is submitted.
    """
    permission_classes = [AllowAny]

    def get(self, request, token):
        try:
            invitation = Invitation.objects.select_related('company').get(token=token)
        except Invitation.DoesNotExist:
            return Response({"detail": "Invalid invitation link."}, status=status.HTTP_404_NOT_FOUND)
        return Response(InvitationPreviewSerializer(invitation).data)


class AcceptInvitationView(APIView):
    """Public — the invitee isn't authenticated yet. They set their own username/password here."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = AcceptInvitationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invitation = serializer.validated_data['invitation']
        user = serializer.save()

        # Notify whoever sent the invite (if they're not a SuperAdmin
        # themselves — they'll already get one below), plus every
        # SuperAdmin, now that the invite has been accepted.
        display_name = user.name or user.username
        verb = "accepted their invitation"
        description = f"{display_name} accepted the invitation to join {invitation.company.name} and is now a member."
        if invitation.invited_by_id and not invitation.invited_by.is_superuser:
            notify(invitation.invited_by, verb, actor=user, description=description)
        notify_superadmins(verb, actor=user, description=description)

        return Response(
            {**_tokens_for(user), "user": UserSerializer(user, context={'request': request}).data},
            status=status.HTTP_201_CREATED,
        )
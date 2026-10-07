from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models
from django.utils import timezone
from rest_framework import serializers

from .models import (
    Company,
    Department,
    Entity,
    EscalationRule,
    Invitation,
    OrganizationCompany,
    PasswordResetOTP,
    Role,
    User,
)

class CompanySerializer(serializers.ModelSerializer):
    """
    This is the tenant model, but it's also what the frontend calls an
    "Organization" — `company_count` / `entity_count` roll up the child
    OrganizationCompany / Entity records for the General Settings list.
    """
    company_count = serializers.IntegerField(source='companies.count', read_only=True)
    entity_count = serializers.IntegerField(source='entities.count', read_only=True)
    created_by_name = serializers.CharField(source='created_by.name', read_only=True)

    class Meta:
        model = Company
        fields = [
            'id', 'name', 'logo', 'address', 'company_count', 'entity_count',
            'subdomain', 'is_active', 'created_at', 'created_by', 'created_by_name',
        ]
        read_only_fields = ['subdomain', 'created_by', 'created_by_name', 'created_at']


class OrganizationCompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationCompany
        fields = [
            'id', 'organization', 'company_name', 'state', 'pin_code',
            'zone', 'region', 'country', 'sub_domain',
        ]


class EntitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Entity
        fields = ['id', 'organization', 'entity_name', 'state', 'region', 'zone']


class EscalationRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = EscalationRule
        fields = ['id', 'level', 'role', 'days', 'description']


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ['id', 'name', 'company']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if request and request.user.is_authenticated and not request.user.is_superuser:
            self.fields['company'].read_only = True


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ['id', 'name', 'permissions', 'company']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if request and request.user.is_authenticated and not request.user.is_superuser:
            self.fields['company'].read_only = True


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        username = data.get("username")
        password = data.get("password")
        if not username or not password:
            raise serializers.ValidationError("Username and password are required")
        user = authenticate(username=username, password=password)
        if not user:
            raise serializers.ValidationError("Invalid credentials")
        if not user.is_active:
            raise serializers.ValidationError("User account is disabled")
        data["user"] = user
        return data


class UserSerializer(serializers.ModelSerializer):
    """
    Read-shape used everywhere except update — role/department render as
    plain display strings and are read-only here.
    """
    company_name = serializers.CharField(source='company.name', read_only=True)
    role = serializers.CharField(source='role.name', read_only=True, default='')
    department = serializers.CharField(source='department.name', read_only=True, default='')
    activity_status = serializers.SerializerMethodField()
    # ✅ FIXED — the frontend's AdminRoute guard (App.tsx / AuthContext.tsx)
    # gates access to /admin on `user.can_manage_users`, but this serializer
    # never sent that field, so it was always `undefined` in the browser.
    # SuperAdmins still reached /admin because `is_superuser` alone let them
    # through; a plain Admin whose access comes from their Role's
    # `can_manage_users` permission (see accounts.constants.Perms) had no
    # way to pass the check and was silently redirected to "/" (Dashboard)
    # every time they clicked Admin. Reuses the existing
    # User.has_perm_codename() helper — same permission check `permissions.py`
    # already enforces server-side — so this is just exposing it to the client.
    can_manage_users = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'name', 'phone_number', 'role',
            'department', 'company', 'company_name', 'is_active',
            'is_superuser', 'last_login', 'activity_status', 'can_manage_users',
        ]
        read_only_fields = [
            'last_login', 'is_superuser', 'company_name', 'activity_status',
            'can_manage_users',
        ]

    def get_activity_status(self, obj):
        return "Active" if obj.is_active else "Inactive"

    def get_can_manage_users(self, obj):
        from .constants import Perms
        return obj.has_perm_codename(Perms.MANAGE_USERS)


class UserCreateSerializer(serializers.ModelSerializer):
    """
    `role` / `department` arrive as free-text names from the Add User form
    (not IDs), so creation resolves-or-creates them scoped to the target
    company. No hardcoded company logic — it's all driven off
    request.user.company at serializer init/validate time.
    """
    password = serializers.CharField(write_only=True, min_length=6)
    role = serializers.CharField(required=False, allow_blank=True)
    department = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'name', 'phone_number', 'role', 'department', 'company', 'password']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if request and request.user.is_authenticated and not request.user.is_superuser:
            self.fields.pop('company', None)

    def validate(self, attrs):
        request = self.context['request']
        company = attrs.get('company') if request.user.is_superuser else request.user.company
        attrs['_company'] = company
        return attrs

    def create(self, validated_data):
        company = validated_data.pop('_company', None)
        role_name = validated_data.pop('role', '').strip()
        dept_name = validated_data.pop('department', '').strip()
        validated_data['company'] = company

        if role_name:
            role, _ = Role.objects.get_or_create(name=role_name, company=company)
            validated_data['role'] = role
        if dept_name and company:
            dept, _ = Department.objects.get_or_create(name=dept_name, company=company)
            validated_data['department'] = dept

        return User.objects.create_user(**validated_data)


class ForgotPasswordSerializer(serializers.Serializer):
    """
    Step 1 of the reset flow. Always resolves to a generic success response
    from the view regardless of whether the email matches an account, so
    this endpoint can't be used to enumerate registered emails. Validation
    here just resolves (or fails to resolve) the target user onto
    `validated_data['user']` — the view decides what to tell the caller.
    """
    email = serializers.EmailField()

    def validate(self, attrs):
        attrs["user"] = User.objects.filter(email__iexact=attrs["email"], is_active=True).first()
        return attrs


class VerifyOTPSerializer(serializers.Serializer):
    """Step 2: confirms the code the user typed matches a live, unused OTP."""
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6, min_length=6)

    def validate(self, attrs):
        user = User.objects.filter(email__iexact=attrs["email"], is_active=True).first()
        if not user:
            raise serializers.ValidationError({"otp": "Invalid or expired code."})

        record = (
            PasswordResetOTP.objects.filter(user=user, otp_code=attrs["otp"], is_used=False)
            .order_by("-created_at")
            .first()
        )
        if not record:
            raise serializers.ValidationError({"otp": "Invalid or expired code."})
        if record.is_expired:
            raise serializers.ValidationError({"otp": "This code has expired. Please request a new one."})

        attrs["user"] = user
        attrs["record"] = record
        return attrs


class ResetPasswordSerializer(serializers.Serializer):
    """
    Step 3: re-validates the same OTP (it must already have been confirmed
    via VerifyOTPSerializer) and sets the new password. The OTP is consumed
    (`is_used=True`) on success so it can't be replayed.
    """
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6, min_length=6)
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})

        user = User.objects.filter(email__iexact=attrs["email"], is_active=True).first()
        if not user:
            raise serializers.ValidationError({"otp": "Invalid or expired code."})

        record = (
            PasswordResetOTP.objects.filter(user=user, otp_code=attrs["otp"], is_used=False)
            .order_by("-created_at")
            .first()
        )
        if not record:
            raise serializers.ValidationError({"otp": "Invalid or expired code."})
        if record.is_expired:
            raise serializers.ValidationError({"otp": "This code has expired. Please request a new one."})
        if not record.is_verified:
            raise serializers.ValidationError({"otp": "Please verify the code before setting a new password."})

        try:
            validate_password(attrs["new_password"], user=user)
        except DjangoValidationError as e:
            raise serializers.ValidationError({"new_password": list(e.messages)})

        attrs["user"] = user
        attrs["record"] = record
        return attrs


class UserUpdateSerializer(serializers.ModelSerializer):
    """
    Used for PATCH/PUT only (Edit User dialog). role/department are now
    PrimaryKeyRelatedFields pointing at EXISTING Role/Department rows — the
    Edit dialog sends the id chosen from a dropdown, not free text. This
    replaces the old resolve-or-create-by-name approach, which silently
    created junk roles/departments whenever the frontend sent an id (e.g.
    "5") instead of a name. username is writable and checked for uniqueness
    (excluding the current instance). Non-superadmins get their `role` /
    `department` querysets scoped to their own company and can't reassign a
    user's company.
    """
    role = serializers.PrimaryKeyRelatedField(queryset=Role.objects.all(), required=False, allow_null=True)
    department = serializers.PrimaryKeyRelatedField(queryset=Department.objects.all(), required=False, allow_null=True)
    company_name = serializers.CharField(source='company.name', read_only=True)
    role_name = serializers.CharField(source='role.name', read_only=True, default='')
    department_name = serializers.CharField(source='department.name', read_only=True, default='')
    activity_status = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'name', 'phone_number',
            'role', 'role_name', 'department', 'department_name',
            'company', 'company_name', 'is_active', 'is_superuser',
            'last_login', 'activity_status',
        ]
        read_only_fields = [
            'last_login', 'is_superuser', 'company_name',
            'role_name', 'department_name', 'activity_status',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if request and request.user.is_authenticated and not request.user.is_superuser:
            # Non-superadmins can't reassign a user's company.
            self.fields.pop('company', None)
            # Scope the dropdown querysets to the admin's own company
            # (plus global/company=None roles, e.g. SuperAdmin-defined ones).
            company = request.user.company
            self.fields['role'].queryset = Role.objects.filter(
                models.Q(company=company) | models.Q(company__isnull=True)
            )
            self.fields['department'].queryset = Department.objects.filter(company=company)

    def validate_username(self, value):
        qs = User.objects.filter(username=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Username already taken.")
        return value

    def update(self, instance, validated_data):
        # role/department are now real FK objects (PrimaryKeyRelatedField
        # already resolved them) — plain attribute assignment is enough.
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance

    def get_activity_status(self, obj):
        return "Active" if obj.is_active else "Inactive"


class InvitationSerializer(serializers.ModelSerializer):
    """
    Same invite mechanism whether SuperAdmin is inviting an Admin into a new
    organization, or an Admin is inviting a User into their own organization —
    scoping is entirely dynamic based on who's making the request.

    name/username are OPTIONAL prefill hints for the invitee — they still
    set their own final username at accept time (AcceptInvitationSerializer),
    but these seed the accept form and get used as fallback defaults if the
    invitee leaves them blank. role/department are free text, resolved-or-
    created scoped to the target company, same pattern as UserCreateSerializer.

    NOTE: `role` and `department` are write_only — they're inputs used to
    resolve/create the actual Role/Department, not display fields. Read
    `role_name` / `department_name` back instead.
    """
    company_name = serializers.CharField(source='company.name', read_only=True)
    role_name = serializers.CharField(source='role.name', read_only=True, default='')
    department_name = serializers.CharField(source='department.name', read_only=True, default='')
    invited_by_name = serializers.SerializerMethodField()
    role = serializers.CharField(required=False, allow_blank=True, write_only=True)
    department = serializers.CharField(required=False, allow_blank=True, write_only=True)
    name = serializers.CharField(required=False, allow_blank=True)
    username = serializers.CharField(required=False, allow_blank=True)
    token = serializers.CharField(read_only=True)
    accept_url = serializers.SerializerMethodField()

    class Meta:
        model = Invitation
        fields = [
            'id', 'email', 'phone_number', 'name', 'username', 'company', 'company_name',
            'role', 'role_name', 'department', 'department_name',
            'invited_by', 'invited_by_name', 'status', 'created_at', 'expires_at',
            'token', 'accept_url',
        ]
        read_only_fields = [
            'invited_by', 'invited_by_name', 'status', 'created_at', 'expires_at',
            'company_name', 'role_name', 'department_name',
            'token', 'accept_url',
        ]
        validators = []

    def get_accept_url(self, obj):
        request = self.context.get('request')
        base_url = ""
        if request:
            try:
                from accounts.views import InvitationViewSet
                base_url = InvitationViewSet._resolve_accept_base_url(request)
            except Exception:
                pass
        if not base_url:
            base_url = getattr(settings, "FRONTEND_ACCEPT_INVITE_URL", "https://rst.vibesandbox.live/accept-invite")
        return f"{base_url}?token={obj.token}"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if not (request and request.user.is_authenticated):
            return
        if not request.user.is_superuser and request.user.company_id:
            self.fields.pop('company', None)  # forced to inviter's own company in validate()

    def get_invited_by_name(self, obj):
        if not obj.invited_by:
            return ''
        # Fall back to username when the inviter's `name` field was never
        # populated (e.g. accounts created via createsuperuser).
        return obj.invited_by.name or obj.invited_by.username

    def validate(self, attrs):
        request = self.context['request']
        if not request.user.is_superuser:
            attrs['company'] = request.user.company

        company = attrs.get('company')
        if not company:
            raise serializers.ValidationError({"company": "An organization is required."})

        username = attrs.get('username', '').strip()
        if username and User.objects.filter(username=username).exists():
            raise serializers.ValidationError({"username": "This username is already taken."})

        return attrs

    def create(self, validated_data):
        email = validated_data.get('email')
        company = validated_data.get('company')
        role_name = validated_data.pop('role', '').strip()
        dept_name = validated_data.pop('department', '').strip()

        if role_name:
            role, _ = Role.objects.get_or_create(name=role_name, company=company)
            validated_data['role'] = role
        if dept_name:
            dept, _ = Department.objects.get_or_create(name=dept_name, company=company)
            validated_data['department'] = dept

        validated_data['invited_by'] = self.context['request'].user

        # If an invitation already exists for this email & company, renew it seamlessly
        existing = Invitation.objects.filter(email=email, company=company).first()
        if existing:
            if existing.status == Invitation.Status.ACCEPTED:
                raise serializers.ValidationError({
                    "email": "This user has already accepted an invitation and is an active user in this organization."
                })
            for k, v in validated_data.items():
                setattr(existing, k, v)
            existing.status = Invitation.Status.PENDING
            existing.expires_at = timezone.now() + timedelta(days=getattr(settings, "INVITATION_EXPIRY_DAYS", 7))
            existing.save()
            return existing

        return Invitation.objects.create(**validated_data)


class InvitationPreviewSerializer(serializers.ModelSerializer):
    """
    Public, read-only shape for the Accept Invite landing page — no auth
    required (the invitee isn't logged in yet). Exposes only what's needed
    to show "You've been invited..." and to prefill the accept form.
    """
    company_name = serializers.CharField(source='company.name', read_only=True)
    role_name = serializers.CharField(source='role.name', read_only=True, default=None)
    department_name = serializers.CharField(source='department.name', read_only=True, default=None)
    is_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = Invitation
        fields = [
            'email', 'name', 'username', 'company_name', 'role_name',
            'department_name', 'status', 'expires_at', 'is_expired',
        ]


class AcceptInvitationSerializer(serializers.Serializer):
    """
    Public — the invitee isn't authenticated yet. username/name are now
    optional here: if the invite included a prefilled name/username, those
    are used as fallback defaults so the invitee doesn't have to retype
    them, but they can still override at accept time. If the invitation was
    seeded with a specific username, whatever the invitee submits must match
    it exactly, or the request is rejected with a "Login failed" message.
    """
    token = serializers.CharField()
    username = serializers.CharField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, min_length=6)
    name = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        try:
            invitation = Invitation.objects.select_related('company', 'role', 'department').get(token=attrs['token'])
        except Invitation.DoesNotExist:
            raise serializers.ValidationError({"token": "Invalid invitation link."})

        if invitation.status != Invitation.Status.PENDING:
            raise serializers.ValidationError({"token": "This invitation is no longer valid."})

        if invitation.is_expired:
            invitation.status = Invitation.Status.EXPIRED
            invitation.save(update_fields=['status'])
            raise serializers.ValidationError({"token": "This invitation has expired."})

        username = attrs.get('username', '').strip() or invitation.username
        if not username:
            raise serializers.ValidationError({"username": "Username is required."})

        # The invitee must confirm the exact username the invite was
        # addressed to. Enforced here (not just client-side) so a
        # mismatched username can't slip through a direct API call.
        if invitation.username and username != invitation.username:
            raise serializers.ValidationError(
                {"username": "Login failed. Username does not match this invitation."}
            )

        if User.objects.filter(username=username).exists():
            raise serializers.ValidationError({"username": "Username already taken."})

        attrs['username'] = username
        attrs['invitation'] = invitation
        return attrs

    def create(self, validated_data):
        invitation = validated_data['invitation']
        user = User.objects.create_user(
            username=validated_data['username'],
            password=validated_data['password'],
            email=invitation.email,
            phone_number=invitation.phone_number,
            name=(validated_data.get('name', '').strip() or invitation.name),
            company=invitation.company,
            role=invitation.role,
            department=invitation.department,
        )
        invitation.status = Invitation.Status.ACCEPTED
        invitation.accepted_by = user
        invitation.save(update_fields=['status', 'accepted_by'])
        return user
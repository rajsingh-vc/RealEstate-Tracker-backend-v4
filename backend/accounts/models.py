import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractUser, Permission
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class Company(models.Model):
    """
    Tenant / White-label organization. Only SuperAdmin can create these.

    This is also what the frontend calls an "Organization" — `address` and
    `logo` back the General Settings > Organizations screen, and
    `company_count` / `entity_count` (see CompanySerializer) roll up the
    child OrganizationCompany / Entity records below.
    """
    name = models.CharField(max_length=255)
    subdomain = models.CharField(max_length=100, unique=True, blank=True)
    address = models.TextField(blank=True, default='')
    logo = models.ImageField(upload_to='org_logos/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='companies_created',
        help_text="The SuperAdmin who created this organization."
    )

    def save(self, *args, **kwargs):
        if not self.subdomain:
            base = slugify(self.name)[:90] or "org"
            candidate, i = base, 1
            while Company.objects.filter(subdomain=candidate).exclude(pk=self.pk).exists():
                i += 1
                candidate = f"{base}-{i}"
            self.subdomain = candidate
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class OrganizationCompany(models.Model):
    """
    The frontend's nested "Company" record one level under an Organization
    (regional/legal entity metadata — NOT a tenant; unrelated to the
    `Company` model above despite the name clash from the frontend).
    """
    organization = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name='companies'
    )
    company_name = models.CharField(max_length=255)
    state = models.CharField(max_length=100, blank=True, default='')
    pin_code = models.CharField(max_length=20, blank=True, default='')
    zone = models.CharField(max_length=100, blank=True, default='')
    region = models.CharField(max_length=100, blank=True, default='')
    country = models.CharField(max_length=100, blank=True, default='')
    sub_domain = models.CharField(max_length=100, blank=True, default='')

    class Meta:
        verbose_name_plural = "organization companies"

    def __str__(self):
        return self.company_name


class Entity(models.Model):
    """The frontend's nested "Entity" record one level under an Organization."""
    organization = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name='entities'
    )
    entity_name = models.CharField(max_length=255)
    state = models.CharField(max_length=100, blank=True, default='')
    region = models.CharField(max_length=100, blank=True, default='')
    zone = models.CharField(max_length=100, blank=True, default='')

    class Meta:
        verbose_name_plural = "entities"

    def __str__(self):
        return self.entity_name


class EscalationRule(models.Model):
    """
    Backs the Admin > Escalation Matrix tab. `company=None` means a global
    rule set by SuperAdmin; otherwise scoped to a single tenant.
    """
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, null=True, blank=True,
        related_name='escalation_rules'
    )
    level = models.PositiveIntegerField()
    role = models.CharField(max_length=100)
    days = models.PositiveIntegerField()
    description = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['level']

    def __str__(self):
        return f"L{self.level} — {self.role}"


class Role(models.Model):
    """
    Dynamic role with associated permissions.
    A role can be global (company=None, e.g. SuperAdmin) or tenant-specific.
    """
    name = models.CharField(max_length=50)
    permissions = models.ManyToManyField(Permission, blank=True)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='roles',
        help_text="Null for global roles (e.g., SuperAdmin)"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('name', 'company')

    def __str__(self):
        return self.name


class Department(models.Model):
    """Tenant-scoped department. Every department belongs to exactly one company."""
    name = models.CharField(max_length=100)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='departments'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('name', 'company')

    def __str__(self):
        return f"{self.name} ({self.company.name})"


class User(AbstractUser):
    name = models.CharField(max_length=255, default='')
    # NOTE: overrides AbstractUser's default email field (which allows
    # duplicates) so that a personal email can never resolve to more than
    # one account. This is what the forgot-password lookup relies on to
    # find the right user, so it must be globally unique — not scoped to
    # `company`, since SuperAdmin has company=None.
    email = models.EmailField(unique=True, blank=True)
    phone_number = models.CharField(max_length=20, blank=True, default='')
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='users',
        help_text="Null for SuperAdmin"
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users'
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users'
    )

    def has_perm_codename(self, codename):
        """Dynamic permission check off the user's Role. SuperAdmin always passes."""
        if self.is_superuser:
            return True
        if self.role_id:
            return self.role.permissions.filter(codename=codename).exists()
        return False

    def __str__(self):
        return f"{self.username} ({self.role.name if self.role else 'No Role'})"


class PasswordResetOTP(models.Model):
    """
    One-time password used to drive the "Forgot password" flow:
      1. POST /auth/forgot-password/  -> creates a row here, emails `otp_code`.
      2. POST /auth/verify-otp/       -> marks `is_verified` once the code
         the user typed matches and hasn't expired/been used.
      3. POST /auth/reset-password/   -> re-checks the same row is verified
         and unused, sets the new password, then marks `is_used`.

    Rows aren't deleted after use — they're just marked used/expired — so
    there's a natural audit trail of reset attempts per user.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='password_reset_otps'
    )
    otp_code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_verified = models.BooleanField(default=False)
    is_used = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.expires_at:
            minutes = getattr(settings, "PASSWORD_RESET_OTP_EXPIRY_MINUTES", 10)
            self.expires_at = timezone.now() + timedelta(minutes=minutes)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @staticmethod
    def generate_code():
        return f"{secrets.randbelow(1_000_000):06d}"

    def __str__(self):
        return f"OTP for {self.user.username} ({'used' if self.is_used else 'active'})"


class Invitation(models.Model):
    """
    Generic onboarding invite — used both when SuperAdmin invites a new Admin
    into an organization, and when an Admin invites a new User into their own
    organization. Nothing here is role-specific or hardcoded: `company`,
    `role`, and `department` are just whichever ones the inviter picked (or,
    for a non-superadmin inviter, whichever ones the serializer forces to
    their own company).

    The invitee never receives a password from anyone — they set their own
    via the accept-invite endpoint, using `token` as proof of the invite.
    """

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        ACCEPTED = 'accepted', 'Accepted'
        EXPIRED = 'expired', 'Expired'
        REVOKED = 'revoked', 'Revoked'

    name = models.CharField(max_length=150, blank=True)
    username = models.CharField(max_length=150, blank=True)
    email = models.EmailField()
    phone_number = models.CharField(max_length=20, blank=True)
    token = models.CharField(max_length=64, unique=True, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='invitations')
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True, related_name='invitations')
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='invitations')
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='invitations_sent'
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    accepted_by = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='accepted_invitation'
    )

    class Meta:
        unique_together = ('email', 'company')

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(32)
        if not self.expires_at:
            days = getattr(settings, "INVITATION_EXPIRY_DAYS", 7)
            self.expires_at = timezone.now() + timedelta(days=days)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"{self.email} -> {self.company.name} ({self.status})"
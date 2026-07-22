from django.conf import settings
from django.db import models


class EscalationRule(models.Model):
    """Backs the "Escalation Matrix" tab in src/pages/Admin.tsx."""

    level = models.PositiveSmallIntegerField(unique=True)
    role = models.CharField(max_length=64)
    days = models.PositiveSmallIntegerField()
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["level"]

    def __str__(self):
        return f"L{self.level} - {self.role}"


class Organization(models.Model):
    """
    Backs the "Organizations" section of the General Settings screen.
    The tenant root: every Company and Entity belongs to exactly one of
    these via `organization`.
    """

    name = models.CharField(max_length=255)
    logo = models.ImageField(upload_to="organization_logos/", blank=True, null=True)
    address = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="organizations_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Company(models.Model):
    """A company belonging to an Organization. Always created/listed scoped
    to its parent organization — never on its own."""

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="companies")
    company_name = models.CharField(max_length=255)
    state = models.CharField(max_length=128)
    pin_code = models.CharField(max_length=16)
    zone = models.CharField(max_length=128)
    region = models.CharField(max_length=128)
    country = models.CharField(max_length=128)
    sub_domain = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["company_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "sub_domain"], name="unique_subdomain_per_organization"
            )
        ]

    def __str__(self):
        return self.company_name


class Entity(models.Model):
    """An entity belonging to an Organization. Always created/listed scoped
    to its parent organization — never on its own."""

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="entities")
    entity_name = models.CharField(max_length=255)
    state = models.CharField(max_length=128)
    region = models.CharField(max_length=128)
    zone = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["entity_name"]
        verbose_name_plural = "entities"

    def __str__(self):
        return self.entity_name
from django.db import models

# NOTE: Project.organization/company/entity intentionally target the
# `accounts` app's models, aliased below to keep every reference in this
# file (Organization/Company/Entity) unchanged. This is NOT the same as
# `adminpanel.models.Organization/Company/Entity`, which define an
# identically-shaped, identically-named parallel set of models — but whose
# API routes (/api/organizations/, /api/companies/, /api/entities/) are
# silently shadowed by accounts.urls (registered first in config/urls.py),
# so the adminpanel versions are never actually reachable or populated.
# accounts.Company doubles as "Organization" in this app (see its
# docstring); accounts.OrganizationCompany is the nested "Company" record.
from accounts.models import Company as Organization
from accounts.models import OrganizationCompany as Company
from accounts.models import Entity


class Project(models.Model):
    HIERARCHY_FULL = "full"
    HIERARCHY_DIRECT_TASK = "direct_task"
    HIERARCHY_CHOICES = [
        (HIERARCHY_FULL, "Full Hierarchy (Tower → Floor → Unit → Task)"),
        (HIERARCHY_DIRECT_TASK, "Direct to Task"),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="projects",
        null=True,
        blank=True,
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="projects",
        null=True,
        blank=True,
    )
    entity = models.ForeignKey(
        Entity,
        on_delete=models.SET_NULL,
        related_name="projects",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=255)
    location = models.CharField(max_length=255)
    status = models.CharField(max_length=64, default="Planning", blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    progress = models.PositiveSmallIntegerField(default=0)
    total_units = models.PositiveIntegerField(default=0)
    rera_number = models.CharField(max_length=64, blank=True)
    developer = models.CharField(max_length=255, blank=True, default="Vibe Group")
    budget = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    spent = models.DecimalField(max_digits=16, decimal_places=2, default=0)

    # ✅ NEW — determines whether this project uses Tower→Floor→Unit→Task,
    # or lets tasks attach directly to the project. Read by both the
    # frontend router and (optionally) task-level validation — single
    # source of truth stored on the project itself, not a global setting.
    hierarchy_mode = models.CharField(
        max_length=20, choices=HIERARCHY_CHOICES, default=HIERARCHY_FULL
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class Tower(models.Model):
    project = models.ForeignKey(Project, related_name="towers", on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    total_floors = models.PositiveIntegerField(default=0)
    progress = models.PositiveSmallIntegerField(default=0)
    status = models.CharField(max_length=64, default="Planning")

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.name} ({self.project.name})"


class Floor(models.Model):
    tower = models.ForeignKey(Tower, related_name="floors", on_delete=models.CASCADE)
    project = models.ForeignKey(Project, related_name="floors", on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    number = models.IntegerField()

    class Meta:
        ordering = ["number"]

    def __str__(self):
        return f"{self.name} - {self.tower.name}"


class Unit(models.Model):
    floor = models.ForeignKey(Floor, related_name="units", on_delete=models.CASCADE)
    tower = models.ForeignKey(Tower, related_name="units", on_delete=models.CASCADE)
    project = models.ForeignKey(Project, related_name="units", on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=32, blank=True)
    area = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=32, default="available", blank=True)
    progress = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.name
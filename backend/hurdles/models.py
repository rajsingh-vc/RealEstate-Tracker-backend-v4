from django.db import models

from projects.models import Project
from tasks.models import Task


from accounts.models import Company


class HurdleSeverity(models.TextChoices):
    CRITICAL = "critical", "Critical"
    HIGH = "high", "High"
    MEDIUM = "medium", "Medium"
    LOW = "low", "Low"


class HurdleStatus(models.TextChoices):
    OPEN = "open", "Open"
    IN_PROGRESS = "in_progress", "In Progress"
    RESOLVED = "resolved", "Resolved"
    ESCALATED = "escalated", "Escalated"


class Hurdle(models.Model):
    """Mirrors the `Hurdle` interface in src/data/demo-data.ts."""

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    # ✅ UPDATED: free text instead of a fixed HurdleType.choices set, to
    # match the frontend's free-text "Hurdle Type" input. No longer
    # constrained to a hardcoded list of known types.
    type = models.CharField(max_length=100)
    affected_task = models.ForeignKey(
        Task, related_name="hurdles", null=True, blank=True, on_delete=models.SET_NULL
    )
    # Kept as free text (not a Tower FK) because the frontend's ReportHurdleDialog
    # stores the tower's display name (e.g. "Tower A"), and towers are not
    # globally unique by name across projects.
    affected_tower = models.CharField(max_length=255, blank=True)
    # ✅ UPDATED: free text instead of Department.choices, to match the
    # frontend's free-text "Responsible Department" input. No longer
    # constrained to a hardcoded department list.
    responsible_department = models.CharField(max_length=100)
    impact_days = models.PositiveIntegerField(default=0)
    severity = models.CharField(max_length=16, choices=HurdleSeverity.choices, default=HurdleSeverity.MEDIUM)
    status = models.CharField(max_length=16, choices=HurdleStatus.choices, default=HurdleStatus.OPEN)
    resolution_notes = models.TextField(blank=True)
    project = models.ForeignKey(Project, related_name="hurdles", on_delete=models.CASCADE)
    reported_date = models.DateField(auto_now_add=True)
    resolved_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-reported_date"]

    def __str__(self):
        return self.title
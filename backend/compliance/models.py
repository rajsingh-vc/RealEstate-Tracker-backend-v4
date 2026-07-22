from django.db import models

from projects.models import Project

from accounts.models import Company


    
class ComplianceStatus(models.TextChoices):
    COMPLETED = "completed", "Completed"
    IN_PROGRESS = "in_progress", "In Progress"
    PENDING = "pending", "Pending"
    NOT_STARTED = "not_started", "Not Started"


class ComplianceItem(models.Model):
    """Backs src/pages/Compliance.tsx."""

    name = models.CharField(max_length=255)
    project = models.ForeignKey(Project, related_name="compliance_items", on_delete=models.CASCADE)
    status = models.CharField(max_length=16, choices=ComplianceStatus.choices, default=ComplianceStatus.NOT_STARTED)
    progress = models.PositiveSmallIntegerField(default=0)
    due_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["due_date"]

    def __str__(self):
        return f"{self.name} - {self.project.name}"

from django.db import models

from projects.models import Project, Unit

from accounts.models import Company



    
class HandoverStatus(models.TextChoices):
    SNAGGING = "snagging", "Snagging"
    INSPECTION = "inspection", "Inspection"
    NOT_READY = "not_ready", "Not Ready"
    HANDED_OVER = "handed_over", "Handed Over"


class HandoverUnit(models.Model):
    """Backs src/pages/Handover.tsx.

    `unit`/`tower` are kept as display strings (matching the frontend form)
    rather than forcing a strict FK to `projects.Unit`, since handover often
    starts being tracked before the digital-twin unit records exist. `unit_ref`
    is an optional FK for when you *do* want to link it to a real Unit row.
    """

    unit = models.CharField(max_length=100)
    tower = models.CharField(max_length=100, blank=True)
    unit_ref = models.ForeignKey(
        Unit, related_name="handover_records", null=True, blank=True, on_delete=models.SET_NULL
    )
    project = models.ForeignKey(Project, related_name="handover_units", on_delete=models.CASCADE)
    status = models.CharField(max_length=16, choices=HandoverStatus.choices, default=HandoverStatus.NOT_READY)
    progress = models.PositiveSmallIntegerField(default=0)
    buyer = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.unit} - {self.project.name}"

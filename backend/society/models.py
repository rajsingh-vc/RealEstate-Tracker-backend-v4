from django.db import models

from projects.models import Project
from accounts.models import Company


class SocietyStatus(models.TextChoices):
    IN_FORMATION = "in_formation", "In Formation"
    REGISTERED = "registered", "Registered"
    COMMITTEE_FORMED = "committee_formed", "Committee Formed"


class Society(models.Model):
    """Backs src/pages/Society.tsx."""

    name = models.CharField(max_length=255)
    project = models.ForeignKey(Project, related_name="societies", on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=SocietyStatus.choices, default=SocietyStatus.IN_FORMATION)
    progress = models.PositiveSmallIntegerField(default=0)

    def __str__(self):
        return self.name

    def recalculate_progress(self):
        steps = list(SocietyStep.objects.filter(society=self))
        if not steps:
            self.progress = 0
        else:
            done = sum(1 for s in steps if s.completed)
            self.progress = round((done / len(steps)) * 100)
        self.save(update_fields=["progress"])


class SocietyStep(models.Model):
    society = models.ForeignKey(Society, related_name="steps", on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    completed = models.BooleanField(default=False)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.name

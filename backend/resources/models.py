from django.db import models

from tasks.models import Task
from accounts.models import Company



class Resource(models.Model):
    """Mirrors the `Resource` interface (one allocation record per task)."""

    task = models.ForeignKey(Task, related_name="resource_allocations", on_delete=models.CASCADE)
    labour = models.PositiveIntegerField(default=0)
    vendor = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"Resources for {self.task.title}"


class ResourceMachine(models.Model):
    resource = models.ForeignKey(Resource, related_name="machines", on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    qty = models.PositiveIntegerField(default=1)


class ResourceMaterial(models.Model):
    resource = models.ForeignKey(Resource, related_name="materials", on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    qty = models.PositiveIntegerField(default=1)
    unit = models.CharField(max_length=32, blank=True)

# documents/models.py
from django.db import models
from projects.models import Project
from accounts.models import Company
from compliance.models import ComplianceItem
# 👇 new import
from handover.models import HandoverUnit   # adjust import to your app


def document_upload_path(instance, filename):
    # Optionally include handover in the path
    if instance.compliance_id:
        return f"documents/project_{instance.project_id}/compliance_{instance.compliance_id}/{filename}"
    if instance.handover_id:
        return f"documents/project_{instance.project_id}/handover_{instance.handover_id}/{filename}"
    return f"documents/project_{instance.project_id}/{filename}"


class Document(models.Model):
    name = models.CharField(max_length=255)
    file = models.FileField(upload_to=document_upload_path)
    type = models.CharField(max_length=16, blank=True)
    category = models.CharField(max_length=100, blank=True, default="General")
    project = models.ForeignKey(
        Project, related_name="documents", on_delete=models.CASCADE, null=True, blank=True
    )
    compliance = models.ForeignKey(
        ComplianceItem,
        related_name="documents",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    # 👇 new handover field
    handover = models.ForeignKey(
        HandoverUnit,
        related_name="documents",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    size_bytes = models.PositiveIntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def save(self, *args, **kwargs):
        if self.file:
            self.size_bytes = self.file.size
            ext = self.file.name.rsplit(".", 1)[-1].upper() if "." in self.file.name else ""
            self.type = self.type or ext
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class DocumentExtraction(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("extracted", "Extracted"),
        ("validated", "Validated"),
        ("imported", "Imported"),
        ("failed", "Failed"),
    ]
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="extractions")
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default="pending")
    doc_type = models.CharField(max_length=64, default="construction_schedule")
    confidence_score = models.FloatField(default=0.0)
    detected_project_name = models.CharField(max_length=255, blank=True)
    detected_status_date = models.DateField(null=True, blank=True)
    raw_data = models.JSONField(default=dict, blank=True)
    normalized_data = models.JSONField(default=dict, blank=True)
    validation_results = models.JSONField(default=dict, blank=True)
    import_summary = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    imported_project = models.ForeignKey(
        Project, null=True, blank=True, on_delete=models.SET_NULL, related_name="extractions"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Extraction {self.id} for Document {self.document_id} ({self.status})"
# documents/models.py
from django.conf import settings
from django.db import models
from projects.models import Project
from accounts.models import Company
from compliance.models import ComplianceItem
from handover.models import HandoverUnit


def document_upload_path(instance, filename):
    if instance.compliance_id:
        return f"documents/project_{instance.project_id}/compliance_{instance.compliance_id}/{filename}"
    if instance.handover_id:
        return f"documents/project_{instance.project_id}/handover_{instance.handover_id}/{filename}"
    return f"documents/project_{instance.project_id}/{filename}"


class Document(models.Model):
    name = models.CharField(max_length=255)
    original_filename = models.CharField(max_length=255, blank=True)
    file = models.FileField(upload_to=document_upload_path)
    type = models.CharField(max_length=32, blank=True)
    mime_type = models.CharField(max_length=128, blank=True)
    category = models.CharField(max_length=100, blank=True, default="General")
    description = models.TextField(blank=True, default="")
    tags = models.JSONField(default=list, blank=True)
    version = models.PositiveIntegerField(default=1)
    parent_document = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="versions"
    )
    processing_status = models.CharField(
        max_length=32,
        choices=[
            ("ready", "Ready"),
            ("queued", "Queued"),
            ("processing", "Processing"),
            ("completed", "Completed"),
            ("failed", "Failed"),
        ],
        default="ready",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="uploaded_documents",
    )
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
            if not self.original_filename:
                self.original_filename = self.file.name.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
            ext = self.file.name.rsplit(".", 1)[-1].upper() if "." in self.file.name else ""
            self.type = self.type or ext
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} (v{self.version})"


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


class ScheduleImport(models.Model):
    STATUS_CHOICES = [
        ("uploaded", "Uploaded"),
        ("queued", "Queued"),
        ("processing", "Processing"),
        ("awaiting_confirmation", "Awaiting Confirmation"),
        ("completed", "Completed"),
        ("completed_with_warnings", "Completed with Warnings"),
        ("failed", "Failed"),
    ]

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="schedule_imports")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="schedule_imports")
    version_label = models.CharField(max_length=64, default="v1.0")
    file_format = models.CharField(max_length=32, default="MPP")
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default="uploaded")
    
    # High-level statistics: total tasks, subtasks, milestones, date span, duration, warnings
    parsed_summary = models.JSONField(default=dict, blank=True)
    # Structured normalized hierarchical tasks
    raw_tasks_data = models.JSONField(default=list, blank=True)
    error_message = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"ScheduleImport #{self.id} ({self.project.name} - {self.version_label} [{self.status}])"


class ScheduleVersion(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="schedule_versions")
    version_number = models.PositiveIntegerField(default=1)
    name = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    import_source = models.ForeignKey(
        ScheduleImport, on_delete=models.SET_NULL, null=True, blank=True, related_name="schedule_versions"
    )
    total_tasks = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-version_number"]
        unique_together = [("project", "version_number")]

    def __str__(self):
        return f"{self.project.name} - Version {self.version_number} (Active: {self.is_active})"


class ImportChangeLog(models.Model):
    CHANGE_CHOICES = [
        ("added", "Added"),
        ("modified", "Modified"),
        ("unchanged", "Unchanged"),
        ("removed", "Removed"),
    ]

    schedule_import = models.ForeignKey(ScheduleImport, on_delete=models.CASCADE, related_name="change_logs")
    change_type = models.CharField(max_length=16, choices=CHANGE_CHOICES)
    task_title = models.CharField(max_length=255)
    wbs_code = models.CharField(max_length=64, blank=True)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"[{self.change_type.upper()}] {self.wbs_code} - {self.task_title}"


class DigitalTwinTaskMapping(models.Model):
    task = models.ForeignKey("tasks.Task", on_delete=models.CASCADE, related_name="digital_twin_mappings")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="digital_twin_mappings")
    tower = models.ForeignKey(
        "projects.Tower", on_delete=models.SET_NULL, null=True, blank=True, related_name="digital_twin_mappings"
    )
    floor = models.ForeignKey(
        "projects.Floor", on_delete=models.SET_NULL, null=True, blank=True, related_name="digital_twin_mappings"
    )
    unit = models.ForeignKey(
        "projects.Unit", on_delete=models.SET_NULL, null=True, blank=True, related_name="digital_twin_mappings"
    )
    zone_name = models.CharField(max_length=128, blank=True)
    element_identifier = models.CharField(
        max_length=128, blank=True, help_text="3D mesh name, unit boundary, or building element identifier"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        unique_together = [("task", "element_identifier", "unit_id", "floor_id", "tower_id")]

    def __str__(self):
        return f"Mapping: Task {self.task_id} -> {self.element_identifier or self.zone_name or 'Zone'}"
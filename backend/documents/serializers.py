# documents/serializers.py
from rest_framework import serializers
from projects.models import Project, Tower, Floor, Unit
from compliance.models import ComplianceItem
from handover.models import HandoverUnit
from tasks.models import Task
from .models import (
    Document,
    ScheduleImport,
    ScheduleVersion,
    ImportChangeLog,
    DigitalTwinTaskMapping,
)


def _human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


class DocumentSerializer(serializers.ModelSerializer):
    project = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.all(), required=False, allow_null=True
    )
    compliance = serializers.PrimaryKeyRelatedField(
        queryset=ComplianceItem.objects.all(), required=False, allow_null=True
    )
    handover = serializers.PrimaryKeyRelatedField(
        queryset=HandoverUnit.objects.all(), required=False, allow_null=True
    )
    project_name = serializers.CharField(source="project.name", read_only=True)
    date = serializers.DateTimeField(source="uploaded_at", read_only=True, format="%Y-%m-%d")
    uploaded_by_name = serializers.CharField(source="uploaded_by.name", read_only=True)
    size = serializers.SerializerMethodField()
    is_schedule = serializers.SerializerMethodField()
    latest_schedule_import_id = serializers.SerializerMethodField()
    versions_count = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            "id", "name", "original_filename", "file", "type", "mime_type", "category",
            "description", "tags", "version", "parent_document", "processing_status",
            "project", "project_name", "compliance", "handover",
            "uploaded_by", "uploaded_by_name", "date", "size",
            "is_schedule", "latest_schedule_import_id", "versions_count",
        ]
        read_only_fields = ["type", "mime_type", "size"]

    def get_size(self, obj):
        return _human_size(obj.size_bytes)

    def get_is_schedule(self, obj):
        t = (obj.type or "").upper()
        ext = obj.file.name.rsplit(".", 1)[-1].upper() if obj.file else ""
        return t in ["MPP", "XML", "MSPDI", "XER"] or ext in ["MPP", "XML", "MSPDI", "XER"]

    def get_latest_schedule_import_id(self, obj):
        first_imp = obj.schedule_imports.first()
        return first_imp.id if first_imp else None

    def get_versions_count(self, obj):
        if obj.parent_document_id:
            return 1 + obj.parent_document.versions.count()
        return 1 + obj.versions.count()

    def validate(self, attrs):
        project = attrs.get("project")
        compliance = attrs.get("compliance")
        handover = attrs.get("handover")

        if not project and compliance:
            attrs["project"] = compliance.project
        if not project and handover:
            attrs["project"] = handover.project

        if not attrs.get("project"):
            raise serializers.ValidationError(
                {"project": "This field is required unless a compliance or handover item is provided."}
            )

        return attrs


class ScheduleImportSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    document_name = serializers.CharField(source="document.name", read_only=True)
    document_file = serializers.CharField(source="document.file.url", read_only=True)
    change_logs = serializers.SerializerMethodField()

    class Meta:
        model = ScheduleImport
        fields = [
            "id", "document", "document_name", "document_file", "project", "project_name",
            "version_label", "file_format", "status", "parsed_summary",
            "error_message", "change_logs", "created_at", "updated_at",
        ]

    def get_change_logs(self, obj):
        logs = obj.change_logs.all()[:30]
        return ImportChangeLogSerializer(logs, many=True).data


class ScheduleVersionSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)

    class Meta:
        model = ScheduleVersion
        fields = [
            "id", "project", "project_name", "version_number", "name",
            "is_active", "import_source", "total_tasks", "created_at",
        ]


class ImportChangeLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportChangeLog
        fields = [
            "id", "schedule_import", "change_type", "task_title",
            "wbs_code", "details", "created_at",
        ]


class DigitalTwinTaskMappingSerializer(serializers.ModelSerializer):
    task_title = serializers.CharField(source="task.title", read_only=True)
    task_wbs = serializers.CharField(source="task.wbs_code", read_only=True)
    task_status = serializers.CharField(source="task.status", read_only=True)
    task_progress = serializers.IntegerField(source="task.progress", read_only=True)
    task_start_date = serializers.DateField(source="task.start_date", read_only=True)
    task_end_date = serializers.DateField(source="task.end_date", read_only=True)
    tower_name = serializers.CharField(source="tower.name", read_only=True)
    floor_name = serializers.CharField(source="floor.name", read_only=True)
    unit_name = serializers.CharField(source="unit.name", read_only=True)

    class Meta:
        model = DigitalTwinTaskMapping
        fields = [
            "id", "task", "task_title", "task_wbs", "task_status", "task_progress",
            "task_start_date", "task_end_date", "project", "tower", "tower_name",
            "floor", "floor_name", "unit", "unit_name", "zone_name",
            "element_identifier", "created_at",
        ]
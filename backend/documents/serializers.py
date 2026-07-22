# documents/serializers.py
from rest_framework import serializers
from projects.models import Project
from compliance.models import ComplianceItem
from handover.models import HandoverUnit  # 👈 import
from .models import Document


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
    # 👇 new handover field
    handover = serializers.PrimaryKeyRelatedField(
        queryset=HandoverUnit.objects.all(), required=False, allow_null=True
    )
    project_name = serializers.CharField(source="project.name", read_only=True)
    date = serializers.DateTimeField(source="uploaded_at", read_only=True, format="%Y-%m-%d")
    size = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            "id", "name", "file", "type", "category",
            "project", "project_name", "compliance", "handover",  # 👈 added handover
            "date", "size",
        ]
        read_only_fields = ["type"]

    def get_size(self, obj):
        return _human_size(obj.size_bytes)

    def validate(self, attrs):
        project = attrs.get("project")
        compliance = attrs.get("compliance")
        handover = attrs.get("handover")

        # If project not provided but compliance or handover is, derive project from them
        if not project and compliance:
            attrs["project"] = compliance.project
        if not project and handover:
            attrs["project"] = handover.project

        if not attrs.get("project"):
            raise serializers.ValidationError(
                {"project": "This field is required unless a compliance or handover item is provided."}
            )

        return attrs
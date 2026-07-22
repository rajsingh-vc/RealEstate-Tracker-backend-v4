from rest_framework import serializers

from projects.models import Project

from .models import ComplianceItem


class ComplianceItemSerializer(serializers.ModelSerializer):
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all())
    # Read-only convenience field; "project.name" as a source is fine here
    # since this field is never used for input (no camelCase-parsing risk).
    project_name = serializers.CharField(source="project.name", read_only=True)

    class Meta:
        model = ComplianceItem
        fields = ["id", "name", "project", "project_name", "status", "progress", "due_date"]

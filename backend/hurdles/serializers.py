from rest_framework import serializers

from projects.models import Project
from tasks.models import Task

from .models import Hurdle


class HurdleSerializer(serializers.ModelSerializer):
    # See tasks/serializers.py's TaskSerializer docstring: every explicit
    # field below is named in snake_case so djangorestframework-camel-case's
    # parser (which converts incoming "affectedTaskId" -> "affected_task_id"
    # before this serializer ever runs) can actually match it on writes.
    affected_task_id = serializers.PrimaryKeyRelatedField(
        source="affected_task", queryset=Task.objects.all(), required=False, allow_null=True
    )
    project_id = serializers.PrimaryKeyRelatedField(source="project", queryset=Project.objects.all())

    class Meta:
        model = Hurdle
        fields = [
            "id", "title", "description", "type", "affected_task_id", "affected_tower",
            "responsible_department", "impact_days", "severity", "status", "resolution_notes",
            "project_id", "reported_date", "resolved_date",
        ]
        read_only_fields = ["reported_date"]

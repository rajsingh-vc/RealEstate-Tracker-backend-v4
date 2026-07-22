from rest_framework import serializers

from projects.models import Project

from .models import HandoverUnit


class HandoverUnitSerializer(serializers.ModelSerializer):
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all())
    project_name = serializers.CharField(source="project.name", read_only=True)

    class Meta:
        model = HandoverUnit
        fields = ["id", "unit", "tower", "project", "project_name", "status", "progress", "buyer"]

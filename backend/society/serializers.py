from rest_framework import serializers

from projects.models import Project

from .models import Society, SocietyStep


class SocietyStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocietyStep
        fields = ["id", "name", "completed"]


class SocietySerializer(serializers.ModelSerializer):
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all())
    project_name = serializers.CharField(source="project.name", read_only=True)
    steps = SocietyStepSerializer(many=True, required=False)

    class Meta:
        model = Society
        fields = ["id", "name", "project", "project_name", "status", "progress", "steps"]
        read_only_fields = ["progress"]

    def create(self, validated_data):
        steps = validated_data.pop("steps", [])
        society = Society.objects.create(**validated_data)
        SocietyStep.objects.bulk_create(
            [SocietyStep(society=society, order=i, **s) for i, s in enumerate(steps)]
        )
        society.recalculate_progress()
        return society

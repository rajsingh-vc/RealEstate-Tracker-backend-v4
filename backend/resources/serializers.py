from rest_framework import serializers

from tasks.models import Task

from .models import Resource, ResourceMachine, ResourceMaterial


class ResourceMachineSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResourceMachine
        fields = ["id", "name", "qty"]


class ResourceMaterialSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResourceMaterial
        fields = ["id", "name", "qty", "unit"]


class ResourceSerializer(serializers.ModelSerializer):
    """Mirrors src/pages/Resources.tsx's `ResourceRecord` (Resource & { id })."""

    task_id = serializers.PrimaryKeyRelatedField(source="task", queryset=Task.objects.all())
    machines = ResourceMachineSerializer(many=True, required=False)
    materials = ResourceMaterialSerializer(many=True, required=False)

    class Meta:
        model = Resource
        fields = ["id", "task_id", "labour", "machines", "materials", "vendor"]

    def create(self, validated_data):
        machines = validated_data.pop("machines", [])
        materials = validated_data.pop("materials", [])
        resource = Resource.objects.create(**validated_data)
        ResourceMachine.objects.bulk_create([ResourceMachine(resource=resource, **m) for m in machines])
        ResourceMaterial.objects.bulk_create([ResourceMaterial(resource=resource, **m) for m in materials])
        return resource

    def update(self, instance, validated_data):
        machines = validated_data.pop("machines", None)
        materials = validated_data.pop("materials", None)
        instance = super().update(instance, validated_data)
        if machines is not None:
            instance.machines.all().delete()
            ResourceMachine.objects.bulk_create([ResourceMachine(resource=instance, **m) for m in machines])
        if materials is not None:
            instance.materials.all().delete()
            ResourceMaterial.objects.bulk_create([ResourceMaterial(resource=instance, **m) for m in materials])
        return instance

from django.contrib.auth import get_user_model
from rest_framework import serializers

from categorymanagement.models import Category, SubCategory
from projects.models import Floor, Project, Tower, Unit
from tasks.models import Task

from .models import Checklist, ChecklistTemplate, ChecklistTemplateItem, SubTask

User = get_user_model()


class ChecklistTemplateSerializer(serializers.ModelSerializer):
    """`items` is a flat list of strings on the frontend (ChecklistTemplate.items: string[]).

    `category` stays a free-text tag (e.g. "Foundation") for backwards
    compatibility. `category_id` / `sub_category_id` are the *linked*
    Category (Tower) / Sub Category (Floor) records from the
    categorymanagement app, driven by the dropdowns on the Checklists
    page — see CategoryManagement.tsx / Checklists.tsx on the frontend.
    """

    items = serializers.ListField(
        child=serializers.CharField(), source="_items_passthrough", required=False, write_only=True
    )

    project_id = serializers.PrimaryKeyRelatedField(
        source="project", queryset=Project.objects.all(), required=False, allow_null=True
    )
    project_name = serializers.CharField(source="project.name", read_only=True, default=None)

    category_id = serializers.PrimaryKeyRelatedField(
        source="linked_category", queryset=Category.objects.all(), required=False, allow_null=True
    )
    category_name = serializers.CharField(source="linked_category.name", read_only=True, default=None)

    sub_category_id = serializers.PrimaryKeyRelatedField(
        source="linked_sub_category", queryset=SubCategory.objects.all(), required=False, allow_null=True
    )
    sub_category_name = serializers.CharField(source="linked_sub_category.name", read_only=True, default=None)

    class Meta:
        model = ChecklistTemplate
        fields = [
            "id", "name", "category", "items",
            "project_id", "project_name",
            "category_id", "category_name",
            "sub_category_id", "sub_category_name",
        ]

    def validate(self, attrs):
        # A sub category must belong to the linked category, and the
        # category must belong to the linked project, same rule the
        # Tower/Floor cascade already enforces on the frontend dropdowns.
        category = attrs.get("linked_category", getattr(self.instance, "linked_category", None))
        sub_category = attrs.get("linked_sub_category", getattr(self.instance, "linked_sub_category", None))
        project = attrs.get("project", getattr(self.instance, "project", None))

        if category and project and category.project_id != project.id:
            raise serializers.ValidationError(
                {"category_id": "Selected category does not belong to the selected project."}
            )
        if sub_category and category and sub_category.tower_id != category.id:
            raise serializers.ValidationError(
                {"sub_category_id": "Selected sub category does not belong to the selected category."}
            )
        return attrs

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["items"] = list(instance.items.order_by("order").values_list("text", flat=True))
        return data

    def create(self, validated_data):
        items = validated_data.pop("_items_passthrough", [])
        template = ChecklistTemplate.objects.create(
            name=validated_data["name"],
            category=validated_data.get("category", "General"),
            project=validated_data.get("project"),
            linked_category=validated_data.get("linked_category"),
            linked_sub_category=validated_data.get("linked_sub_category"),
        )
        ChecklistTemplateItem.objects.bulk_create(
            [ChecklistTemplateItem(template=template, text=text, order=i) for i, text in enumerate(items)]
        )
        return template

    def update(self, instance, validated_data):
        items = validated_data.pop("_items_passthrough", None)
        instance.name = validated_data.get("name", instance.name)
        instance.category = validated_data.get("category", instance.category)
        if "project" in validated_data:
            instance.project = validated_data["project"]
        if "linked_category" in validated_data:
            instance.linked_category = validated_data["linked_category"]
        if "linked_sub_category" in validated_data:
            instance.linked_sub_category = validated_data["linked_sub_category"]
        instance.save()
        if items is not None:
            instance.items.all().delete()
            ChecklistTemplateItem.objects.bulk_create(
                [ChecklistTemplateItem(template=instance, text=text, order=i) for i, text in enumerate(items)]
            )
        return instance


class ChecklistSerializer(serializers.ModelSerializer):
    task_id = serializers.PrimaryKeyRelatedField(source="task", queryset=Task.objects.all())
    unit_id = serializers.PrimaryKeyRelatedField(source="unit", queryset=Unit.objects.all(), required=False, allow_null=True)
    floor_id = serializers.PrimaryKeyRelatedField(source="floor", queryset=Floor.objects.all(), required=False, allow_null=True)
    tower_id = serializers.PrimaryKeyRelatedField(source="tower", queryset=Tower.objects.all(), required=False, allow_null=True)
    project_id = serializers.PrimaryKeyRelatedField(source="project", read_only=True)

    class Meta:
        model = Checklist
        fields = ["id", "name", "task_id", "unit_id", "floor_id", "tower_id", "project_id", "status", "progress"]

    def create(self, validated_data):
        task = validated_data["task"]
        validated_data["unit"] = validated_data.get("unit") or task.unit
        validated_data["floor"] = validated_data.get("floor") or task.floor
        validated_data["tower"] = validated_data.get("tower") or task.tower
        validated_data["project"] = task.project
        return super().create(validated_data)


class SubTaskSerializer(serializers.ModelSerializer):
    checklist_id = serializers.PrimaryKeyRelatedField(source="checklist", queryset=Checklist.objects.all())
    task_id = serializers.PrimaryKeyRelatedField(source="task", read_only=True)
    unit_id = serializers.PrimaryKeyRelatedField(source="unit", read_only=True)
    floor_id = serializers.PrimaryKeyRelatedField(source="floor", read_only=True)
    tower_id = serializers.PrimaryKeyRelatedField(source="tower", read_only=True)
    project_id = serializers.PrimaryKeyRelatedField(source="project", read_only=True)

    class Meta:
        model = SubTask
        fields = ["id", "name", "checklist_id", "task_id", "unit_id", "floor_id", "tower_id", "project_id", "status", "progress"]

    def create(self, validated_data):
        checklist = validated_data["checklist"]
        validated_data["task"] = checklist.task
        validated_data["unit"] = checklist.unit
        validated_data["floor"] = checklist.floor
        validated_data["tower"] = checklist.tower
        validated_data["project"] = checklist.project
        return super().create(validated_data)
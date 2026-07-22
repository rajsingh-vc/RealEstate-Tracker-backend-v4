from rest_framework import serializers

from projects.models import Project, Tower

from .models import Category, SubCategory


class SubCategorySerializer(serializers.ModelSerializer):
    """Mirrors `SubCategoryFormValues` in CategoryManagement.tsx
    (number, name, status, progress).

    The underlying Floor table has no `status` / `progress` columns, so
    those two are read-only here and report the same fallback values the
    frontend already falls back to (`subCategory.status || "Active"`,
    `subCategory.progress || 0`) instead of silently discarding whatever a
    client sends for them.
    """

    category_id = serializers.PrimaryKeyRelatedField(source="tower", queryset=Tower.objects.all())
    project_id = serializers.PrimaryKeyRelatedField(source="project", read_only=True)
    status = serializers.SerializerMethodField()
    progress = serializers.SerializerMethodField()

    class Meta:
        model = SubCategory
        fields = ["id", "name", "number", "category_id", "project_id", "status", "progress"]

    def get_status(self, obj):
        return "Active"

    def get_progress(self, obj):
        return 0

    def create(self, validated_data):
        tower = validated_data["tower"]
        validated_data["project"] = tower.project
        return super().create(validated_data)


class CategorySerializer(serializers.ModelSerializer):
    """Mirrors `CategoryFormValues` in CategoryManagement.tsx
    (name, status, totalFloors, progress)."""

    project_id = serializers.PrimaryKeyRelatedField(source="project", queryset=Project.objects.all())
    total_sub_categories = serializers.IntegerField(source="total_floors", required=False)
    sub_categories = SubCategorySerializer(source="floors", many=True, read_only=True)

    class Meta:
        model = Category
        fields = [
            "id", "name", "project_id", "status", "progress",
            "total_sub_categories", "sub_categories",
        ]


class CategoryListSerializer(CategorySerializer):
    """Lightweight variant without the nested sub-categories, for list views."""

    class Meta(CategorySerializer.Meta):
        fields = [f for f in CategorySerializer.Meta.fields if f != "sub_categories"]

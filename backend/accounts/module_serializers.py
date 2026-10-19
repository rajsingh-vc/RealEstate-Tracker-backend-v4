from rest_framework import serializers
from .models import AppModule, RoleModulePermission, UserModulePermission, ModuleAuditLog, Role, User


class AppModuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppModule
        fields = [
            "id",
            "key",
            "name",
            "description",
            "category",
            "route",
            "icon",
            "order",
            "is_active",
            "default_enabled",
            "default_visible",
            "admin_only",
            "created_at",
            "updated_at",
        ]


class RoleModulePermissionSerializer(serializers.ModelSerializer):
    module_key = serializers.CharField(source="module.key", read_only=True)
    module_name = serializers.CharField(source="module.name", read_only=True)
    category = serializers.CharField(source="module.category", read_only=True)

    class Meta:
        model = RoleModulePermission
        fields = [
            "id",
            "role",
            "module",
            "module_key",
            "module_name",
            "category",
            "organization",
            "is_enabled",
            "is_visible",
            "updated_at",
        ]


class UserModulePermissionSerializer(serializers.ModelSerializer):
    module_key = serializers.CharField(source="module.key", read_only=True)
    module_name = serializers.CharField(source="module.name", read_only=True)
    category = serializers.CharField(source="module.category", read_only=True)
    created_by_name = serializers.CharField(source="created_by.name", read_only=True)

    class Meta:
        model = UserModulePermission
        fields = [
            "id",
            "user",
            "module",
            "module_key",
            "module_name",
            "category",
            "project",
            "is_enabled",
            "is_visible",
            "created_by",
            "created_by_name",
            "updated_at",
        ]


class ModuleAuditLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source="actor.name", read_only=True)
    actor_email = serializers.CharField(source="actor.email", read_only=True)
    target_user_name = serializers.CharField(source="target_user.name", read_only=True)
    target_role_name = serializers.CharField(source="target_role.name", read_only=True)

    class Meta:
        model = ModuleAuditLog
        fields = [
            "id",
            "actor",
            "actor_name",
            "actor_email",
            "action",
            "module_key",
            "target_user",
            "target_user_name",
            "target_role",
            "target_role_name",
            "target_project",
            "organization",
            "previous_value",
            "new_value",
            "details",
            "created_at",
        ]

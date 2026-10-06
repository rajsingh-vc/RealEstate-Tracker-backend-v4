from rest_framework import serializers

# Same aliasing as projects/models.py — Project's FKs target the accounts
# app's models (the ones actually reachable via /api/organizations/,
# /api/companies/, /api/entities/), not adminpanel's identically-named,
# shadowed-and-unreachable equivalents.
from accounts.models import Company as Organization
from accounts.models import OrganizationCompany as Company
from accounts.models import Entity

from .models import Floor, Project, Tower, Unit


class StatusChoiceSerializer(serializers.Serializer):
    value = serializers.CharField()
    label = serializers.CharField()


class UnitSerializer(serializers.ModelSerializer):
    floor_id = serializers.PrimaryKeyRelatedField(source="floor", queryset=Floor.objects.all())
    tower_id = serializers.PrimaryKeyRelatedField(source="tower", read_only=True)
    project_id = serializers.PrimaryKeyRelatedField(source="project", read_only=True)
    unit_number = serializers.CharField(source="name")
    area_sq_ft = serializers.IntegerField(source="area", required=False)

    class Meta:
        model = Unit
        fields = [
            "id", "unit_number", "floor_id", "tower_id", "project_id",
            "type", "area_sq_ft", "status", "progress",
        ]

    def create(self, validated_data):
        floor = validated_data["floor"]
        validated_data["tower"] = floor.tower
        validated_data["project"] = floor.project
        return super().create(validated_data)


class FloorSerializer(serializers.ModelSerializer):
    tower_id = serializers.PrimaryKeyRelatedField(source="tower", queryset=Tower.objects.all())
    project_id = serializers.PrimaryKeyRelatedField(source="project", read_only=True)
    units = UnitSerializer(many=True, read_only=True)

    class Meta:
        model = Floor
        fields = ["id", "name", "number", "tower_id", "project_id", "units"]

    def create(self, validated_data):
        tower = validated_data["tower"]
        validated_data["project"] = tower.project
        return super().create(validated_data)


class TowerSerializer(serializers.ModelSerializer):
    project_id = serializers.PrimaryKeyRelatedField(source="project", queryset=Project.objects.all())
    floors = FloorSerializer(many=True, read_only=True)

    class Meta:
        model = Tower
        fields = ["id", "name", "project_id", "total_floors", "floors", "progress", "status"]


class ProjectSerializer(serializers.ModelSerializer):
    towers = TowerSerializer(many=True, read_only=True)

    organization_id = serializers.PrimaryKeyRelatedField(
        source="organization", queryset=Organization.objects.all(),
        required=False, allow_null=True
    )
    company_id = serializers.PrimaryKeyRelatedField(
        source="company", queryset=Company.objects.all(),
        required=False, allow_null=True
    )
    entity_id = serializers.PrimaryKeyRelatedField(
        source="entity", queryset=Entity.objects.all(), required=False, allow_null=True
    )

    organization_name = serializers.CharField(source="organization.name", read_only=True)
    organization_logo = serializers.SerializerMethodField(read_only=True)
    company_name = serializers.CharField(source="company.company_name", read_only=True)
    entity_name = serializers.CharField(source="entity.entity_name", read_only=True, allow_null=True)

    def get_organization_logo(self, obj):
        if obj.organization and obj.organization.logo:
            request = self.context.get("request")
            try:
                if request:
                    return request.build_absolute_uri(obj.organization.logo.url)
                return obj.organization.logo.url
            except Exception:
                return None
        return None

    budget = serializers.DecimalField(max_digits=16, decimal_places=2, coerce_to_string=False, required=False)
    spent = serializers.DecimalField(max_digits=16, decimal_places=2, coerce_to_string=False, required=False)

    class Meta:
        model = Project
        fields = [
            "id", "name", "location", "status", "start_date", "end_date", "progress",
            "towers", "total_units", "rera_number", "developer", "budget", "spent",
            "organization_id", "company_id", "entity_id",
            "organization_name", "organization_logo", "company_name", "entity_name",
            "hierarchy_mode",  # ✅ NEW — camelCase renderer outputs this as hierarchyMode
            "created_at", "updated_at",  # ✅ NEW — renders as createdAt / updatedAt
        ]

    def validate(self, attrs):
        organization = attrs.get("organization") or getattr(self.instance, "organization", None)
        company = attrs.get("company") or getattr(self.instance, "company", None)
        entity = attrs.get("entity") or getattr(self.instance, "entity", None)

        if company and organization and company.organization_id != organization.id:
            raise serializers.ValidationError(
                {"company_id": "Selected company does not belong to the selected organization."}
            )
        if entity and organization and entity.organization_id != organization.id:
            raise serializers.ValidationError(
                {"entity_id": "Selected entity does not belong to the selected organization."}
            )
        return attrs

    def create(self, validated_data):
        # Quick-create flows (e.g. the Documents "create new project" shortcut)
        # don't collect org/company explicitly — fall back to the requesting
        # user's own org, since user.company_id IS the Organization FK
        # (see adminpanel/scoping.py user_organization_ids()).
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not validated_data.get("organization") and user is not None:
            org_id = getattr(user, "company_id", None)
            if org_id:
                validated_data["organization"] = Organization.objects.filter(id=org_id).first()
        return super().create(validated_data)


class ProjectListSerializer(ProjectSerializer):
    """Lightweight variant without the nested towers/floors/units tree, used for list views."""

    class Meta(ProjectSerializer.Meta):
        fields = [f for f in ProjectSerializer.Meta.fields if f != "towers"]
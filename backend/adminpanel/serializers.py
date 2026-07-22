from rest_framework import serializers

from .models import Company, Entity, EscalationRule, Organization


class EscalationRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = EscalationRule
        fields = ["id", "level", "role", "days", "description"]


class OrganizationSerializer(serializers.ModelSerializer):
    # Counts drive the "N companies · N entities" subtitle shown in the UI
    # without the client having to fetch/aggregate the child lists itself.
    company_count = serializers.SerializerMethodField()
    entity_count = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = [
            "id",
            "name",
            "logo",
            "address",
            "company_count",
            "entity_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_company_count(self, obj) -> int:
        return obj.companies.count()

    def get_entity_count(self, obj) -> int:
        return obj.entities.count()


class CompanySerializer(serializers.ModelSerializer):
    
     class Meta:
        model = Company
        fields = [
            "id",
            "organization",
            "company_name",
            "state",
            "pin_code",
            "zone",
            "region",
            "country",
            "sub_domain",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class EntitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Entity
        fields = [
            "id",
            "organization",
            "entity_name",
            "state",
            "region",
            "zone",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
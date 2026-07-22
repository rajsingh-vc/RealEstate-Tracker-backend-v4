from django.contrib import admin

from .models import Company, Entity, EscalationRule, Organization


@admin.register(EscalationRule)
class EscalationRuleAdmin(admin.ModelAdmin):
    list_display = ("level", "role", "days", "description")


class CompanyInline(admin.TabularInline):
    model = Company
    extra = 0


class EntityInline(admin.TabularInline):
    model = Entity
    extra = 0


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "address", "created_by", "created_at")
    search_fields = ("name", "address")
    inlines = [CompanyInline, EntityInline]


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("company_name", "organization", "sub_domain", "country", "state")
    list_filter = ("organization",)
    search_fields = ("company_name", "sub_domain")


@admin.register(Entity)
class EntityAdmin(admin.ModelAdmin):
    list_display = ("entity_name", "organization", "region", "zone")
    list_filter = ("organization",)
    search_fields = ("entity_name",)
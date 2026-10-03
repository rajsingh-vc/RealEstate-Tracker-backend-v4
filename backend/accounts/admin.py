from django.contrib import admin

from .models import (
    Company, Department, Entity, EscalationRule, Invitation, OrganizationCompany,
    PasswordResetOTP, Role, User,
)


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'subdomain', 'is_active', 'created_by', 'created_at')
    search_fields = ('name', 'subdomain')
    list_filter = ('is_active',)


@admin.register(OrganizationCompany)
class OrganizationCompanyAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'organization', 'country', 'region')
    list_filter = ('organization',)
    search_fields = ('company_name',)


@admin.register(Entity)
class EntityAdmin(admin.ModelAdmin):
    list_display = ('entity_name', 'organization', 'region', 'zone')
    list_filter = ('organization',)
    search_fields = ('entity_name',)


@admin.register(EscalationRule)
class EscalationRuleAdmin(admin.ModelAdmin):
    list_display = ('level', 'role', 'days', 'company')
    list_filter = ('company',)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'company')
    list_filter = ('company',)


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'company')
    list_filter = ('company',)


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'company', 'role', 'department', 'is_active')
    list_filter = ('company', 'role', 'department', 'is_active')


@admin.register(PasswordResetOTP)
class PasswordResetOTPAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at', 'expires_at', 'is_verified', 'is_used')
    list_filter = ('is_verified', 'is_used')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('otp_code', 'created_at')


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ('email', 'company', 'role', 'department', 'status', 'invited_by', 'created_at', 'expires_at')
    list_filter = ('status', 'company')
    search_fields = ('email',)
from django.contrib import admin

from .models import ComplianceItem


@admin.register(ComplianceItem)
class ComplianceItemAdmin(admin.ModelAdmin):
    list_display = ("name", "project", "status", "progress", "due_date")
    list_filter = ("status", "project")

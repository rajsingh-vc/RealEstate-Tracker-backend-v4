from django.contrib import admin

from .models import Hurdle


@admin.register(Hurdle)
class HurdleAdmin(admin.ModelAdmin):
    list_display = ("title", "project", "severity", "status", "impact_days", "reported_date")
    list_filter = ("severity", "status", "type", "project")
    search_fields = ("title", "description")

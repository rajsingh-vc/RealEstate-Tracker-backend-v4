from django.contrib import admin

from .models import HandoverUnit


@admin.register(HandoverUnit)
class HandoverUnitAdmin(admin.ModelAdmin):
    list_display = ("unit", "tower", "project", "status", "progress", "buyer")
    list_filter = ("status", "project")

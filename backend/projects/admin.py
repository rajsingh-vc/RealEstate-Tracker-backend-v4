from django.contrib import admin

from .models import Floor, Project, Tower, Unit


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "location", "status", "hierarchy_mode", "progress", "total_units", "budget", "spent")
    list_filter = ("status", "hierarchy_mode")  # ✅ NEW filter
    search_fields = ("name", "location", "rera_number")


@admin.register(Tower)
class TowerAdmin(admin.ModelAdmin):
    list_display = ("name", "project", "total_floors", "progress", "status")
    list_filter = ("project", "status")


@admin.register(Floor)
class FloorAdmin(admin.ModelAdmin):
    list_display = ("name", "tower", "number")
    list_filter = ("tower",)


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ("name", "floor", "type", "area")
    list_filter = ("type", "floor__tower")
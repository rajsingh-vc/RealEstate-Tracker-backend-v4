from django.contrib import admin

from .models import Society, SocietyStep


class SocietyStepInline(admin.TabularInline):
    model = SocietyStep
    extra = 0


@admin.register(Society)
class SocietyAdmin(admin.ModelAdmin):
    list_display = ("name", "project", "status", "progress")
    list_filter = ("status", "project")
    inlines = [SocietyStepInline]

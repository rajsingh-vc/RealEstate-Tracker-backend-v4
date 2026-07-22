from django.contrib import admin

from .models import ChecklistTemplate, ChecklistTemplateItem


class ChecklistTemplateItemInline(admin.TabularInline):
    model = ChecklistTemplateItem
    extra = 0


@admin.register(ChecklistTemplate)
class ChecklistTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "project", "linked_category", "linked_sub_category")
    list_filter = ("category", "project")
    inlines = [ChecklistTemplateItemInline]

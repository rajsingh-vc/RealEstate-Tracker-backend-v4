from django.contrib import admin

from .models import Task, TaskChecklistItem, TaskComment


class TaskChecklistItemInline(admin.TabularInline):
    model = TaskChecklistItem
    extra = 0


class TaskCommentInline(admin.TabularInline):
    model = TaskComment
    extra = 0
    readonly_fields = ("date",)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("title", "project", "department", "status", "priority", "progress", "delay_days", "critical_path")
    list_filter = ("status", "department", "priority", "critical_path", "project")
    search_fields = ("title", "description")
    inlines = [TaskChecklistItemInline, TaskCommentInline]
    filter_horizontal = ("assigned_users", "dependencies")

from django.contrib import admin

from .models import Category, SubCategory


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "project", "status", "total_floors", "progress")
    list_filter = ("status", "project")
    search_fields = ("name",)


@admin.register(SubCategory)
class SubCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "number", "tower", "project")
    list_filter = ("tower", "project")
    search_fields = ("name",)

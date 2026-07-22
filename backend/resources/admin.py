from django.contrib import admin

from .models import Resource, ResourceMachine, ResourceMaterial


class ResourceMachineInline(admin.TabularInline):
    model = ResourceMachine
    extra = 0


class ResourceMaterialInline(admin.TabularInline):
    model = ResourceMaterial
    extra = 0


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ("task", "labour", "vendor")
    inlines = [ResourceMachineInline, ResourceMaterialInline]

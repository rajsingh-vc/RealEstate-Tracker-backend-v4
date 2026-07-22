from rest_framework import viewsets, serializers
from rest_framework.viewsets import ViewSet
from rest_framework.response import Response

# TODO: point this at wherever your shared scoping helpers actually live —
# per your setup, Tasks already uses this same pattern via
# project__organization_id__in.
from adminpanel.scoping import is_unrestricted, user_organization_ids

from .models import Project, Tower, Floor, Unit
from .serializers import (
    ProjectSerializer, ProjectListSerializer, TowerSerializer, FloorSerializer, UnitSerializer,
)


class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.select_related("organization", "company", "entity").prefetch_related("towers")

    def get_serializer_class(self):
        return ProjectListSerializer if self.action == "list" else ProjectSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not is_unrestricted(user):
            qs = qs.filter(organization_id__in=user_organization_ids(user))
        return qs


class TowerViewSet(viewsets.ModelViewSet):
    queryset = Tower.objects.select_related("project")
    serializer_class = TowerSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not is_unrestricted(user):
            qs = qs.filter(project__organization_id__in=user_organization_ids(user))
        return qs

    def perform_create(self, serializer):
        # ✅ NEW — block towers on direct_task projects, matching the same
        # rule the frontend already enforces by hiding the button.
        project = serializer.validated_data["project"]
        if project.hierarchy_mode != Project.HIERARCHY_FULL:
            raise serializers.ValidationError(
                {"project_id": "This project is in Direct-to-Task mode — towers can't be added."}
            )
        serializer.save()


class FloorViewSet(viewsets.ModelViewSet):
    queryset = Floor.objects.select_related("tower", "project")
    serializer_class = FloorSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not is_unrestricted(user):
            qs = qs.filter(project__organization_id__in=user_organization_ids(user))
        return qs

    def perform_create(self, serializer):
        tower = serializer.validated_data["tower"]
        if tower.project.hierarchy_mode != Project.HIERARCHY_FULL:
            raise serializers.ValidationError(
                {"tower_id": "This project is in Direct-to-Task mode — floors can't be added."}
            )
        serializer.save()


class UnitViewSet(viewsets.ModelViewSet):
    queryset = Unit.objects.select_related("floor", "tower", "project")
    serializer_class = UnitSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not is_unrestricted(user):
            qs = qs.filter(project__organization_id__in=user_organization_ids(user))
        return qs

    def perform_create(self, serializer):
        floor = serializer.validated_data["floor"]
        if floor.project.hierarchy_mode != Project.HIERARCHY_FULL:
            raise serializers.ValidationError(
                {"floor_id": "This project is in Direct-to-Task mode — units can't be added."}
            )
        serializer.save()


# ✅ Backs `statusesApi.list(entity)` on the frontend — status values are
# derived from whatever's actually in the DB per entity, falling back to a
# sane default set for a brand-new install with no data yet. Nothing here
# is a hardcoded dropdown list living only in the frontend.
ENTITY_MODEL_MAP = {"project": Project, "tower": Tower, "floor": Floor, "unit": Unit}

DEFAULT_STATUSES = {
    "project": ["Planning", "Active", "On Hold", "Completed"],
    "tower": ["Planning", "Active", "Completed"],
    "floor": ["Active", "Completed"],
    "unit": ["Available", "Sold", "Blocked"],
    "task": ["not_started", "ready", "in_progress", "blocked", "review", "completed", "delayed"],
    "checklist": ["Pending", "In Progress", "Completed"],
}


def _humanize(value: str) -> str:
    return value.replace("_", " ").replace("-", " ").strip().title()


class StatusViewSet(ViewSet):
    def list(self, request):
        entity = request.query_params.get("entity", "project")
        values: set[str] = set()

        model = ENTITY_MODEL_MAP.get(entity)
        if model is not None:
            values.update(
                v for v in model.objects.exclude(status="").values_list("status", flat=True).distinct() if v
            )
        elif entity == "task":
            from tasks.models import Task
            values.update(
                v for v in Task.objects.exclude(status="").values_list("status", flat=True).distinct() if v
            )

        if not values:
            values.update(DEFAULT_STATUSES.get(entity, []))

        return Response([{"value": v, "label": _humanize(v)} for v in sorted(values)])
from django.db.models import Q
from rest_framework import permissions, viewsets

from adminpanel.scoping import is_unrestricted, user_organization_ids

from .models import Checklist, ChecklistTemplate, SubTask
from .serializers import ChecklistSerializer, ChecklistTemplateSerializer, SubTaskSerializer


class ChecklistTemplateViewSet(viewsets.ModelViewSet):
    queryset = ChecklistTemplate.objects.select_related(
        "project", "linked_category", "linked_sub_category"
    ).prefetch_related("items").all()
    serializer_class = ChecklistTemplateSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["category", "project", "linked_category", "linked_sub_category"]
    search_fields = ["name", "category"]

    def get_queryset(self):
        # Fixed: ChecklistTemplate had no `company`/`project` field before,
        # so the previous `user.company` filter raised a FieldError for any
        # non-superuser. Now that templates can optionally link to a
        # project (via Category Management), scope the same way every
        # other project-linked app does — by organization — while still
        # showing unlinked/global templates (project is null) to everyone.
        user = self.request.user
        if is_unrestricted(user):
            return self.queryset
        org_ids = user_organization_ids(user)
        if not org_ids:
            return self.queryset.filter(project__isnull=True)
        return self.queryset.filter(
            Q(project__isnull=True) | Q(project__organization_id__in=org_ids)
        )


class ChecklistViewSet(viewsets.ModelViewSet):
    queryset = Checklist.objects.select_related("task", "unit", "floor", "tower", "project").all()
    serializer_class = ChecklistSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["task", "unit", "floor", "tower", "project"]

    def get_queryset(self):
        # Same organization-scoping as ChecklistTemplateViewSet above —
        # `project__company=user.company` compared adminpanel.Company
        # (Project.company) against accounts.Company (user.company), two
        # unrelated models that share a name, which the ORM rejects.
        user = self.request.user
        if is_unrestricted(user):
            return self.queryset
        org_ids = user_organization_ids(user)
        if not org_ids:
            return self.queryset.none()
        return self.queryset.filter(project__organization_id__in=org_ids)


class SubTaskViewSet(viewsets.ModelViewSet):
    queryset = SubTask.objects.select_related("checklist", "task", "unit", "floor", "tower", "project").all()
    serializer_class = SubTaskSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["checklist", "task", "unit", "floor", "tower", "project"]

    def get_queryset(self):
        user = self.request.user
        if is_unrestricted(user):
            return self.queryset
        org_ids = user_organization_ids(user)
        if not org_ids:
            return self.queryset.none()
        return self.queryset.filter(project__organization_id__in=org_ids)
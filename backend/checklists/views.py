from django.db.models import Q
from rest_framework import permissions, viewsets

from accounts.module_guard import HasModuleAccess
from accounts.permissions import IsAdminOrSuperAdminOrReadOnly, is_admin_or_superadmin
from adminpanel.scoping import is_unrestricted, user_organization_ids

from .models import Checklist, ChecklistTemplate, SubTask
from .serializers import ChecklistSerializer, ChecklistTemplateSerializer, SubTaskSerializer


class ChecklistTemplateViewSet(viewsets.ModelViewSet):
    module_key = "checklists"
    queryset = ChecklistTemplate.objects.select_related(
        "project", "linked_category", "linked_sub_category"
    ).prefetch_related("items").all()
    serializer_class = ChecklistTemplateSerializer
    permission_classes = [IsAdminOrSuperAdminOrReadOnly, HasModuleAccess]
    filterset_fields = ["category", "project", "linked_category", "linked_sub_category"]
    search_fields = ["name", "category"]

    def get_queryset(self):
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
    module_key = "checklists"
    queryset = Checklist.objects.select_related("task", "unit", "floor", "tower", "project").all()
    serializer_class = ChecklistSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    filterset_fields = ["task", "unit", "floor", "tower", "project"]

    def get_queryset(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return self.queryset.none()
        if is_unrestricted(user):
            qs = self.queryset
        else:
            org_ids = user_organization_ids(user)
            if not org_ids:
                return self.queryset.none()
            qs = self.queryset.filter(project__organization_id__in=org_ids)

        if not is_admin_or_superadmin(user):
            qs = qs.filter(
                Q(task__assigned_to=user) |
                Q(task__assigned_users=user) |
                Q(task__assigned_hod=user) |
                Q(task__parent__assigned_to=user) |
                Q(task__parent__assigned_users=user)
            ).distinct()
        return qs


class SubTaskViewSet(viewsets.ModelViewSet):
    module_key = "checklists"
    queryset = SubTask.objects.select_related("checklist", "task", "unit", "floor", "tower", "project").all()
    serializer_class = SubTaskSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    filterset_fields = ["checklist", "task", "unit", "floor", "tower", "project"]

    def get_queryset(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return self.queryset.none()
        if is_unrestricted(user):
            qs = self.queryset
        else:
            org_ids = user_organization_ids(user)
            if not org_ids:
                return self.queryset.none()
            qs = self.queryset.filter(project__organization_id__in=org_ids)

        if not is_admin_or_superadmin(user):
            qs = qs.filter(
                Q(task__assigned_to=user) |
                Q(task__assigned_users=user) |
                Q(task__assigned_hod=user) |
                Q(task__parent__assigned_to=user) |
                Q(task__parent__assigned_users=user)
            ).distinct()
        return qs
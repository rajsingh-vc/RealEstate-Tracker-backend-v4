from rest_framework import permissions, viewsets

from accounts.module_guard import HasModuleAccess
from adminpanel.scoping import is_unrestricted, user_organization_ids

from .models import Resource
from .serializers import ResourceSerializer


class ResourceViewSet(viewsets.ModelViewSet):
    module_key = "resources"
    queryset = Resource.objects.select_related("task").prefetch_related("machines", "materials").all()
    serializer_class = ResourceSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    filterset_fields = ["task"]

    def get_queryset(self):
        user = self.request.user
        if is_unrestricted(user):
            return self.queryset
        org_ids = user_organization_ids(user)
        if not org_ids:
            return self.queryset.none()
        return self.queryset.filter(task__project__organization_id__in=org_ids)

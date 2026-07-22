from rest_framework import permissions, viewsets

from adminpanel.scoping import is_unrestricted, user_organization_ids

from .models import Resource
from .serializers import ResourceSerializer


class ResourceViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        # Resource has no `company` field at all (despite the stale import
        # in models.py) — the old `filter(company=user.company)` raised a
        # FieldError for every non-superuser. Resource has no project FK of
        # its own either; it hangs off Task, which hangs off Project, so
        # scope through that chain — same organization-scoping rules as
        # everywhere else.
        user = self.request.user
        if is_unrestricted(user):
            return self.queryset
        org_ids = user_organization_ids(user)
        if not org_ids:
            return self.queryset.none()
        return self.queryset.filter(task__project__organization_id__in=org_ids)
    

    

    queryset = Resource.objects.select_related("task").prefetch_related("machines", "materials").all()
    serializer_class = ResourceSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["task"]



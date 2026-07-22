from rest_framework import permissions, viewsets

from adminpanel.scoping import is_unrestricted, user_organization_ids

from .models import HandoverUnit
from .serializers import HandoverUnitSerializer


class HandoverUnitViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        # HandoverUnit has no `company` field at all (despite the stale
        # import in models.py) — the old `filter(company=user.company)`
        # raised a FieldError for every non-superuser. Scoped via project's
        # organization instead, same as Hurdle/Document/Checklist.
        user = self.request.user
        if is_unrestricted(user):
            return self.queryset
        org_ids = user_organization_ids(user)
        if not org_ids:
            return self.queryset.none()
        return self.queryset.filter(project__organization_id__in=org_ids)

    queryset = HandoverUnit.objects.select_related("project").all()
    serializer_class = HandoverUnitSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["status", "project"]
    search_fields = ["unit", "buyer"]



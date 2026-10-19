from rest_framework import permissions, viewsets

from adminpanel.scoping import is_unrestricted, user_organization_ids

from accounts.module_guard import HasModuleAccess
from .models import Hurdle
from .serializers import HurdleSerializer


class HurdleViewSet(viewsets.ModelViewSet):
    module_key = "hurdles"
    queryset = Hurdle.objects.select_related("project", "affected_task").all()
    serializer_class = HurdleSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    filterset_fields = ["severity", "status", "type", "project", "responsible_department"]
    search_fields = ["title", "description", "affected_tower"]
    ordering_fields = ["reported_date", "impact_days"]

    def get_queryset(self):
        user = self.request.user
        if is_unrestricted(user):
            return self.queryset
        org_ids = user_organization_ids(user)
        if not org_ids:
            return self.queryset.none()
        return self.queryset.filter(project__organization_id__in=org_ids)



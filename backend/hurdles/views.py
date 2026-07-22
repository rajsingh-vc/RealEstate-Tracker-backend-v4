from rest_framework import permissions, viewsets

from adminpanel.scoping import is_unrestricted, user_organization_ids

from .models import Hurdle
from .serializers import HurdleSerializer


class HurdleViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        # Same organization-scoping rules as ProjectViewSet/TaskViewSet
        # (see projects/views.py, tasks/views.py), instead of the old
        # `user.company` check. That check compared accounts.User.company
        # (an accounts.Company instance) against Project.company (an
        # adminpanel.Company instance) — two different models that happen
        # to share a name, which Django's ORM rejects with "Must be
        # Company instance". Hurdle has no organization FK of its own, so
        # access is resolved through its project, same as Task.
        user = self.request.user
        if is_unrestricted(user):
            return self.queryset
        org_ids = user_organization_ids(user)
        if not org_ids:
            return self.queryset.none()
        return self.queryset.filter(project__organization_id__in=org_ids)

    queryset = Hurdle.objects.select_related("project", "affected_task").all()
    serializer_class = HurdleSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["severity", "status", "type", "project", "responsible_department"]
    search_fields = ["title", "description", "affected_tower"]
    ordering_fields = ["reported_date", "impact_days"]



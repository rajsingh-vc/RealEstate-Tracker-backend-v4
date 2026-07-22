# documents/views.py
from rest_framework import permissions, viewsets

from adminpanel.scoping import is_unrestricted, user_organization_ids

from .models import Document
from .serializers import DocumentSerializer


class DocumentViewSet(viewsets.ModelViewSet):
    queryset = Document.objects.select_related("project", "compliance", "handover").all()
    serializer_class = DocumentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["category", "project", "type", "compliance", "handover"]  # 👈 added handover
    search_fields = ["name"]
    pagination_class = None

    def get_queryset(self):
        # Same organization-scoping as ProjectViewSet/TaskViewSet —
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
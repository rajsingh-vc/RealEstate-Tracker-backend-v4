from rest_framework import viewsets
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser

from accounts.permissions import IsAdminOrCEO

from .models import Company, Entity, EscalationRule, Organization
from .scoping import scope_by_organization_fk, scope_organizations
from .serializers import (
    CompanySerializer,
    EntitySerializer,
    EscalationRuleSerializer,
    OrganizationSerializer,
)


class EscalationRuleViewSet(viewsets.ModelViewSet):
    queryset = EscalationRule.objects.all()
    serializer_class = EscalationRuleSerializer
    permission_classes = [IsAdminOrCEO]
    # Escalation rules are global by design (no organization FK on the
    # model), so there's nothing to scope by tenant here — access is
    # already gated by IsAdminOrCEO. Left as its own queryset rather than
    # routed through scoping.py since there's no per-org data to filter.


class OrganizationViewSet(viewsets.ModelViewSet):
    """
    /api/organizations/

    Supports multipart uploads so the logo file can be sent alongside the
    other fields on create/update.
    """

    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer
    permission_classes = [IsAdminOrCEO]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        return scope_organizations(self.request.user, Organization.objects.all())

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class CompanyViewSet(viewsets.ModelViewSet):
    """
    /api/companies/?organization=<id>

    Always operates scoped to an organization: the `organization` query
    param filters list results, and the FK is required on create.
    """

    queryset = Company.objects.select_related("organization").all()
    serializer_class = CompanySerializer
    permission_classes = [IsAdminOrCEO]

    def get_queryset(self):
        queryset = scope_by_organization_fk(
            self.request.user, Company.objects.select_related("organization").all()
        )
        organization_id = self.request.query_params.get("organization")
        if organization_id:
            queryset = queryset.filter(organization_id=organization_id)
        return queryset


class EntityViewSet(viewsets.ModelViewSet):
    """
    /api/entities/?organization=<id>

    Mirrors CompanyViewSet: always scoped to an organization.
    """

    queryset = Entity.objects.select_related("organization").all()
    serializer_class = EntitySerializer
    permission_classes = [IsAdminOrCEO]

    def get_queryset(self):
        queryset = scope_by_organization_fk(
            self.request.user, Entity.objects.select_related("organization").all()
        )
        organization_id = self.request.query_params.get("organization")
        if organization_id:
            queryset = queryset.filter(organization_id=organization_id)
        return queryset
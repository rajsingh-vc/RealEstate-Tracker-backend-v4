from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from adminpanel.scoping import is_unrestricted, user_organization_ids

from .models import Society
from .serializers import SocietySerializer, SocietyStepSerializer


class SocietyViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        # Society has no `company` field at all (despite the stale import
        # in models.py) — the old `filter(company=user.company)` raised a
        # FieldError for every non-superuser. Scoped via project's
        # organization instead, same as Hurdle/Document/Checklist.
        user = self.request.user
        if is_unrestricted(user):
            return self.queryset
        org_ids = user_organization_ids(user)
        if not org_ids:
            return self.queryset.none()
        return self.queryset.filter(project__organization_id__in=org_ids)

    queryset = Society.objects.select_related("project").prefetch_related("steps").all()
    serializer_class = SocietySerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["status", "project"]
    search_fields = ["name"]

    @action(detail=True, methods=["post"], url_path=r"steps/(?P<step_id>[^/.]+)/toggle")
    def toggle_step(self, request, pk=None, step_id=None):
        """POST /api/societies/{id}/steps/{step_id}/toggle/ -> flips a step and
        recalculates the society's overall progress (Society.tsx recalculateProgress)."""
        society = self.get_object()
        step = society.steps.filter(pk=step_id).first()
        if not step:
            return Response({"detail": "Step not found."}, status=404)
        step.completed = not step.completed
        step.save(update_fields=["completed"])
        society.recalculate_progress()
        return Response(SocietyStepSerializer(step).data)



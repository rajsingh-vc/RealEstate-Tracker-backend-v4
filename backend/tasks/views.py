from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from accounts.permissions import IsAdminOrCEO
from adminpanel.scoping import is_unrestricted, user_organization_ids

from .models import Task, TaskChecklistItem
from .serializers import (
    TaskChatMessageSerializer,
    TaskChecklistItemSerializer,
    TaskCommentSerializer,
    TaskListSerializer,
    TaskSerializer,
)


class TaskViewSet(viewsets.ModelViewSet):
    queryset = Task.objects.select_related(
        "project__organization", "project__company", "project__entity", "tower", "assigned_to", "depends_on"
    ).all()
    permission_classes = [permissions.IsAuthenticated]  # adjust if you want IsAdminOrCEO instead
    # "project__organization" lets the frontend filter tasks the same way
    # projects can be filtered by organization (?project__organization=<id>).
    filterset_fields = ["project", "project__organization", "tower", "status", "priority", "department"]
    search_fields = ["title", "description"]
    # No pagination — GET /api/tasks/ returns a plain JSON array of every
    # matching task instead of {count, next, previous, results} split
    # across dozens of pages. Fine for hundreds of tasks; if this table
    # grows into the tens of thousands, pagination (or better, server-side
    # filtering from the UI) should come back.
    pagination_class = None

    def get_serializer_class(self):
        return TaskListSerializer if self.action == "list" else TaskSerializer

    def get_queryset(self):
        # Same organization-scoping rules as ProjectViewSet/TowerViewSet/
        # FloorViewSet/UnitViewSet in projects/views.py, instead of the old
        # `user.company` check (which used a different, legacy tenancy
        # model and didn't line up with how Projects are actually scoped).
        # Task has no organization FK of its own, so — exactly like Tower/
        # Floor/Unit — access is resolved through its project.
        user = self.request.user
        if is_unrestricted(user):
            return self.queryset
        org_ids = user_organization_ids(user)
        if not org_ids:
            return self.queryset.none()
        return self.queryset.filter(project__organization_id__in=org_ids)

    def perform_create(self, serializer):
        # Mirrors ProjectViewSet.perform_create: a user shouldn't be able to
        # create a task under a project belonging to an organization they
        # don't have access to, even though the "project" field itself
        # accepts any project id (its queryset isn't request-scoped).
        user = self.request.user
        project = serializer.validated_data.get("project")

        if not is_unrestricted(user):
            allowed_org_ids = user_organization_ids(user)
            if not project or project.organization_id not in allowed_org_ids:
                raise ValidationError(
                    {"project_id": "You don't have access to create a task under this project."}
                )

        serializer.save()

    @action(detail=True, methods=['post'], url_path='comments')
    def add_comment(self, request, pk=None):
        """POST /api/tasks/{id}/comments/ — adds a comment authored by the
        logged-in user. Matches tasksApi.addComment in lib/api.ts."""
        task = self.get_object()
        text = (request.data.get('text') or '').strip()
        if not text:
            raise ValidationError({"text": "This field is required."})

        comment = task.comments.create(author=request.user, text=text)
        return Response(TaskCommentSerializer(comment).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path=r'checklist/(?P<item_id>\d+)/toggle')
    def toggle_checklist_item(self, request, pk=None, item_id=None):
        """POST /api/tasks/{id}/checklist/{itemId}/toggle/ — flips completed
        and recalculates the task's progress from checklist completion."""
        task = self.get_object()
        item = task.checklist_items.get(pk=item_id)
        item.completed = not item.completed
        item.save(update_fields=['completed'])
        task.recalculate_progress_from_checklist()
        return Response(TaskChecklistItemSerializer(item).data)

    @action(detail=True, methods=['get', 'post'], url_path='chat')
    def chat(self, request, pk=None):
        """GET /api/tasks/{id}/chat/  — list messages, oldest first.
        POST /api/tasks/{id}/chat/ — create a message authored by the
        logged-in user. Matches tasksApi.chat.list / .send in lib/api.ts."""
        task = self.get_object()

        if request.method == 'GET':
            messages = task.chat_messages.select_related('author').all()
            return Response(TaskChatMessageSerializer(messages, many=True).data)

        text = (request.data.get('text') or '').strip()
        if not text:
            raise ValidationError({"text": "This field is required."})

        message = task.chat_messages.create(author=request.user, text=text)
        return Response(TaskChatMessageSerializer(message).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['delete'], url_path=r'chat/(?P<message_id>\d+)')
    def chat_delete(self, request, pk=None, message_id=None):
        """DELETE /api/tasks/{id}/chat/{messageId}/ — matches
        tasksApi.chat.remove in lib/api.ts."""
        task = self.get_object()
        deleted, _ = task.chat_messages.filter(pk=message_id).delete()
        if not deleted:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)

    # ------------------------------------------------------------------
    # REMOVED: the `bulk` action (POST /api/tasks/bulk/) that parsed
    # tasks out of a PDF-derived table and auto-created towers/projects
    # for them. It existed solely to back the "Bulk Import Tasks" flow in
    # Documents.tsx, which has been removed — Documents now only uploads
    # and lists files, and Tasks are created one at a time via the normal
    # create endpoint (POST /api/tasks/) from NewTaskDialog.tsx.
    #
    # If you still need a generic multi-task import path elsewhere (not
    # driven by a document upload), it's worth re-adding as its own
    # endpoint rather than restoring this version, since this one was
    # tightly coupled to the PDF column-mapping shape the frontend used
    # to send (project_name/tower_name fallback resolution, etc.).
    # ------------------------------------------------------------------
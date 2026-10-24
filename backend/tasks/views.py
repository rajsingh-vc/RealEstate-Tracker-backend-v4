from django.db.models import Q
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from accounts.permissions import IsAdminOrCEO, is_admin_or_superadmin
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
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["project", "project__organization", "tower", "status", "priority", "department"]
    search_fields = ["title", "description"]
    pagination_class = None

    def get_serializer_class(self):
        return TaskListSerializer if self.action == "list" else TaskSerializer

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

        # Optional assignee filter (used by admins to filter tasks by assignee)
        assigned_to_param = self.request.query_params.get("assigned_to") or self.request.query_params.get("assignedTo")
        if assigned_to_param:
            if assigned_to_param == "unassigned":
                qs = qs.filter(assigned_to__isnull=True, assigned_users__isnull=True)
            else:
                qs = qs.filter(
                    Q(assigned_to_id=assigned_to_param) |
                    Q(assigned_users__id=assigned_to_param) |
                    Q(assigned_hod_id=assigned_to_param)
                ).distinct()

        # Non-admin users ONLY see tasks assigned to them (or tasks where they are primary, assigned user, or HOD)
        if not is_admin_or_superadmin(user):
            qs = qs.filter(
                Q(assigned_to=user) |
                Q(assigned_users=user) |
                Q(assigned_hod=user) |
                Q(parent__assigned_to=user) |
                Q(parent__assigned_users=user)
            ).distinct()

        return qs

    def check_object_permissions(self, request, obj):
        super().check_object_permissions(request, obj)
        user = request.user
        if is_admin_or_superadmin(user):
            return

        if request.method == "DELETE":
            self.permission_denied(request, message="Only administrators can delete tasks.")

        is_assigned = (
            obj.assigned_to_id == user.id
            or obj.assigned_users.filter(id=user.id).exists()
            or obj.assigned_hod_id == user.id
            or (obj.parent and (
                obj.parent.assigned_to_id == user.id
                or obj.parent.assigned_users.filter(id=user.id).exists()
                or obj.parent.assigned_hod_id == user.id
            ))
        )
        if not is_assigned:
            self.permission_denied(request, message="You do not have permission to access or edit this task.")

    def perform_create(self, serializer):
        user = self.request.user
        project = serializer.validated_data.get("project")

        if not is_unrestricted(user):
            allowed_org_ids = user_organization_ids(user)
            if not project or project.organization_id not in allowed_org_ids:
                raise ValidationError(
                    {"project_id": "You don't have access to create a task under this project."}
                )

        if not is_admin_or_superadmin(user):
            parent = serializer.validated_data.get("parent")
            is_parent_assigned = parent and (
                parent.assigned_to_id == user.id
                or parent.assigned_users.filter(id=user.id).exists()
                or parent.assigned_hod_id == user.id
            )
            if not is_parent_assigned:
                raise ValidationError({"detail": "Only administrators can create top-level tasks."})

        serializer.save()

    def perform_destroy(self, instance):
        if not is_admin_or_superadmin(self.request.user):
            raise ValidationError({"detail": "Only administrators can delete tasks."})
        instance.delete()

    @action(detail=True, methods=['get', 'post'], url_path='comments')
    def comments(self, request, pk=None):
        """GET /api/tasks/{id}/comments/  — list comments, oldest first.
        POST /api/tasks/{id}/comments/ — adds a comment authored by the
        logged-in user. Matches tasksApi.getComments / .addComment in
        lib/api.ts.

        NOTE: previously this action only accepted POST, so the frontend's
        GET (used to populate the ["task", id, "comments"] query) hit a 405
        every time and fell back to task.comments from the list endpoint
        (which is always empty) — that's why comments appeared to
        "disappear" after being posted.
        """
        task = self.get_object()

        if request.method == 'GET':
            comments = task.comments.select_related('author').all()
            return Response(TaskCommentSerializer(comments, many=True).data)

        text = (request.data.get('text') or '').strip()
        if not text:
            raise ValidationError({"text": "This field is required."})

        comment = task.comments.create(author=request.user, text=text)
        return Response(TaskCommentSerializer(comment).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get', 'post'], url_path='subtasks')
    def subtasks(self, request, pk=None):
        """GET /api/tasks/{id}/subtasks/  — list subtasks under this parent task.
        POST /api/tasks/{id}/subtasks/ — create a child task under this task."""
        task = self.get_object()

        if request.method == 'GET':
            subtasks = task.subtasks.all()
            return Response(TaskListSerializer(subtasks, many=True).data)

        title = (request.data.get('title') or request.data.get('name') or '').strip()
        if not title:
            raise ValidationError({"title": "Subtask title is required."})

        subtask = Task.objects.create(
            title=title,
            parent=task,
            project=task.project,
            tower=task.tower,
            floor=task.floor,
            unit=task.unit,
            department=request.data.get('department') or task.department,
            priority=request.data.get('priority') or task.priority,
            status=request.data.get('status') or 'not_started',
            progress=int(request.data.get('progress') or 0),
            assigned_to_id=request.data.get('assigned_to') or request.data.get('assignedTo') or None,
            start_date=request.data.get('start_date') or request.data.get('startDate') or None,
            end_date=request.data.get('end_date') or request.data.get('endDate') or None,
        )
        return Response(TaskSerializer(subtask).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get', 'post'], url_path='checklist')
    def checklist(self, request, pk=None):
        """GET /api/tasks/{id}/checklist/ — list checklist items.
        POST /api/tasks/{id}/checklist/ — create a checklist item."""
        task = self.get_object()
        if request.method == 'GET':
            items = task.checklist_items.all()
            return Response(TaskChecklistItemSerializer(items, many=True).data)

        title = (request.data.get('title') or '').strip()
        if not title:
            raise ValidationError({"title": "This field is required."})

        item = task.checklist_items.create(title=title, order=task.checklist_items.count())
        return Response(TaskChecklistItemSerializer(item).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['delete'], url_path=r'checklist/(?P<item_id>\d+)')
    def delete_checklist_item(self, request, pk=None, item_id=None):
        """DELETE /api/tasks/{id}/checklist/{itemId}/ — deletes a checklist item."""
        task = self.get_object()
        deleted, _ = task.checklist_items.filter(pk=item_id).delete()
        if not deleted:
            return Response(status=status.HTTP_404_NOT_FOUND)
        task.recalculate_progress_from_checklist()
        return Response(status=status.HTTP_204_NO_CONTENT)

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
# documents/views.py
import os
from rest_framework import permissions, viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django.http import FileResponse, Http404

from adminpanel.scoping import is_unrestricted, user_organization_ids
from .models import (
    Document,
    ScheduleImport,
    ScheduleVersion,
    ImportChangeLog,
    DigitalTwinTaskMapping,
)
from .serializers import (
    DocumentSerializer,
    ScheduleImportSerializer,
    ScheduleVersionSerializer,
    ImportChangeLogSerializer,
    DigitalTwinTaskMappingSerializer,
)
from .services.file_validator import validate_file_content
from .services.schedule_parser import ScheduleParserService


class DocumentViewSet(viewsets.ModelViewSet):
    queryset = Document.objects.select_related("project", "compliance", "handover", "uploaded_by").all()
    serializer_class = DocumentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["category", "project", "type", "compliance", "handover", "processing_status"]
    search_fields = ["name", "original_filename", "description"]
    pagination_class = None

    def get_queryset(self):
        user = self.request.user
        if is_unrestricted(user):
            return self.queryset
        org_ids = user_organization_ids(user)
        if not org_ids:
            return self.queryset.none()
        return self.queryset.filter(project__organization_id__in=org_ids)

    def perform_create(self, serializer):
        user = self.request.user
        project = serializer.validated_data.get("project")

        if not is_unrestricted(user):
            allowed_org_ids = user_organization_ids(user)
            if not project or project.organization_id not in allowed_org_ids:
                raise ValidationError({"project": "You do not have permission to upload documents for this project."})

        # Validate file content
        file_obj = self.request.FILES.get("file")
        if file_obj:
            val_res = validate_file_content(file_obj)
            if not val_res["valid"]:
                raise ValidationError({"file": val_res["error"]})
            
            doc = serializer.save(
                uploaded_by=user,
                mime_type=val_res.get("mimeType", ""),
                original_filename=file_obj.name,
                type=val_res.get("extension", ""),
            )

            # Auto-create pending ScheduleImport if schedule format
            if val_res.get("isSchedule") and doc.project:
                ScheduleImport.objects.create(
                    document=doc,
                    project=doc.project,
                    file_format=val_res["extension"],
                    status="uploaded",
                    version_label="v1.0",
                )
        else:
            serializer.save(uploaded_by=user)

    @action(detail=False, methods=["post"], url_path="validate-file")
    def validate_file(self, request):
        """Pre-flight endpoint for frontend drag-and-drop validation."""
        file_obj = request.FILES.get("file")
        if not file_obj:
            return Response({"valid": False, "error": "No file provided."}, status=status.HTTP_400_BAD_REQUEST)
        res = validate_file_content(file_obj)
        return Response(res)

    @action(detail=True, methods=["post"], url_path="parse-schedule")
    def parse_schedule(self, request, pk=None):
        """Server-side parsing of MPP / XML schedule into preview data."""
        doc = self.get_object()
        if not doc.project:
            return Response({"error": "Document has no associated project."}, status=status.HTTP_400_BAD_REQUEST)

        file_path = doc.file.path
        if not os.path.exists(file_path):
            return Response({"error": "Document file not found on disk."}, status=status.HTTP_404_NOT_FOUND)

        schedule_import = doc.schedule_imports.first()
        if not schedule_import:
            ext = doc.type or doc.file.name.rsplit(".", 1)[-1].upper()
            schedule_import = ScheduleImport.objects.create(
                document=doc,
                project=doc.project,
                file_format=ext,
                status="processing",
            )
        else:
            schedule_import.status = "processing"
            schedule_import.save(update_fields=["status"])

        doc.processing_status = "processing"
        doc.save(update_fields=["processing_status"])

        try:
            parsed = ScheduleParserService.parse_file(file_path, original_filename=doc.original_filename or doc.file.name)
            summary = parsed["summary"]
            tasks = parsed["tasks"]

            # Generate diff comparison against current database tasks
            comparison = ScheduleParserService.compare_schedule(doc.project, tasks)

            # Auto-ensure tower and floors are created and synced from schedule
            structure_sync = ScheduleParserService.sync_project_towers_and_floors(doc.project, tasks_data=tasks)

            schedule_import.parsed_summary = summary
            schedule_import.raw_tasks_data = tasks
            schedule_import.status = "awaiting_confirmation"
            schedule_import.error_message = ""
            schedule_import.save()

            doc.processing_status = "completed"
            doc.save(update_fields=["processing_status"])

            return Response({
                "scheduleImportId": schedule_import.id,
                "status": schedule_import.status,
                "summary": summary,
                "tasksCount": len(tasks),
                "tasksPreview": tasks[:100],  # sample tree preview
                "comparison": comparison,
                "structureSync": structure_sync,
            })
        except Exception as e:
            schedule_import.status = "failed"
            schedule_import.error_message = str(e)
            schedule_import.save()

            doc.processing_status = "failed"
            doc.save(update_fields=["processing_status"])
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["get"], url_path="schedule-preview")
    def schedule_preview(self, request, pk=None):
        """Returns the parsed schedule preview and comparison."""
        doc = self.get_object()
        schedule_import = doc.schedule_imports.first()
        if not schedule_import or not schedule_import.raw_tasks_data:
            return Response({"error": "Schedule has not been parsed yet."}, status=status.HTTP_404_NOT_FOUND)

        structure_sync = ScheduleParserService.sync_project_towers_and_floors(doc.project, tasks_data=schedule_import.raw_tasks_data)
        comparison = ScheduleParserService.compare_schedule(doc.project, schedule_import.raw_tasks_data)
        return Response({
            "scheduleImportId": schedule_import.id,
            "status": schedule_import.status,
            "summary": schedule_import.parsed_summary,
            "tasksCount": len(schedule_import.raw_tasks_data),
            "tasks": schedule_import.raw_tasks_data,
            "comparison": comparison,
            "structureSync": structure_sync,
        })

    @action(detail=True, methods=["post"], url_path="confirm-schedule-import")
    def confirm_schedule_import(self, request, pk=None):
        """Confirms import, generates Task hierarchy, dependencies, checklists, and versions."""
        doc = self.get_object()
        schedule_import = doc.schedule_imports.first()
        if not schedule_import or not schedule_import.raw_tasks_data:
            return Response({"error": "No parsed schedule available to import."}, status=status.HTTP_400_BAD_REQUEST)

        mode = request.data.get("mode", "create_new_version")
        version_label = request.data.get("versionLabel", "v1.0")
        if version_label:
            schedule_import.version_label = version_label

        try:
            result = ScheduleParserService.execute_import(schedule_import, mode=mode)
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"Failed to persist schedule: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=["get"], url_path="versions")
    def versions(self, request, pk=None):
        """List version history of a document."""
        doc = self.get_object()
        root = doc.parent_document or doc
        all_versions = Document.objects.filter(models.Q(id=root.id) | models.Q(parent_document=root)).order_by("-version")
        return Response(DocumentSerializer(all_versions, many=True).data)

    @action(detail=True, methods=["get"], url_path="download")
    def download(self, request, pk=None):
        """Secure authorized file download stream."""
        doc = self.get_object()
        if not doc.file or not os.path.exists(doc.file.path):
            raise Http404("Document file not found.")

        filename = doc.original_filename or os.path.basename(doc.file.name)
        response = FileResponse(open(doc.file.path, "rb"), as_attachment=True, filename=filename)
        return response


class ScheduleImportViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ScheduleImport.objects.select_related("project", "document").all()
    serializer_class = ScheduleImportSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["project", "status"]
    pagination_class = None

    def get_queryset(self):
        user = self.request.user
        if is_unrestricted(user):
            return self.queryset
        org_ids = user_organization_ids(user)
        return self.queryset.filter(project__organization_id__in=org_ids)


class ScheduleVersionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ScheduleVersion.objects.select_related("project").all()
    serializer_class = ScheduleVersionSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["project", "is_active"]
    pagination_class = None


class DigitalTwinTaskMappingViewSet(viewsets.ModelViewSet):
    queryset = DigitalTwinTaskMapping.objects.select_related(
        "task", "project", "tower", "floor", "unit"
    ).all()
    serializer_class = DigitalTwinTaskMappingSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["project", "tower", "floor", "unit", "task"]
    pagination_class = None

    def get_queryset(self):
        user = self.request.user
        if is_unrestricted(user):
            return self.queryset
        org_ids = user_organization_ids(user)
        return self.queryset.filter(project__organization_id__in=org_ids)

    @action(detail=False, methods=["post"], url_path="bulk-map")
    def bulk_map(self, request):
        """Maps a list of tasks to a tower, floor, unit, or zone."""
        task_ids = request.data.get("taskIds", [])
        project_id = request.data.get("projectId")
        tower_id = request.data.get("towerId")
        floor_id = request.data.get("floorId")
        unit_id = request.data.get("unitId")
        zone_name = request.data.get("zoneName", "")
        element_id = request.data.get("elementIdentifier", "")

        if not task_ids or not project_id:
            return Response({"error": "taskIds and projectId are required."}, status=status.HTTP_400_BAD_REQUEST)

        created_count = 0
        for tid in task_ids:
            mapping, created = DigitalTwinTaskMapping.objects.update_or_create(
                task_id=tid,
                project_id=project_id,
                defaults={
                    "tower_id": tower_id,
                    "floor_id": floor_id,
                    "unit_id": unit_id,
                    "zone_name": zone_name,
                    "element_identifier": element_id,
                },
            )
            if created:
                created_count += 1

        return Response({
            "status": "success",
            "mappedCount": len(task_ids),
            "newlyCreated": created_count,
        })
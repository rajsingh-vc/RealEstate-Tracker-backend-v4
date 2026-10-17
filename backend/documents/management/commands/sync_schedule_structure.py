import logging
from django.core.management.base import BaseCommand
from projects.models import Project
from documents.services.schedule_parser import ScheduleParserService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Auto-creates missing Towers, extracts Floors/Basements/Terraces from schedules and maps tasks."

    def add_arguments(self, parser):
        parser.add_argument(
            "--project-id",
            type=int,
            help="Optional ID of specific project to sync. Defaults to all projects.",
        )

    def handle(self, *args, **options):
        project_id = options.get("project_id")
        if project_id:
            projects = Project.objects.filter(id=project_id)
        else:
            projects = Project.objects.all()

        total_synced = 0
        for project in projects:
            self.stdout.write(f"Syncing towers, floors, and tasks for project {project.id}: {project.name}...")
            result = ScheduleParserService.sync_project_towers_and_floors(project)
            self.stdout.write(
                self.style.SUCCESS(
                    f"  -> Tower: {result['towerName']} | Floors: {result['totalFloors']} | "
                    f"Mapped Tasks: {result['mappedTasksCount']}/{result['totalTasksCount']}"
                )
            )
            total_synced += 1

        self.stdout.write(self.style.SUCCESS(f"Successfully synced {total_synced} project(s)."))

from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from accounts.models import Company, User
from projects.models import Project
from documents.models import Document, ScheduleImport, ScheduleVersion
from documents.services.schedule_parser import ScheduleParserService, UniversalXmlScheduleParser
from tasks.models import Task, TaskDependency, TaskChecklistItem
import tempfile
import os

SAMPLE_MSPDI_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Project xmlns="http://schemas.microsoft.com/project">
    <Name>Tower A Structural Schedule</Name>
    <StartDate>2026-11-01T08:00:00</StartDate>
    <FinishDate>2027-04-30T17:00:00</FinishDate>
    <Author>Konstruct PM</Author>
    <Company>Notandas Realty</Company>
    <Tasks>
        <Task>
            <UID>1</UID>
            <ID>1</ID>
            <Name>Substructure &amp; Foundation</Name>
            <OutlineNumber>1</OutlineNumber>
            <OutlineLevel>1</OutlineLevel>
            <Start>2026-11-01T08:00:00</Start>
            <Finish>2026-12-15T17:00:00</Finish>
            <Duration>PT360H0M0S</Duration>
            <PercentComplete>60</PercentComplete>
            <Summary>1</Summary>
            <Milestone>0</Milestone>
            <Critical>1</Critical>
        </Task>
        <Task>
            <UID>2</UID>
            <ID>2</ID>
            <Name>Piling Works</Name>
            <OutlineNumber>1.1</OutlineNumber>
            <OutlineLevel>2</OutlineLevel>
            <Start>2026-11-01T08:00:00</Start>
            <Finish>2026-11-20T17:00:00</Finish>
            <Duration>PT160H0M0S</Duration>
            <PercentComplete>100</PercentComplete>
            <Summary>0</Summary>
            <Milestone>0</Milestone>
            <Critical>1</Critical>
            <Notes>Borehole survey\nRig stabilization\nConcrete pouring</Notes>
        </Task>
        <Task>
            <UID>3</UID>
            <ID>3</ID>
            <Name>Raft Concreting</Name>
            <OutlineNumber>1.2</OutlineNumber>
            <OutlineLevel>2</OutlineLevel>
            <Start>2026-11-21T08:00:00</Start>
            <Finish>2026-12-15T17:00:00</Finish>
            <Duration>PT200H0M0S</Duration>
            <PercentComplete>20</PercentComplete>
            <Summary>0</Summary>
            <Milestone>0</Milestone>
            <Critical>1</Critical>
            <PredecessorLink>
                <PredecessorUID>2</PredecessorUID>
                <Type>1</Type>
                <LinkLag>0</LinkLag>
            </PredecessorLink>
        </Task>
        <Task>
            <UID>4</UID>
            <ID>4</ID>
            <Name>Foundation Completion Milestone</Name>
            <OutlineNumber>1.3</OutlineNumber>
            <OutlineLevel>2</OutlineLevel>
            <Start>2026-12-15T17:00:00</Start>
            <Finish>2026-12-15T17:00:00</Finish>
            <Duration>PT0H0M0S</Duration>
            <PercentComplete>0</PercentComplete>
            <Summary>0</Summary>
            <Milestone>1</Milestone>
            <Critical>1</Critical>
            <PredecessorLink>
                <PredecessorUID>3</PredecessorUID>
                <Type>1</Type>
                <LinkLag>0</LinkLag>
            </PredecessorLink>
        </Task>
    </Tasks>
</Project>
"""

class ScheduleImportTestCase(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Konstruct Group")
        self.user = User.objects.create(username="pm_user", email="pm@konstruct.world", name="Project Manager")
        self.project = Project.objects.create(name="Skyline Tower", location="Mumbai", organization=self.company)

    def test_xml_schedule_parsing_and_persistence(self):
        with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False) as f:
            f.write(SAMPLE_MSPDI_XML)
            temp_path = f.name

        try:
            # 1. Test parser
            result = UniversalXmlScheduleParser.parse(temp_path)
            summary = result["summary"]
            tasks = result["tasks"]

            self.assertEqual(summary["totalTasks"], 4)
            self.assertEqual(summary["milestonesCount"], 1)
            self.assertEqual(summary["summaryTasksCount"], 1)
            self.assertEqual(summary["subtasksCount"], 3)
            self.assertEqual(tasks[1]["name"], "Piling Works")
            self.assertEqual(tasks[2]["predecessors"][0]["predecessorUniqueId"], 2)

            # 2. Test ScheduleImport creation & execute_import
            doc_file = SimpleUploadedFile("schedule.xml", SAMPLE_MSPDI_XML.encode("utf-8"), content_type="application/xml")
            doc = Document.objects.create(name="Master Schedule", file=doc_file, project=self.project, uploaded_by=self.user)
            
            sched_import = ScheduleImport.objects.create(
                document=doc,
                project=self.project,
                version_label="v1.0",
                parsed_summary=summary,
                raw_tasks_data=tasks,
                status="awaiting_confirmation",
            )

            import_result = ScheduleParserService.execute_import(sched_import, mode="create_new_version")
            self.assertEqual(import_result["status"], "completed")
            self.assertEqual(import_result["importedTasksCount"], 4)

            # Verify persisted tasks
            persisted_tasks = Task.objects.filter(project=self.project)
            self.assertEqual(persisted_tasks.count(), 4)

            # Verify hierarchy
            parent = Task.objects.get(project=self.project, source_ref="1")
            child = Task.objects.get(project=self.project, source_ref="2")
            self.assertEqual(child.parent_id, parent.id)

            # Verify dependency
            raft_task = Task.objects.get(project=self.project, source_ref="3")
            dep = TaskDependency.objects.filter(task=raft_task, predecessor=child).first()
            self.assertIsNotNone(dep)
            self.assertEqual(dep.dependency_type, "FS")

            # Verify checklist generation from notes
            checklists = TaskChecklistItem.objects.filter(task=child)
            self.assertGreaterEqual(checklists.count(), 3)
            self.assertTrue(checklists.filter(title="Borehole survey").exists())

            # Verify milestone
            ms_task = Task.objects.get(project=self.project, source_ref="4")
            self.assertTrue(ms_task.is_milestone)

            # Verify schedule version
            self.assertEqual(ScheduleVersion.objects.filter(project=self.project).count(), 1)
            active_ver = ScheduleVersion.objects.get(project=self.project, is_active=True)
            self.assertEqual(active_ver.total_tasks, 4)

        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

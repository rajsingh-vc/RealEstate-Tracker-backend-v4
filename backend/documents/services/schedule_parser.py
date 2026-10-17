import os
import re
import sys
from datetime import datetime, date
from decimal import Decimal
import xml.etree.ElementTree as ET
from django.db import transaction
from django.utils import timezone

# Optional / Graceful MPXJ loader
MPXJ_AVAILABLE = False
try:
    if "JAVA_HOME" not in os.environ:
        if os.path.exists(r"C:\Program Files\Java\jdk-24"):
            os.environ["JAVA_HOME"] = r"C:\Program Files\Java\jdk-24"
        elif os.path.exists(r"C:\Program Files\Java"):
            jdks = [os.path.join(r"C:\Program Files\Java", d) for d in os.listdir(r"C:\Program Files\Java") if "jdk" in d.lower()]
            if jdks:
                os.environ["JAVA_HOME"] = jdks[0]
    import mpxj
    MPXJ_AVAILABLE = True
except Exception as e:
    print(f"[ScheduleParser] MPXJ import notice: {e}")


def ensure_mpxj_jvm():
    """Ensure JPype JVM is started with MPXJ classpath."""
    if not MPXJ_AVAILABLE:
        raise RuntimeError("MPXJ package is not available on this environment.")
    if not mpxj.isJVMStarted():
        classpath = mpxj.getClassPath().split(";")
        mpxj.startJVM(classpath=classpath)


def format_date(d):
    """Normalize date/datetime objects to YYYY-MM-DD string."""
    if not d:
        return None
    if isinstance(d, (datetime, date)):
        return d.strftime("%Y-%m-%d")
    s = str(d).strip()
    if not s:
        return None
    # If Java Date or string like "2026-10-17T08:00:00"
    if "T" in s:
        return s.split("T")[0]
    if " " in s:
        parts = s.split(" ")[0]
        if len(parts) == 10 and parts[4] == "-":
            return parts
    return s[:10] if len(s) >= 10 else s


class UniversalXmlScheduleParser:
    """Pure-Python fallback parser for Microsoft Project XML (MSPDI format)."""

    @staticmethod
    def parse(file_path):
        tree = ET.parse(file_path)
        root = tree.getroot()

        # Handle XML namespace if present
        ns = ""
        if root.tag.startswith("{"):
            ns = root.tag.split("}")[0] + "}"

        def find_text(elem, tag, default=""):
            child = elem.find(f"{ns}{tag}")
            return child.text.strip() if child is not None and child.text else default

        project_name = find_text(root, "Title") or find_text(root, "Name") or "Imported Schedule"
        start_date = format_date(find_text(root, "StartDate"))
        finish_date = format_date(find_text(root, "FinishDate"))
        author = find_text(root, "Author")
        company = find_text(root, "Company")

        tasks_elem = root.find(f"{ns}Tasks")
        raw_tasks = []
        warnings = []

        if tasks_elem is not None:
            for task_node in tasks_elem.findall(f"{ns}Task"):
                uid_str = find_text(task_node, "UID")
                id_str = find_text(task_node, "ID")
                name = find_text(task_node, "Name")

                # Skip blank or null project root task if it has no name
                if not name and id_str == "0":
                    continue
                if not name:
                    continue

                unique_id = int(uid_str) if uid_str.isdigit() else (int(id_str) if id_str.isdigit() else len(raw_tasks) + 1)
                task_id = int(id_str) if id_str.isdigit() else unique_id
                outline_number = find_text(task_node, "OutlineNumber") or str(task_id)
                outline_level = int(find_text(task_node, "OutlineLevel", "1") or "1")
                wbs = find_text(task_node, "WBS") or outline_number

                start = format_date(find_text(task_node, "Start"))
                finish = format_date(find_text(task_node, "Finish"))
                actual_start = format_date(find_text(task_node, "ActualStart"))
                actual_finish = format_date(find_text(task_node, "ActualFinish"))

                # Duration string often looks like PT8H0M0S or similar
                dur_str = find_text(task_node, "Duration", "")
                dur_days = 1.0
                if "H" in dur_str or "D" in dur_str:
                    try:
                        dur_clean = dur_str.replace("PT", "").replace("P", "")
                        if "H" in dur_clean:
                            hours = float(dur_clean.split("H")[0])
                            dur_days = round(hours / 8.0, 2)
                        elif "D" in dur_clean:
                            dur_days = float(dur_clean.split("D")[0])
                    except Exception:
                        dur_days = 1.0

                percent = int(find_text(task_node, "PercentComplete", "0") or "0")
                is_milestone = find_text(task_node, "Milestone", "0") == "1"
                is_summary = find_text(task_node, "Summary", "0") == "1"
                critical = find_text(task_node, "Critical", "0") == "1"
                notes = find_text(task_node, "Notes", "")

                # Predecessors
                predecessors = []
                for pred_node in task_node.findall(f"{ns}PredecessorLink"):
                    pred_uid_str = find_text(pred_node, "PredecessorUID")
                    pred_type_code = find_text(pred_node, "Type", "1")  # 1=FF, 2=FS, 3=SF, 4=SS
                    type_map = {"0": "FF", "1": "FS", "2": "FF", "3": "SS", "4": "SF"}
                    pred_type = type_map.get(pred_type_code, "FS")
                    lag_str = find_text(pred_node, "LinkLag", "0")
                    lag_days = 0.0
                    try:
                        lag_days = round(float(lag_str) / 4800.0, 2)  # tenths of minutes to 8h day
                    except Exception:
                        pass
                    if pred_uid_str.isdigit():
                        predecessors.append({
                            "predecessorUniqueId": int(pred_uid_str),
                            "type": pred_type,
                            "lagDays": lag_days,
                        })

                raw_tasks.append({
                    "id": task_id,
                    "uniqueId": unique_id,
                    "name": name,
                    "wbs": wbs,
                    "outlineNumber": outline_number,
                    "outlineLevel": outline_level,
                    "durationDays": dur_days,
                    "startDate": start,
                    "finishDate": finish,
                    "actualStartDate": actual_start,
                    "actualFinishDate": actual_finish,
                    "baselineStartDate": start,
                    "baselineFinishDate": finish,
                    "percentComplete": percent,
                    "isMilestone": is_milestone,
                    "isSummary": is_summary,
                    "critical": critical,
                    "notes": notes,
                    "predecessors": predecessors,
                    "resources": [],
                    "parentUniqueId": None,
                })

        # Calculate parent relationships using outline numbers (e.g. 1.2 is child of 1)
        outline_map = {t["outlineNumber"]: t["uniqueId"] for t in raw_tasks}
        for t in raw_tasks:
            parts = t["outlineNumber"].split(".")
            if len(parts) > 1:
                parent_outline = ".".join(parts[:-1])
                t["parentUniqueId"] = outline_map.get(parent_outline)

        summary = UniversalXmlScheduleParser.build_summary(
            project_name, start_date, finish_date, author, company, raw_tasks, warnings
        )
        return {"summary": summary, "tasks": raw_tasks}

    @staticmethod
    def build_summary(project_name, start_date, finish_date, author, company, tasks, warnings):
        milestones = [t for t in tasks if t["isMilestone"]]
        summaries = [t for t in tasks if t["isSummary"]]
        critical = [t for t in tasks if t["critical"]]
        
        valid_starts = [t["startDate"] for t in tasks if t.get("startDate")]
        valid_finishes = [t["finishDate"] for t in tasks if t.get("finishDate")]
        earliest_start = min(valid_starts) if valid_starts else start_date
        latest_finish = max(valid_finishes) if valid_finishes else finish_date

        if not valid_starts:
            warnings.append("Some tasks do not specify a scheduled start date.")

        return {
            "projectName": project_name or "Project Schedule",
            "startDate": earliest_start,
            "finishDate": latest_finish,
            "author": author or "",
            "company": company or "",
            "totalTasks": len(tasks),
            "summaryTasksCount": len(summaries),
            "subtasksCount": len(tasks) - len(summaries),
            "milestonesCount": len(milestones),
            "criticalTasksCount": len(critical),
            "warnings": warnings,
        }


class ScheduleParserService:
    """Enterprise parser supporting native .mpp, .xml, .mspdi, .xer."""

    @classmethod
    def parse_file(cls, file_path, original_filename=""):
        ext = (original_filename or file_path).rsplit(".", 1)[-1].lower()

        # If it's XML / MSPDI, try pure XML parser first or MPXJ
        if ext in ["xml", "mspdi"]:
            try:
                return UniversalXmlScheduleParser.parse(file_path)
            except Exception as e:
                print(f"[ScheduleParser] XML direct parse fallback notice: {e}")

        # Otherwise (or for .mpp / .xer), use MPXJ
        if not MPXJ_AVAILABLE:
            if ext in ["xml", "mspdi"]:
                return UniversalXmlScheduleParser.parse(file_path)
            raise RuntimeError(
                f"Cannot parse binary .{ext} file without Java/MPXJ. "
                "Please upload Microsoft Project XML (.xml / .mspdi) or ensure Java JDK is installed."
            )

        try:
            ensure_mpxj_jvm()
            reader_cls = mpxj.JClass("org.mpxj.reader.UniversalProjectReader")
            reader = reader_cls()
            file_obj = mpxj.JClass("java.io.File")(os.path.abspath(file_path))
            project_file = reader.read(file_obj)
            return cls._extract_mpxj_data(project_file)
        except Exception as e:
            # If MPXJ failed and file might be XML
            if ext in ["xml", "mspdi"]:
                return UniversalXmlScheduleParser.parse(file_path)
            raise RuntimeError(f"Server schedule parser error: {str(e)}")

    @classmethod
    def _extract_mpxj_data(cls, project_file):
        props = project_file.getProjectProperties()
        project_name = str(props.getProjectTitle() or props.getName() or "Imported Schedule")
        start_date = format_date(props.getStartDate())
        finish_date = format_date(props.getFinishDate())
        author = str(props.getAuthor() or "")
        company = str(props.getCompany() or "")

        raw_tasks = []
        warnings = []

        all_tasks = project_file.getTasks()
        iterator = all_tasks.iterator()

        while iterator.hasNext():
            task = iterator.next()
            task_id = int(task.getID() or 0)
            task_uid = int(task.getUniqueID() or task_id)
            name = str(task.getName() or "").strip()

            # Skip project root summary if uninformative
            if not name and task_id == 0:
                continue
            if not name:
                continue

            outline_num = str(task.getOutlineNumber() or str(task_id))
            outline_level = int(task.getOutlineLevel() or 1)
            wbs = str(task.getWBS() or outline_num)

            start = format_date(task.getStart())
            finish = format_date(task.getFinish())
            actual_start = format_date(task.getActualStart())
            actual_finish = format_date(task.getActualFinish())
            baseline_start = format_date(task.getBaselineStart()) or start
            baseline_finish = format_date(task.getBaselineFinish()) or finish

            dur = task.getDuration()
            dur_days = float(dur.getDuration()) if dur else 1.0

            pct = int(task.getPercentageComplete() or 0)
            is_milestone = bool(task.getMilestone())
            is_summary = bool(task.getSummary())
            critical = bool(task.getCritical())
            notes = str(task.getNotes() or "").strip()

            parent_task = task.getParentTask()
            parent_uid = int(parent_task.getUniqueID()) if parent_task and int(parent_task.getUniqueID() or 0) != 0 else None

            # Predecessors
            predecessors = []
            pred_list = task.getPredecessors()
            if pred_list:
                pred_iter = pred_list.iterator()
                while pred_iter.hasNext():
                    rel = pred_iter.next()
                    try:
                        target_task = rel.getPredecessorTask()
                        if not target_task:
                            target_task = rel.getSuccessorTask()
                        
                        if target_task:
                            type_str = str(rel.getType() or "FS").upper()
                            if "START_START" in type_str or "SS" in type_str:
                                norm_type = "SS"
                            elif "FINISH_FINISH" in type_str or "FF" in type_str:
                                norm_type = "FF"
                            elif "START_FINISH" in type_str or "SF" in type_str:
                                norm_type = "SF"
                            else:
                                norm_type = "FS"
                            
                            try:
                                lag_dur = rel.getLag()
                                lag_days = float(lag_dur.getDuration()) if lag_dur else 0.0
                            except Exception:
                                lag_days = 0.0

                            predecessors.append({
                                "predecessorUniqueId": int(target_task.getUniqueID()),
                                "type": norm_type,
                                "lagDays": lag_days,
                            })
                    except Exception as rel_err:
                        print(f"[ScheduleParser] Warning processing relation: {rel_err}")

            # Resources
            resources = []
            assign_list = task.getResourceAssignments()
            if assign_list:
                assign_iter = assign_list.iterator()
                while assign_iter.hasNext():
                    assign = assign_iter.next()
                    res = assign.getResource()
                    if res and res.getName():
                        resources.append(str(res.getName()))

            raw_tasks.append({
                "id": task_id,
                "uniqueId": task_uid,
                "name": name,
                "wbs": wbs,
                "outlineNumber": outline_num,
                "outlineLevel": outline_level,
                "durationDays": dur_days,
                "startDate": start,
                "finishDate": finish,
                "actualStartDate": actual_start,
                "actualFinishDate": actual_finish,
                "baselineStartDate": baseline_start,
                "baselineFinishDate": baseline_finish,
                "percentComplete": pct,
                "isMilestone": is_milestone,
                "isSummary": is_summary,
                "critical": critical,
                "notes": notes,
                "parentUniqueId": parent_uid,
                "predecessors": predecessors,
                "resources": resources,
            })

        summary = UniversalXmlScheduleParser.build_summary(
            project_name, start_date, finish_date, author, company, raw_tasks, warnings
        )
        return {"summary": summary, "tasks": raw_tasks}

    @classmethod
    def compare_schedule(cls, project, parsed_tasks):
        """Compare parsed tasks with existing project tasks to generate diff summary."""
        from tasks.models import Task

        existing_tasks = list(Task.objects.filter(project=project))
        by_source_ref = {t.source_ref: t for t in existing_tasks if t.source_ref}
        by_wbs = {t.wbs_code: t for t in existing_tasks if t.wbs_code}
        by_title = {t.title.strip().lower(): t for t in existing_tasks}

        added = []
        modified = []
        unchanged = []
        matched_existing_ids = set()

        for pt in parsed_tasks:
            match = (
                by_source_ref.get(str(pt["uniqueId"]))
                or by_wbs.get(pt["wbs"])
                or by_title.get(pt["name"].strip().lower())
            )

            if not match:
                added.append({
                    "title": pt["name"],
                    "wbs": pt["wbs"],
                    "startDate": pt["startDate"],
                    "finishDate": pt["finishDate"],
                    "durationDays": pt["durationDays"],
                })
            else:
                matched_existing_ids.add(match.id)
                diffs = {}
                if pt["startDate"] and str(match.start_date) != pt["startDate"]:
                    diffs["startDate"] = {"old": str(match.start_date), "new": pt["startDate"]}
                if pt["finishDate"] and str(match.end_date) != pt["finishDate"]:
                    diffs["finishDate"] = {"old": str(match.end_date), "new": pt["finishDate"]}
                if pt["durationDays"] and match.duration_days != pt["durationDays"]:
                    diffs["durationDays"] = {"old": match.duration_days, "new": pt["durationDays"]}
                if pt["percentComplete"] is not None and match.progress != pt["percentComplete"]:
                    diffs["progress"] = {"old": match.progress, "new": pt["percentComplete"]}

                if diffs:
                    modified.append({
                        "taskId": match.id,
                        "title": pt["name"],
                        "wbs": pt["wbs"],
                        "diffs": diffs,
                    })
                else:
                    unchanged.append({
                        "taskId": match.id,
                        "title": pt["name"],
                        "wbs": pt["wbs"],
                    })

        # Removed tasks: only tasks previously tagged with a schedule source_ref
        removed = [
            {"taskId": t.id, "title": t.title, "wbs": t.wbs_code}
            for t in existing_tasks
            if t.source_ref and t.id not in matched_existing_ids
        ]

        return {
            "hasExistingSchedule": len(existing_tasks) > 0,
            "existingTasksCount": len(existing_tasks),
            "addedCount": len(added),
            "modifiedCount": len(modified),
            "unchangedCount": len(unchanged),
            "removedCount": len(removed),
            "added": added[:50],  # preview sample
            "modified": modified[:50],
            "removed": removed[:50],
        }

    @classmethod
    @transaction.atomic
    def execute_import(cls, schedule_import, mode="create_new_version"):
        """
        Idempotent database persistence for confirmed schedule.
        Creates Task hierarchy, TaskDependency, checklists, and ScheduleVersion.
        """
        from tasks.models import Task, TaskDependency, TaskChecklistItem
        from documents.models import ScheduleVersion, ImportChangeLog

        project = schedule_import.project
        tasks_data = schedule_import.raw_tasks_data or []

        # Determine version number
        latest_version = ScheduleVersion.objects.filter(project=project).order_by("-version_number").first()
        next_ver_num = (latest_version.version_number + 1) if latest_version else 1

        if mode == "create_new_version":
            ScheduleVersion.objects.filter(project=project, is_active=True).update(is_active=False)
            schedule_ver = ScheduleVersion.objects.create(
                project=project,
                version_number=next_ver_num,
                name=f"Schedule {schedule_import.version_label or f'v{next_ver_num}.0'}",
                is_active=True,
                import_source=schedule_import,
                total_tasks=len(tasks_data),
            )
        else:
            schedule_ver = latest_version or ScheduleVersion.objects.create(
                project=project,
                version_number=1,
                name="Schedule v1.0",
                is_active=True,
                import_source=schedule_import,
                total_tasks=len(tasks_data),
            )

        # Existing map by source_ref and wbs_code
        existing_tasks = {t.source_ref: t for t in Task.objects.filter(project=project) if t.source_ref}
        existing_by_wbs = {t.wbs_code: t for t in Task.objects.filter(project=project) if t.wbs_code}

        task_records = {}  # uniqueId -> Task instance
        change_logs = []

        # Pass 1: Upsert Task records
        for item in tasks_data:
            uid_str = str(item["uniqueId"])
            wbs = item.get("wbs") or item.get("outlineNumber") or ""
            title = item.get("name") or f"Task {uid_str}"

            target_task = existing_tasks.get(uid_str) or existing_by_wbs.get(wbs)
            is_new = target_task is None

            start = item.get("startDate")
            end = item.get("finishDate")
            baseline_start = item.get("baselineStartDate") or start
            baseline_end = item.get("baselineFinishDate") or end

            status = "not_started"
            pct = int(item.get("percentComplete") or 0)
            if pct == 100:
                status = "completed"
            elif pct > 0:
                status = "in_progress"

            if is_new:
                target_task = Task.objects.create(
                    project=project,
                    title=title,
                    description=item.get("notes") or "",
                    wbs_code=wbs,
                    source_ref=uid_str,
                    source_document=schedule_import.document,
                    start_date=start,
                    end_date=end,
                    baseline_start_date=baseline_start,
                    baseline_end_date=baseline_end,
                    duration_days=item.get("durationDays"),
                    progress=pct,
                    status=status,
                    is_milestone=bool(item.get("isMilestone")),
                    critical_path=bool(item.get("critical")),
                    department="Civil" if not item.get("isSummary") else "Management",
                )
                change_logs.append(
                    ImportChangeLog(
                        schedule_import=schedule_import,
                        change_type="added",
                        task_title=title,
                        wbs_code=wbs,
                        details={"status": status, "start": start, "end": end},
                    )
                )
            else:
                diffs = {}
                if target_task.start_date != start and start:
                    diffs["start"] = {"from": str(target_task.start_date), "to": start}
                    target_task.start_date = start
                if target_task.end_date != end and end:
                    diffs["end"] = {"from": str(target_task.end_date), "to": end}
                    target_task.end_date = end
                if target_task.progress != pct:
                    diffs["progress"] = {"from": target_task.progress, "to": pct}
                    target_task.progress = pct
                    target_task.status = status

                target_task.wbs_code = wbs
                target_task.source_ref = uid_str
                target_task.source_document = schedule_import.document
                target_task.duration_days = item.get("durationDays")
                target_task.is_milestone = bool(item.get("isMilestone"))
                target_task.critical_path = bool(item.get("critical"))
                target_task.save()

                change_logs.append(
                    ImportChangeLog(
                        schedule_import=schedule_import,
                        change_type="modified" if diffs else "unchanged",
                        task_title=title,
                        wbs_code=wbs,
                        details=diffs,
                    )
                )

            task_records[item["uniqueId"]] = target_task

        # Pass 2: Set Hierarchy parent_id
        for item in tasks_data:
            current_task = task_records.get(item["uniqueId"])
            parent_uid = item.get("parentUniqueId")
            if current_task and parent_uid and parent_uid in task_records:
                parent_task = task_records[parent_uid]
                if current_task.parent_id != parent_task.id:
                    current_task.parent = parent_task
                    current_task.save(update_fields=["parent"])

        # Pass 3: Set Dependencies
        for item in tasks_data:
            current_task = task_records.get(item["uniqueId"])
            preds = item.get("predecessors") or []
            if current_task and preds:
                for p in preds:
                    pred_uid = p.get("predecessorUniqueId")
                    if pred_uid and pred_uid in task_records:
                        pred_task = task_records[pred_uid]
                        TaskDependency.objects.update_or_create(
                            task=current_task,
                            predecessor=pred_task,
                            defaults={
                                "dependency_type": p.get("type", "FS"),
                                "lag_days": p.get("lagDays", 0.0),
                                "source_expression": f"{pred_task.wbs_code or pred_uid}{p.get('type','FS')}",
                            },
                        )

        # Pass 4: Automated Checklist generation for leaf tasks or tasks with notes
        for item in tasks_data:
            current_task = task_records.get(item["uniqueId"])
            if current_task and not item.get("isSummary"):
                # If notes contain newline-separated inspection / action items, convert to checklists
                notes = item.get("notes") or ""
                lines = [line.strip().lstrip("-*•").strip() for line in notes.split("\n") if line.strip()]
                
                # If no notes, generate standard quality & safety verification checkpoints
                if not lines:
                    lines = [
                        f"Site clearance & alignment check for {current_task.title}",
                        f"Material inspection & approval for {current_task.title}",
                        f"Execution & quality compliance sign-off",
                    ]

                existing_checklist_titles = set(
                    current_task.checklist_items.values_list("title", flat=True)
                )
                new_items = []
                for idx, title_text in enumerate(lines[:5]):  # limit initial items cleanly
                    if title_text not in existing_checklist_titles:
                        new_items.append(
                            TaskChecklistItem(
                                task=current_task,
                                title=title_text,
                                completed=current_task.status == "completed",
                                order=idx,
                            )
                        )
                if new_items:
                    TaskChecklistItem.objects.bulk_create(new_items)
                    current_task.recalculate_progress_from_checklist()

        # Save change logs
        if change_logs:
            ImportChangeLog.objects.bulk_create(change_logs)

        # Update Project dates & progress rollup
        schedule_summary = schedule_import.parsed_summary or {}
        if schedule_summary.get("startDate") and not project.start_date:
            project.start_date = schedule_summary["startDate"]
        if schedule_summary.get("finishDate") and not project.end_date:
            project.end_date = schedule_summary["finishDate"]

        all_proj_tasks = list(Task.objects.filter(project=project))
        if all_proj_tasks:
            avg_progress = round(sum(t.progress for t in all_proj_tasks) / len(all_proj_tasks))
            project.progress = avg_progress
        project.save()

        # Update schedule import status
        schedule_import.status = "completed"
        schedule_import.save(update_fields=["status", "updated_at"])

        # Pass 5: Auto-create Tower and Floors (Basements, Ground, Numbered, Terrace, Roof) and map tasks
        structure_sync = cls.sync_project_towers_and_floors(project, tasks_data=tasks_data)

        return {
            "status": "completed",
            "versionNumber": schedule_ver.version_number,
            "versionName": schedule_ver.name,
            "importedTasksCount": len(tasks_data),
            "projectProgress": project.progress,
            "structureSync": structure_sync,
        }

    @classmethod
    def extract_floor_info(cls, title):
        t = (title or "").strip()
        if not t:
            return None

        # 1. Basement matching: Basement 5, B5, Lower Basement, Upper Basement
        m = re.search(r'\b(?:basement|b)\s*[-_]?\s*(\d+)\b', t, re.IGNORECASE)
        if m:
            num = int(m.group(1))
            return {"key": f"B{num}", "name": f"Basement {num}", "raw_num": -num, "sort_order": -num, "type": "basement"}

        if re.search(r'\b(lower basement|lb)\b', t, re.IGNORECASE):
            return {"key": "B2", "name": "Lower Basement", "raw_num": -2, "sort_order": -2, "type": "basement"}
        if re.search(r'\b(upper basement|ub)\b', t, re.IGNORECASE):
            return {"key": "B1", "name": "Upper Basement", "raw_num": -1, "sort_order": -1, "type": "basement"}

        # 2. Ground floor / Plinth / Stilt (ignore phrases like 'ground to terrace')
        if re.search(r'\b(gf|ground floor|ground(?:\s*floor)?(?:\s*slab)?|plinth|stilt)\b', t, re.IGNORECASE) and not re.search(r'ground to terrace', t, re.IGNORECASE):
            return {"key": "G", "name": "Ground Floor", "raw_num": 0, "sort_order": 0, "type": "ground"}

        # 3. Podium
        m = re.search(r'\bpodium\s*[-_]?\s*(\d+)\b', t, re.IGNORECASE)
        if m:
            num = int(m.group(1))
            return {"key": f"P{num}", "name": f"Podium {num}", "raw_num": num, "sort_order": 0.1 * num, "type": "podium"}

        # 4. Terrace / Roof / LMR / Mummty
        if re.search(r'\b(mummty|lmr|lift machine room|overhead tank|oht)\b', t, re.IGNORECASE):
            return {"key": "LMR", "name": "Mummty / LMR", "raw_num": 99, "sort_order": 99, "type": "roof"}
        if re.search(r'\b(terrace|roof(?:\s*top)?)\b', t, re.IGNORECASE) and not re.search(r'ground to terrace', t, re.IGNORECASE):
            return {"key": "TERRACE", "name": "Terrace", "raw_num": 90, "sort_order": 90, "type": "terrace"}

        # 5. Numbered floors: "Floor Slab 4", "Floor 10", "1st Floor", "Level 4"
        m = re.search(r'\b(?:floor(?:\s*slab)?|level|lvl|slab)\s*[-_]?\s*(\d+)\b', t, re.IGNORECASE)
        if m:
            num = int(m.group(1))
            return {"key": f"F{num}", "name": f"Floor {num}", "raw_num": num, "sort_order": num, "type": "floor"}

        m = re.search(r'\b(\d+)(?:st|nd|rd|th)\s+(?:floor|slab|level)\b', t, re.IGNORECASE)
        if m:
            num = int(m.group(1))
            return {"key": f"F{num}", "name": f"Floor {num}", "raw_num": num, "sort_order": num, "type": "floor"}

        return None

    @classmethod
    def sync_project_towers_and_floors(cls, project, tasks_data=None):
        """
        Auto-creates a Tower if the project doesn't have one.
        Scans tasks (either raw parsed tasks_data or existing database tasks)
        for floors, basements, terrace, and podiums.
        Creates Floor records under the project's tower and maps tasks/subtasks to them.
        """
        from projects.models import Tower, Floor
        from tasks.models import Task
        from documents.models import DigitalTwinTaskMapping

        # 1. Ensure Tower exists for project
        tower = project.towers.first()
        if not tower:
            tower = Tower.objects.create(
                project=project,
                name="Tower A",
                status="Construction",
            )

        # 2. Collect tasks to scan (from tasks_data or existing database tasks)
        db_tasks = list(Task.objects.filter(project=project).order_by("wbs_code", "id"))

        detected_floors = {}
        # Scan raw tasks data if available
        if tasks_data:
            for item in tasks_data:
                info = cls.extract_floor_info(item.get("name") or "")
                if info:
                    detected_floors[info["key"]] = info

        # Scan existing tasks in DB
        for task in db_tasks:
            info = cls.extract_floor_info(task.title)
            if info:
                detected_floors[info["key"]] = info

        # 3. Create or update Floor models
        sorted_floors = sorted(detected_floors.values(), key=lambda x: x["sort_order"])
        max_pos = 0
        for f in sorted_floors:
            if f["type"] in ("floor", "podium"):
                max_pos = max(max_pos, f["raw_num"])

        floor_key_to_model = {}
        for f in sorted_floors:
            if f["type"] == "basement":
                norm_number = f["raw_num"]
            elif f["type"] == "ground":
                norm_number = 0
            elif f["type"] in ("floor", "podium"):
                norm_number = f["raw_num"]
            elif f["type"] == "terrace":
                norm_number = max_pos + 1
            elif f["type"] == "roof":
                norm_number = max_pos + 2
            else:
                norm_number = f["raw_num"]

            fl_obj, _ = Floor.objects.get_or_create(
                project=project,
                tower=tower,
                name=f["name"],
                defaults={"number": norm_number},
            )
            if fl_obj.number != norm_number:
                fl_obj.number = norm_number
                fl_obj.save(update_fields=["number"])
            floor_key_to_model[f["key"]] = fl_obj

        # Register any existing tower floors into floor_key_to_model by name
        for existing_fl in tower.floors.all():
            for k, f_info in detected_floors.items():
                if f_info["name"].strip().lower() == existing_fl.name.strip().lower():
                    floor_key_to_model[k] = existing_fl

        tower.total_floors = tower.floors.count()
        tower.save(update_fields=["total_floors"])

        # 4. Map tasks and subtasks
        # Direct task-level matches
        task_floor_key = {}
        for task in db_tasks:
            fk = cls.extract_floor_info(task.title)
            if fk:
                task_floor_key[task.id] = fk["key"]

        # Hierarchical inheritance: subtasks inherit from parent WBS
        wbs_to_key = {}
        for task in db_tasks:
            if task.id in task_floor_key and task.wbs_code:
                wbs_to_key[task.wbs_code] = task_floor_key[task.id]

        for task in db_tasks:
            if task.id not in task_floor_key and task.wbs_code:
                parts = task.wbs_code.split(".")
                for d in range(len(parts) - 1, 0, -1):
                    parent_wbs = ".".join(parts[:d])
                    if parent_wbs in wbs_to_key:
                        task_floor_key[task.id] = wbs_to_key[parent_wbs]
                        break

        # Save tower and floor on Task instances
        mapped_tasks_count = 0
        digital_twin_mappings = []
        for task in db_tasks:
            task.tower = tower
            fk = task_floor_key.get(task.id)
            if fk and fk in floor_key_to_model:
                task.floor = floor_key_to_model[fk]
                mapped_tasks_count += 1
                digital_twin_mappings.append(
                    DigitalTwinTaskMapping(
                        task=task,
                        project=project,
                        tower=tower,
                        floor=task.floor,
                        zone_name=task.floor.name,
                        element_identifier=f"floor-{task.floor.number}",
                    )
                )
            else:
                task.floor = None
            task.save(update_fields=["tower", "floor"])

        # Create Digital Twin mappings
        if digital_twin_mappings:
            DigitalTwinTaskMapping.objects.filter(project=project).delete()
            DigitalTwinTaskMapping.objects.bulk_create(digital_twin_mappings, ignore_conflicts=True)

        # Sync Checklists & SubTasks from task inspection items and hierarchical child tasks
        from checklists.models import Checklist, SubTask
        for task in db_tasks:
            # 1. From TaskChecklistItem
            items = list(task.checklist_items.all())
            if items:
                chk, _ = Checklist.objects.get_or_create(
                    task=task,
                    project=project,
                    name=f"{task.title} Inspection Checklist",
                    defaults={
                        "status": "completed" if task.status == "completed" else "pending",
                        "progress": task.progress,
                        "tower": tower,
                        "floor": task.floor,
                    },
                )
                if chk.tower != tower or chk.floor != task.floor:
                    chk.tower = tower
                    chk.floor = task.floor
                    chk.save(update_fields=["tower", "floor"])

                for item in items:
                    SubTask.objects.get_or_create(
                        checklist=chk,
                        task=task,
                        project=project,
                        name=item.title,
                        defaults={
                            "status": "completed" if item.completed else "pending",
                            "progress": 100 if item.completed else 0,
                            "tower": tower,
                            "floor": task.floor,
                        },
                    )

            # 2. From child tasks
            child_tasks = list(task.subtasks.all())
            if child_tasks:
                pkg_chk, _ = Checklist.objects.get_or_create(
                    task=task,
                    project=project,
                    name=f"{task.title} Work Package",
                    defaults={
                        "status": "completed" if task.status == "completed" else "pending",
                        "progress": task.progress,
                        "tower": tower,
                        "floor": task.floor,
                    },
                )
                if pkg_chk.tower != tower or pkg_chk.floor != task.floor:
                    pkg_chk.tower = tower
                    pkg_chk.floor = task.floor
                    pkg_chk.save(update_fields=["tower", "floor"])

                for child in child_tasks:
                    SubTask.objects.get_or_create(
                        checklist=pkg_chk,
                        task=task,
                        project=project,
                        name=child.title,
                        defaults={
                            "status": child.status,
                            "progress": child.progress,
                            "tower": child.tower or tower,
                            "floor": child.floor or task.floor,
                        },
                    )

        return {
            "towerId": tower.id,
            "towerName": tower.name,
            "totalFloors": tower.total_floors,
            "detectedFloorsCount": len(floor_key_to_model),
            "mappedTasksCount": mapped_tasks_count,
            "totalTasksCount": len(db_tasks),
        }

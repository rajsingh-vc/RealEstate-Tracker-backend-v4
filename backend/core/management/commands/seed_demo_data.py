"""
Seeds the database with the exact demo dataset the frontend ships with:
  - src/data/demo-data.ts (users, projects, towers, floors, units, tasks,
    hurdles, checklist templates, resources)
  - the per-page localStorage seeds in Compliance.tsx, Handover.tsx,
    Society.tsx and Admin.tsx

Run with: python manage.py seed_demo_data
Safe to re-run — uses get_or_create/update_or_create throughout.

All seeded users share the password: demo1234
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from adminpanel.models import EscalationRule
from checklists.models import ChecklistTemplate, ChecklistTemplateItem
from compliance.models import ComplianceItem
from handover.models import HandoverUnit
from hurdles.models import Hurdle
from projects.models import Floor, Project, Tower, Unit
from resources.models import Resource, ResourceMachine, ResourceMaterial
from society.models import Society, SocietyStep
from tasks.models import Task, TaskChecklistItem, TaskComment

User = get_user_model()

DEMO_PASSWORD = "demo1234"

# ---------------------------------------------------------------------------
# Raw data transcribed 1:1 from src/data/demo-data.ts
# ---------------------------------------------------------------------------

USERS = [
    {"id": "u1", "name": "Rajesh Sharma", "role": "CEO", "department": "Admin", "email": "rajesh@vibe.com"},
    {"id": "u2", "name": "Priya Mehta", "role": "Project Director", "department": "Admin", "email": "priya@vibe.com"},
    {"id": "u3", "name": "Amit Patel", "role": "HOD", "department": "Civil", "email": "amit@vibe.com"},
    {"id": "u4", "name": "Sunita Rao", "role": "HOD", "department": "Electrical", "email": "sunita@vibe.com"},
    {"id": "u5", "name": "Vikram Singh", "role": "HOD", "department": "Plumbing", "email": "vikram@vibe.com"},
    {"id": "u6", "name": "Deepak Kumar", "role": "Site Engineer", "department": "Civil", "email": "deepak@vibe.com"},
    {"id": "u7", "name": "Anita Joshi", "role": "Site Engineer", "department": "Electrical", "email": "anita@vibe.com"},
    {"id": "u8", "name": "Rahul Gupta", "role": "Site Engineer", "department": "Plumbing", "email": "rahul@vibe.com"},
    {"id": "u9", "name": "Suresh Verma", "role": "HOD", "department": "Finishing", "email": "suresh@vibe.com"},
    {"id": "u10", "name": "Pooja Desai", "role": "HOD", "department": "Fire Safety", "email": "pooja@vibe.com"},
    {"id": "u11", "name": "Kiran Patil", "role": "Vendor", "department": "MEP", "email": "kiran@vendor.com"},
    {"id": "u12", "name": "Manoj Tiwari", "role": "Site Engineer", "department": "Finishing", "email": "manoj@vibe.com"},
]

PROJECTS = [
    {"id": "p1", "name": "Marine Heights", "location": "Worli, Mumbai", "status": "active",
     "start_date": "2024-01-15", "end_date": "2026-12-31", "progress": 42,
     "total_units": 240, "rera_number": "P51900028372", "budget": 850000000, "spent": 357000000},
    {"id": "p2", "name": "Skyline Residences", "location": "Andheri West, Mumbai", "status": "active",
     "start_date": "2024-06-01", "end_date": "2027-06-30", "progress": 28,
     "total_units": 360, "rera_number": "P51900031245", "budget": 1200000000, "spent": 336000000},
    {"id": "p3", "name": "Palm Gardens", "location": "Thane West", "status": "planning",
     "start_date": "2025-03-01", "end_date": "2028-03-31", "progress": 8,
     "total_units": 120, "rera_number": "P51900034567", "budget": 450000000, "spent": 36000000},
]

TOWERS = [
    {"id": "t1", "name": "Tower A", "project_id": "p1", "total_floors": 30, "progress": 48, "status": "Construction"},
    {"id": "t2", "name": "Tower B", "project_id": "p1", "total_floors": 25, "progress": 35, "status": "Construction"},
    {"id": "t3", "name": "Tower A", "project_id": "p2", "total_floors": 35, "progress": 32, "status": "Construction"},
    {"id": "t4", "name": "Tower B", "project_id": "p2", "total_floors": 35, "progress": 25, "status": "Foundation"},
    {"id": "t5", "name": "Tower C", "project_id": "p2", "total_floors": 28, "progress": 20, "status": "Foundation"},
    {"id": "t6", "name": "Tower A", "project_id": "p3", "total_floors": 20, "progress": 8, "status": "Planning"},
]

FLOORS = [
    {"id": "f1", "name": "Floor 1", "number": 1, "tower_id": "t1", "units": ["un1", "un2", "un3", "un4"]},
    {"id": "f2", "name": "Floor 2", "number": 2, "tower_id": "t1", "units": ["un5", "un6", "un7", "un8"]},
    {"id": "f3", "name": "Floor 5", "number": 5, "tower_id": "t1", "units": ["un9", "un10", "un11", "un12"]},
    {"id": "f4", "name": "Floor 10", "number": 10, "tower_id": "t1", "units": ["un13", "un14", "un15", "un16"]},
    {"id": "f5", "name": "Floor 12", "number": 12, "tower_id": "t1", "units": ["un17", "un18", "un19", "un20"]},
    {"id": "f6", "name": "Floor 1", "number": 1, "tower_id": "t2", "units": ["un21", "un22", "un23", "un24"]},
    {"id": "f7", "name": "Floor 2", "number": 2, "tower_id": "t2", "units": ["un25", "un26"]},
    {"id": "f8", "name": "Floor 5", "number": 5, "tower_id": "t2", "units": ["un27", "un28"]},
    {"id": "f9", "name": "Floor 8", "number": 8, "tower_id": "t2", "units": ["un29", "un30"]},
    {"id": "f10", "name": "Floor 10", "number": 10, "tower_id": "t2", "units": ["un31", "un32"]},
    {"id": "f11", "name": "Floor 1", "number": 1, "tower_id": "t3", "units": ["un33", "un34"]},
    {"id": "f12", "name": "Floor 5", "number": 5, "tower_id": "t3", "units": ["un35", "un36"]},
    {"id": "f13", "name": "Floor 10", "number": 10, "tower_id": "t3", "units": ["un37", "un38"]},
    {"id": "f14", "name": "Floor 1", "number": 1, "tower_id": "t4", "units": ["un39", "un40"]},
    {"id": "f15", "name": "Floor 3", "number": 3, "tower_id": "t4", "units": ["un41", "un42"]},
    {"id": "f16", "name": "Floor 5", "number": 5, "tower_id": "t4", "units": ["un43", "un44"]},
    {"id": "f17", "name": "Floor 1", "number": 1, "tower_id": "t5", "units": ["un45", "un46"]},
    {"id": "f18", "name": "Floor 3", "number": 3, "tower_id": "t5", "units": ["un47", "un48"]},
    {"id": "f19", "name": "Floor 1", "number": 1, "tower_id": "t6", "units": ["un49", "un50"]},
    {"id": "f20", "name": "Floor 2", "number": 2, "tower_id": "t6", "units": ["un51", "un52"]},
]

UNIT_TYPES = ["1BHK", "2BHK", "3BHK", "4BHK"]
UNIT_AREAS = [550, 850, 1200, 1600]

TASKS = [
    {"id": "task1", "title": "Foundation Excavation", "description": "Complete excavation for Tower A foundation",
     "department": "Civil", "assigned_hod": "u3", "assigned_users": ["u6"],
     "start_date": "2024-02-01", "end_date": "2024-04-15", "actual_start_date": "2024-02-05", "actual_end_date": "2024-04-20",
     "priority": "critical", "status": "completed", "dependencies": [], "progress": 100, "delay_days": 5,
     "delay_reason": "Monsoon delay", "critical_path": True, "project_id": "p1", "tower_id": "t1", "floor_id": "f1", "phase": "Foundation",
     "checklist": ["Site survey completed", "Soil testing done", "Excavation plan approved", "Safety barriers installed"],
     "checklist_completed": [True, True, True, True],
     "comments": [{"user": "Amit Patel", "text": "Excavation completed with minor delays due to rain", "date": "2024-04-20"}]},
    {"id": "task2", "title": "RCC Foundation", "description": "RCC foundation work for Tower A",
     "department": "Civil", "assigned_hod": "u3", "assigned_users": ["u6"],
     "start_date": "2024-04-20", "end_date": "2024-07-30", "actual_start_date": "2024-04-25",
     "priority": "critical", "status": "completed", "dependencies": ["task1"], "progress": 100, "delay_days": 0,
     "critical_path": True, "project_id": "p1", "tower_id": "t1", "floor_id": "f1", "phase": "Foundation",
     "checklist": ["Rebar placement done", "Formwork installed", "Concrete pouring done", "Curing completed"],
     "checklist_completed": [True, True, True, True], "comments": []},
    {"id": "task3", "title": "Structural Column Work - F1", "description": "Column casting for Floor 1",
     "department": "Structural", "assigned_hod": "u3", "assigned_users": ["u6"],
     "start_date": "2024-08-01", "end_date": "2024-09-15", "actual_start_date": "2024-08-03",
     "priority": "high", "status": "completed", "dependencies": ["task2"], "progress": 100, "delay_days": 0,
     "critical_path": True, "project_id": "p1", "tower_id": "t1", "floor_id": "f1", "phase": "Structure",
     "checklist": ["Column layout marked", "Rebar tied", "Column casting done"],
     "checklist_completed": [True, True, True], "comments": []},
    {"id": "task4", "title": "Slab Casting - Floor 1", "description": "Slab casting for Floor 1, Tower A",
     "department": "Civil", "assigned_hod": "u3", "assigned_users": ["u6"],
     "start_date": "2024-09-16", "end_date": "2024-10-30", "actual_start_date": "2024-09-18",
     "priority": "high", "status": "completed", "dependencies": ["task3"], "progress": 100, "delay_days": 0,
     "critical_path": True, "project_id": "p1", "tower_id": "t1", "floor_id": "f1", "phase": "Structure",
     "checklist": ["Shuttering done", "Slab rebar placed", "Concrete poured", "De-shuttering done"],
     "checklist_completed": [True, True, True, True], "comments": []},
    {"id": "task5", "title": "Slab Casting - Floor 2", "description": "Slab casting for Floor 2",
     "department": "Civil", "assigned_hod": "u3", "assigned_users": ["u6"],
     "start_date": "2024-11-01", "end_date": "2024-12-15", "actual_start_date": "2024-11-05",
     "priority": "high", "status": "completed", "dependencies": ["task4"], "progress": 100, "delay_days": 0,
     "critical_path": True, "project_id": "p1", "tower_id": "t1", "floor_id": "f2", "phase": "Structure",
     "checklist": ["Shuttering done", "Concrete poured"], "checklist_completed": [True, True], "comments": []},
    {"id": "task6", "title": "Electrical Conduit - Floor 1", "description": "Electrical conduit installation Floor 1",
     "department": "Electrical", "assigned_hod": "u4", "assigned_users": ["u7"],
     "start_date": "2024-11-01", "end_date": "2024-12-30",
     "priority": "medium", "status": "completed", "dependencies": ["task4"], "progress": 100, "delay_days": 0,
     "critical_path": False, "project_id": "p1", "tower_id": "t1", "floor_id": "f1", "phase": "MEP",
     "checklist": ["Layout marking", "Conduit installed", "Wiring pulled"],
     "checklist_completed": [True, True, True], "comments": []},
    {"id": "task7", "title": "Plumbing Rough-in - Floor 1", "description": "Plumbing rough-in for Floor 1 units",
     "department": "Plumbing", "assigned_hod": "u5", "assigned_users": ["u8"],
     "start_date": "2024-11-15", "end_date": "2025-01-15",
     "priority": "medium", "status": "completed", "dependencies": ["task4"], "progress": 100, "delay_days": 0,
     "critical_path": False, "project_id": "p1", "tower_id": "t1", "floor_id": "f1", "phase": "MEP",
     "checklist": ["Pipe layout done", "Pressure tested"], "checklist_completed": [True, True], "comments": []},
    {"id": "task8", "title": "Slab Casting - Floor 5", "description": "Structural slab for Floor 5",
     "department": "Civil", "assigned_hod": "u3", "assigned_users": ["u6"],
     "start_date": "2025-01-15", "end_date": "2025-03-15", "actual_start_date": "2025-01-20",
     "priority": "high", "status": "in_progress", "dependencies": ["task5"], "progress": 65, "delay_days": 0,
     "critical_path": True, "project_id": "p1", "tower_id": "t1", "floor_id": "f3", "phase": "Structure",
     "checklist": ["Shuttering done", "Rebar placed", "Concrete pour"],
     "checklist_completed": [True, True, False],
     "comments": [{"user": "Deepak Kumar", "text": "Rebar inspection passed. Pour scheduled for next week.", "date": "2025-03-05"}]},
    {"id": "task9", "title": "Electrical Conduit - Floor 2", "description": "Electrical work on Floor 2",
     "department": "Electrical", "assigned_hod": "u4", "assigned_users": ["u7"],
     "start_date": "2025-01-01", "end_date": "2025-02-28",
     "priority": "medium", "status": "in_progress", "dependencies": ["task5"], "progress": 72, "delay_days": 3,
     "delay_reason": "Material shortage", "critical_path": False, "project_id": "p1", "tower_id": "t1", "floor_id": "f2", "phase": "MEP",
     "checklist": ["Layout marking", "Conduit installed", "Wiring pulled", "Inspection"],
     "checklist_completed": [True, True, False, False], "comments": []},
    {"id": "task10", "title": "Plumbing Installation - Unit 1203", "description": "Kitchen & bathroom plumbing for Unit 1203",
     "department": "Plumbing", "assigned_hod": "u5", "assigned_users": ["u8"],
     "start_date": "2025-02-01", "end_date": "2025-04-15",
     "priority": "medium", "status": "in_progress", "dependencies": [], "progress": 40, "delay_days": 0,
     "critical_path": False, "project_id": "p1", "tower_id": "t1", "floor_id": "f5", "unit_id": "un17", "phase": "MEP",
     "checklist": ["Kitchen plumbing layout", "Kitchen pipe installation", "Bathroom plumbing layout", "Bathroom pipe installation", "Pressure testing"],
     "checklist_completed": [True, True, False, False, False], "comments": []},
    {"id": "task11", "title": "Electrical Wiring - Unit 1203", "description": "Complete electrical wiring for Unit 1203",
     "department": "Electrical", "assigned_hod": "u4", "assigned_users": ["u7"],
     "start_date": "2025-02-15", "end_date": "2025-04-30",
     "priority": "medium", "status": "not_started", "dependencies": [], "progress": 0, "delay_days": 0,
     "critical_path": False, "project_id": "p1", "tower_id": "t1", "floor_id": "f5", "unit_id": "un17", "phase": "MEP",
     "checklist": ["Switch board layout", "Wiring installation", "Earthing completed"],
     "checklist_completed": [False, False, False], "comments": []},
    {"id": "task12", "title": "Bathroom Waterproofing - Unit 1203", "description": "Waterproofing treatment for all bathrooms",
     "department": "Civil", "assigned_hod": "u3", "assigned_users": ["u6"],
     "start_date": "2025-03-01", "end_date": "2025-04-15",
     "priority": "high", "status": "not_started", "dependencies": ["task10"], "progress": 0, "delay_days": 0,
     "critical_path": False, "project_id": "p1", "tower_id": "t1", "floor_id": "f5", "unit_id": "un17", "phase": "Finishing",
     "checklist": ["Surface preparation", "Waterproofing coat applied", "Water ponding test"],
     "checklist_completed": [False, False, False], "comments": []},
    {"id": "task13", "title": "Slab Casting - Floor 10", "description": "Structural slab work Floor 10",
     "department": "Civil", "assigned_hod": "u3", "assigned_users": ["u6"],
     "start_date": "2025-04-01", "end_date": "2025-06-01",
     "priority": "high", "status": "not_started", "dependencies": ["task8"], "progress": 0, "delay_days": 0,
     "critical_path": True, "project_id": "p1", "tower_id": "t1", "floor_id": "f4", "phase": "Structure",
     "checklist": [], "checklist_completed": [], "comments": []},
    {"id": "task14", "title": "Interior Plastering - Floor 1", "description": "Internal wall plastering Floor 1",
     "department": "Finishing", "assigned_hod": "u9", "assigned_users": ["u12"],
     "start_date": "2025-02-01", "end_date": "2025-03-30",
     "priority": "medium", "status": "in_progress", "dependencies": ["task6", "task7"], "progress": 55, "delay_days": 0,
     "critical_path": False, "project_id": "p1", "tower_id": "t1", "floor_id": "f1", "phase": "Finishing",
     "checklist": ["Wall preparation", "First coat", "Second coat", "Curing"],
     "checklist_completed": [True, True, False, False], "comments": []},
    {"id": "task15", "title": "Fire Safety Installation - Floor 1", "description": "Fire alarm and sprinkler system",
     "department": "Fire Safety", "assigned_hod": "u10", "assigned_users": ["u7"],
     "start_date": "2025-03-01", "end_date": "2025-05-15",
     "priority": "high", "status": "ready", "dependencies": ["task6"], "progress": 0, "delay_days": 0,
     "critical_path": False, "project_id": "p1", "tower_id": "t1", "floor_id": "f1", "phase": "MEP",
     "checklist": ["Sprinkler layout approved", "Pipe installation", "Alarm system installed", "Testing completed"],
     "checklist_completed": [False, False, False, False], "comments": []},
    {"id": "task16", "title": "Foundation Work - Tower B", "description": "Complete foundation for Tower B",
     "department": "Civil", "assigned_hod": "u3", "assigned_users": ["u6"],
     "start_date": "2024-04-01", "end_date": "2024-08-30", "actual_start_date": "2024-04-10", "actual_end_date": "2024-09-10",
     "priority": "critical", "status": "completed", "dependencies": [], "progress": 100, "delay_days": 10,
     "delay_reason": "Rock bed encountered during excavation", "critical_path": True, "project_id": "p1", "tower_id": "t2", "floor_id": "f6", "phase": "Foundation",
     "checklist": [], "checklist_completed": [], "comments": []},
    {"id": "task17", "title": "Structural Work - Tower B F1-F2", "description": "Structural columns and slabs",
     "department": "Civil", "assigned_hod": "u3", "assigned_users": ["u6"],
     "start_date": "2024-09-15", "end_date": "2025-01-30", "actual_start_date": "2024-09-20",
     "priority": "high", "status": "in_progress", "dependencies": ["task16"], "progress": 78, "delay_days": 5,
     "delay_reason": "Labour shortage during Diwali", "critical_path": True, "project_id": "p1", "tower_id": "t2", "floor_id": "f6", "phase": "Structure",
     "checklist": [], "checklist_completed": [], "comments": []},
    {"id": "task18", "title": "MEP Rough-in - Tower B F1", "description": "All MEP rough-in work for Tower B Floor 1",
     "department": "MEP", "assigned_hod": "u5", "assigned_users": ["u8", "u7"],
     "start_date": "2025-01-01", "end_date": "2025-03-30",
     "priority": "medium", "status": "blocked", "dependencies": ["task17"], "progress": 15, "delay_days": 12,
     "delay_reason": "Waiting for structural completion", "critical_path": False, "project_id": "p1", "tower_id": "t2", "floor_id": "f6", "phase": "MEP",
     "checklist": [], "checklist_completed": [],
     "comments": [{"user": "Vikram Singh", "text": "Blocked due to structural work delay", "date": "2025-02-15"}]},
    {"id": "task19", "title": "Foundation - Skyline Tower A", "description": "Foundation excavation and RCC",
     "department": "Civil", "assigned_hod": "u3", "assigned_users": ["u6"],
     "start_date": "2024-07-01", "end_date": "2024-12-31", "actual_start_date": "2024-07-10", "actual_end_date": "2025-01-15",
     "priority": "critical", "status": "completed", "dependencies": [], "progress": 100, "delay_days": 15,
     "delay_reason": "Heavy monsoon", "critical_path": True, "project_id": "p2", "tower_id": "t3", "floor_id": "f11", "phase": "Foundation",
     "checklist": [], "checklist_completed": [], "comments": []},
    {"id": "task20", "title": "Structural - Skyline Tower A", "description": "Structural work up to Floor 5",
     "department": "Civil", "assigned_hod": "u3", "assigned_users": ["u6"],
     "start_date": "2025-01-20", "end_date": "2025-08-30",
     "priority": "critical", "status": "in_progress", "dependencies": ["task19"], "progress": 35, "delay_days": 0,
     "critical_path": True, "project_id": "p2", "tower_id": "t3", "floor_id": "f12", "phase": "Structure",
     "checklist": [], "checklist_completed": [], "comments": []},
    {"id": "task21", "title": "Foundation - Skyline Tower B", "description": "Foundation for Tower B",
     "department": "Civil", "assigned_hod": "u3", "assigned_users": ["u6"],
     "start_date": "2024-09-01", "end_date": "2025-02-28",
     "priority": "high", "status": "in_progress", "dependencies": [], "progress": 82, "delay_days": 0,
     "critical_path": True, "project_id": "p2", "tower_id": "t4", "floor_id": "f14", "phase": "Foundation",
     "checklist": [], "checklist_completed": [], "comments": []},
    {"id": "task22", "title": "RERA Registration - Palm Gardens", "description": "Complete RERA registration process",
     "department": "Legal", "assigned_hod": "u2", "assigned_users": ["u2"],
     "start_date": "2025-01-15", "end_date": "2025-03-31",
     "priority": "critical", "status": "in_progress", "dependencies": [], "progress": 60, "delay_days": 0,
     "critical_path": True, "project_id": "p3", "tower_id": "t6", "floor_id": "f19", "phase": "Pre-Construction",
     "checklist": ["Documentation prepared", "Application submitted", "Fees paid", "Certificate received"],
     "checklist_completed": [True, True, True, False], "comments": []},
    {"id": "task23", "title": "Soil Testing - Palm Gardens", "description": "Geotechnical soil investigation",
     "department": "Civil", "assigned_hod": "u3", "assigned_users": ["u6"],
     "start_date": "2025-02-01", "end_date": "2025-03-15",
     "priority": "high", "status": "review", "dependencies": [], "progress": 90, "delay_days": 0,
     "critical_path": False, "project_id": "p3", "tower_id": "t6", "floor_id": "f19", "phase": "Pre-Construction",
     "checklist": ["Bore holes completed", "Lab testing done", "Report generated"],
     "checklist_completed": [True, True, False], "comments": []},
    {"id": "task24", "title": "Lift Shaft Construction - Tower A", "description": "Lift shaft construction Floors 1-12",
     "department": "Civil", "assigned_hod": "u3", "assigned_users": ["u6"],
     "start_date": "2024-10-01", "end_date": "2025-02-28",
     "priority": "critical", "status": "delayed", "dependencies": ["task4"], "progress": 45, "delay_days": 18,
     "delay_reason": "Formwork material delay from supplier", "critical_path": True, "project_id": "p1", "tower_id": "t1", "floor_id": "f1", "phase": "Structure",
     "checklist": [], "checklist_completed": [],
     "comments": [{"user": "Amit Patel", "text": "Escalated to vendor management", "date": "2025-02-20"}]},
    {"id": "task25", "title": "External Plastering - Tower A", "description": "External wall plastering Floors 1-5",
     "department": "Finishing", "assigned_hod": "u9", "assigned_users": ["u12"],
     "start_date": "2025-02-15", "end_date": "2025-05-30",
     "priority": "medium", "status": "delayed", "dependencies": ["task8"], "progress": 10, "delay_days": 8,
     "delay_reason": "Scaffolding availability", "critical_path": False, "project_id": "p1", "tower_id": "t1", "floor_id": "f3", "phase": "Finishing",
     "checklist": [], "checklist_completed": [], "comments": []},
]

HURDLES = [
    {"id": "h1", "title": "Cement Shortage", "description": "OPC 53 grade cement supply disrupted due to factory shutdown",
     "type": "material_delay", "affected_task_id": "task8", "affected_tower": "Tower A", "responsible_department": "Civil",
     "impact_days": 7, "severity": "high", "status": "in_progress", "project_id": "p1", "reported_date": "2025-02-28"},
    {"id": "h2", "title": "Electrical Panel Delivery Delayed", "description": "Main distribution board delayed by manufacturer",
     "type": "vendor_delay", "affected_task_id": "task9", "affected_tower": "Tower A", "responsible_department": "Electrical",
     "impact_days": 14, "severity": "critical", "status": "escalated", "project_id": "p1", "reported_date": "2025-02-15"},
    {"id": "h3", "title": "Labour Strike", "description": "Partial work stoppage by masonry workers demanding pay revision",
     "type": "labour_shortage", "affected_task_id": "task14", "affected_tower": "Tower A", "responsible_department": "Finishing",
     "impact_days": 5, "severity": "high", "status": "resolved", "resolution_notes": "Negotiated 8% pay increase",
     "project_id": "p1", "reported_date": "2025-02-10", "resolved_date": "2025-02-18"},
    {"id": "h4", "title": "Fire NOC Approval Pending", "description": "Fire department approval for Tower A design pending since 3 weeks",
     "type": "approval_pending", "affected_task_id": "task15", "affected_tower": "Tower A", "responsible_department": "Fire Safety",
     "impact_days": 21, "severity": "critical", "status": "open", "project_id": "p1", "reported_date": "2025-02-01"},
    {"id": "h5", "title": "Design Revision - Lobby Area", "description": "Architect requested design change for ground floor lobby",
     "type": "design_change", "affected_task_id": "task14", "affected_tower": "Tower A", "responsible_department": "Finishing",
     "impact_days": 10, "severity": "medium", "status": "in_progress", "project_id": "p1", "reported_date": "2025-03-01"},
    {"id": "h6", "title": "Crane Breakdown", "description": "Tower crane hydraulic system failure, needs replacement parts",
     "type": "equipment_failure", "affected_task_id": "task17", "affected_tower": "Tower B", "responsible_department": "Civil",
     "impact_days": 4, "severity": "high", "status": "resolved", "resolution_notes": "Spare parts sourced from alternate vendor",
     "project_id": "p1", "reported_date": "2025-01-20", "resolved_date": "2025-01-25"},
    {"id": "h7", "title": "Heavy Rainfall Warning", "description": "IMD yellow alert for next 5 days, external work suspended",
     "type": "weather_delay", "affected_task_id": "task20", "affected_tower": "Tower A", "responsible_department": "Civil",
     "impact_days": 5, "severity": "medium", "status": "open", "project_id": "p2", "reported_date": "2025-03-08"},
    {"id": "h8", "title": "Formwork Material Delay", "description": "Aluminum formwork panels stuck in transit",
     "type": "material_delay", "affected_task_id": "task24", "affected_tower": "Tower A", "responsible_department": "Civil",
     "impact_days": 18, "severity": "critical", "status": "escalated", "project_id": "p1", "reported_date": "2025-01-15"},
    {"id": "h9", "title": "Plumber Shortage", "description": "Insufficient skilled plumbers for parallel floor work",
     "type": "labour_shortage", "affected_task_id": "task10", "affected_tower": "Tower A", "responsible_department": "Plumbing",
     "impact_days": 3, "severity": "low", "status": "resolved", "resolution_notes": "Hired 5 additional plumbers from subcontractor",
     "project_id": "p1", "reported_date": "2025-02-20", "resolved_date": "2025-02-24"},
    {"id": "h10", "title": "Soil Contamination Found", "description": "Chemical contamination detected in bore sample #3",
     "type": "design_change", "affected_task_id": "task23", "affected_tower": "Tower A", "responsible_department": "Civil",
     "impact_days": 15, "severity": "high", "status": "in_progress", "project_id": "p3", "reported_date": "2025-03-01"},
]

CHECKLIST_TEMPLATES = [
    {"name": "Foundation Excavation", "category": "Foundation", "items": ["Site survey completed", "Soil testing report reviewed", "Excavation plan approved", "Safety barriers installed", "Dewatering system ready", "Level marking done", "Excavation depth verified", "Soil disposal arranged"]},
    {"name": "RCC Foundation", "category": "Foundation", "items": ["PCC laid and cured", "Rebar placement per drawing", "Cover blocks placed", "Formwork aligned", "Concrete mix design approved", "Slump test done", "Concrete pouring completed", "Curing schedule initiated"]},
    {"name": "Column Casting", "category": "Structure", "items": ["Column layout marked", "Starter bars checked", "Rebar tied per schedule", "Formwork erected", "Verticality checked", "Concrete poured", "Vibration done", "De-shuttering after curing"]},
    {"name": "Slab Casting", "category": "Structure", "items": ["Shuttering erected", "Slab rebar placed", "Electrical conduits embedded", "Plumbing sleeves placed", "Pre-pour inspection done", "Concrete poured", "Curing started", "De-shuttering after 14 days"]},
    {"name": "Electrical Installation", "category": "MEP", "items": ["Material delivered", "Layout marking completed", "Conduit installed", "Wiring completed", "Switch boards fixed", "Earthing done", "Inspection completed", "Photos uploaded", "QA approved"]},
    {"name": "Plumbing Installation", "category": "MEP", "items": ["Material delivered", "Layout per drawing", "Pipe installation done", "Joints sealed", "Pressure test completed", "Leak test passed", "Insulation applied", "Final inspection done"]},
    {"name": "Waterproofing", "category": "MEP", "items": ["Surface cleaned and prepared", "Primer coat applied", "Membrane laid", "Seams sealed", "Ponding test - 48 hours", "No leaks confirmed", "Protection screed applied", "Photos documented"]},
    {"name": "Fire Safety System", "category": "Fire Safety", "items": ["Fire riser installed", "Sprinkler layout approved", "Sprinkler pipes installed", "Alarm system installed", "Smoke detectors placed", "Hydrant system ready", "Pressure test done", "Fire department inspection", "NOC obtained"]},
    {"name": "Lift Installation", "category": "MEP", "items": ["Lift shaft dimensions verified", "Guide rails installed", "Machine room prepared", "Control panel installed", "Cabin assembled", "Safety switches tested", "Load test completed", "Lift certification received"]},
    {"name": "Internal Plastering", "category": "Finishing", "items": ["Wall surface prepared", "Plumb line checked", "Chicken mesh at junctions", "First coat applied", "Curing done", "Second coat applied", "Surface finish verified", "Thickness checked"]},
    {"name": "Painting", "category": "Finishing", "items": ["Surface sanded", "Primer coat applied", "Putty applied", "Sanding after putty", "First paint coat", "Second paint coat", "Touch-up done", "Final inspection"]},
    {"name": "Tiling", "category": "Finishing", "items": ["Surface leveled", "Layout pattern approved", "Adhesive applied", "Tiles laid", "Spacing verified", "Grouting done", "Cleaning completed", "Edge finishing done"]},
    {"name": "RERA Registration", "category": "Legal", "items": ["Project documents compiled", "Land title verified", "Architect certificate obtained", "Engineer certificate obtained", "CA certificate obtained", "Application form filled", "Fees paid", "Registration number received"]},
    {"name": "Occupancy Certificate", "category": "Legal", "items": ["Building completion certificate", "Fire NOC obtained", "Lift certification done", "Water supply connection", "Sewage connection", "Electrical supply certificate", "Structural stability certificate", "OC application submitted", "OC received"]},
    {"name": "Customer Handover", "category": "Handover", "items": ["Final cleaning done", "Snagging list cleared", "All keys handed", "Meter readings recorded", "Welcome kit provided", "Parking allotment done", "Documentation handed", "Customer signed off"]},
    {"name": "Society Formation", "category": "Society", "items": ["Conveyance deed prepared", "Society registration application", "First AGM conducted", "Committee elected", "Bank account opened", "Common area handed over", "Maintenance agreement signed", "Developer responsibilities transferred"]},
    {"name": "External Plastering", "category": "Finishing", "items": ["Scaffolding erected", "Wall cleaned", "Chicken mesh applied", "First coat plaster", "Curing", "Second coat", "Texture finish", "Scaffolding removed"]},
    {"name": "Window Installation", "category": "Finishing", "items": ["Frame dimensions verified", "Frames received and inspected", "Frame fixing done", "Glass panels installed", "Sealant applied", "Hardware fitted", "Water test done", "Cleaning done"]},
    {"name": "Snagging Checklist", "category": "Handover", "items": ["Paint defects checked", "Tile alignment verified", "Plumbing leaks checked", "Electrical points tested", "Door/window operation verified", "Waterproofing verified", "Flooring level checked", "All fixtures working"]},
    {"name": "Site Mobilization", "category": "Foundation", "items": ["Site office setup", "Labour camp ready", "Material storage area", "Water supply arranged", "Power supply connected", "Safety equipment procured", "First aid station", "Site signage installed"]},
]

RESOURCES = [
    {"task_id": "task4", "labour": 25, "vendor": "ABC Contractors",
     "machines": [{"name": "Concrete Pump", "qty": 2}, {"name": "Vibrator", "qty": 4}],
     "materials": [{"name": "Cement", "qty": 100, "unit": "bags"}, {"name": "Steel", "qty": 5, "unit": "tons"}, {"name": "Sand", "qty": 20, "unit": "cum"}]},
    {"task_id": "task8", "labour": 30, "vendor": "ABC Contractors",
     "machines": [{"name": "Concrete Pump", "qty": 2}, {"name": "Tower Crane", "qty": 1}],
     "materials": [{"name": "Cement", "qty": 150, "unit": "bags"}, {"name": "Steel", "qty": 8, "unit": "tons"}]},
    {"task_id": "task10", "labour": 6, "vendor": "Jain Plumbing", "machines": [],
     "materials": [{"name": "CPVC Pipes", "qty": 200, "unit": "meters"}, {"name": "Fittings", "qty": 50, "unit": "pieces"}]},
    {"task_id": "task14", "labour": 15, "vendor": "", "machines": [{"name": "Mixer", "qty": 2}],
     "materials": [{"name": "Cement", "qty": 60, "unit": "bags"}, {"name": "Sand", "qty": 15, "unit": "cum"}]},
]

# ---- Per-page localStorage seeds (Compliance.tsx / Handover.tsx / Society.tsx / Admin.tsx) ----

COMPLIANCE_ITEMS = [
    {"name": "RERA Registration", "project": "Marine Heights", "status": "completed", "progress": 100, "due_date": "2024-03-15"},
    {"name": "RERA Registration", "project": "Skyline Residences", "status": "completed", "progress": 100, "due_date": "2024-08-20"},
    {"name": "RERA Registration", "project": "Palm Gardens", "status": "in_progress", "progress": 60, "due_date": "2025-03-31"},
    {"name": "Environmental Clearance", "project": "Marine Heights", "status": "completed", "progress": 100, "due_date": "2024-01-10"},
    {"name": "Environmental Clearance", "project": "Skyline Residences", "status": "completed", "progress": 100, "due_date": "2024-05-20"},
    {"name": "Fire NOC - Tower A", "project": "Marine Heights", "status": "pending", "progress": 30, "due_date": "2025-06-30"},
    {"name": "Fire NOC - Tower B", "project": "Marine Heights", "status": "not_started", "progress": 0, "due_date": "2025-12-31"},
    {"name": "Lift Certification", "project": "Marine Heights", "status": "not_started", "progress": 0, "due_date": "2026-03-31"},
    {"name": "Occupancy Certificate", "project": "Marine Heights", "status": "not_started", "progress": 0, "due_date": "2026-12-31"},
    {"name": "Building Completion Certificate", "project": "Marine Heights", "status": "not_started", "progress": 0, "due_date": "2026-10-31"},
]

HANDOVER_UNITS = [
    {"unit": "Unit 101", "tower": "Tower A", "project": "Marine Heights", "status": "snagging", "progress": 70, "buyer": "Mr. Anil Kapoor"},
    {"unit": "Unit 102", "tower": "Tower A", "project": "Marine Heights", "status": "inspection", "progress": 50, "buyer": "Mrs. Priya Shah"},
    {"unit": "Unit 103", "tower": "Tower A", "project": "Marine Heights", "status": "not_ready", "progress": 30, "buyer": "Mr. Rakesh Jain"},
    {"unit": "Unit 104", "tower": "Tower A", "project": "Marine Heights", "status": "not_ready", "progress": 15, "buyer": "Mrs. Sunita Mehta"},
    {"unit": "Unit 201", "tower": "Tower A", "project": "Marine Heights", "status": "handed_over", "progress": 100, "buyer": "Mr. Vijay Kumar"},
    {"unit": "Unit 202", "tower": "Tower A", "project": "Marine Heights", "status": "handed_over", "progress": 100, "buyer": "Dr. Anita Rao"},
]

SOCIETIES = [
    {"name": "Marine Heights Co-op Society", "project": "Marine Heights", "status": "in_formation", "progress": 35,
     "steps": [
         {"name": "Conveyance Deed Preparation", "completed": True},
         {"name": "Society Registration Application", "completed": False},
         {"name": "First AGM", "completed": False},
         {"name": "Committee Election", "completed": False},
         {"name": "Bank Account Opening", "completed": False},
         {"name": "Common Area Handover", "completed": False},
         {"name": "Maintenance Agreement", "completed": False},
     ]},
]

ESCALATION_RULES = [
    {"level": 1, "role": "Site Engineer", "days": 1, "description": "First notification to assigned engineer"},
    {"level": 2, "role": "Project Manager", "days": 2, "description": "Escalate if unresolved after 2 days"},
    {"level": 3, "role": "HOD", "days": 3, "description": "Department head notification"},
    {"level": 4, "role": "Project Director", "days": 5, "description": "Director-level escalation"},
    {"level": 5, "role": "CEO", "days": 7, "description": "CEO escalation for critical issues"},
]


class Command(BaseCommand):
    help = "Seeds the database with the FE-RealEstate-Tracker demo dataset (idempotent)."

    @transaction.atomic
    def handle(self, *args, **options):
        users = self._seed_users()
        projects = self._seed_projects()
        towers = self._seed_towers(projects)
        floors = self._seed_floors(towers)
        units = self._seed_units(floors)
        tasks = self._seed_tasks(users, projects, towers, floors, units)
        self._seed_hurdles(tasks, projects)
        templates = self._seed_checklist_templates()
        self._seed_resources(tasks)
        self._seed_compliance(projects)
        self._seed_handover(projects)
        self._seed_society(projects)
        self._seed_escalation_rules()

        self.stdout.write(self.style.SUCCESS("\nDemo data seeded successfully."))
        self.stdout.write(f"  {len(users)} users, {len(projects)} projects, {len(tasks)} tasks, "
                           f"{len(HURDLES)} hurdles, {len(templates)} checklist templates.")
        self.stdout.write(self.style.WARNING(f"  All demo users share the password: {DEMO_PASSWORD}"))
        self.stdout.write("  e.g. username 'rajesh' (CEO), 'amit' (Civil HOD), 'deepak' (Site Engineer)")

    # -- users -----------------------------------------------------------
    def _seed_users(self):
        by_old_id = {}
        for u in USERS:
            username = u["email"].split("@")[0]
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "name": u["name"], "email": u["email"], "role": u["role"], "department": u["department"],
                },
            )
            if created:
                user.set_password(DEMO_PASSWORD)
                user.save()
            by_old_id[u["id"]] = user
        return by_old_id

    # -- projects / towers / floors / units -------------------------------
    def _seed_projects(self):
        by_old_id = {}
        for p in PROJECTS:
            project, _ = Project.objects.update_or_create(
                name=p["name"],
                defaults={
                    "location": p["location"], "status": p["status"], "start_date": p["start_date"],
                    "end_date": p["end_date"], "progress": p["progress"], "total_units": p["total_units"],
                    "rera_number": p["rera_number"], "budget": p["budget"], "spent": p["spent"],
                },
            )
            by_old_id[p["id"]] = project
        return by_old_id

    def _seed_towers(self, projects):
        by_old_id = {}
        for t in TOWERS:
            project = projects[t["project_id"]]
            tower, _ = Tower.objects.update_or_create(
                project=project, name=t["name"], total_floors=t["total_floors"],
                defaults={"progress": t["progress"], "status": t["status"]},
            )
            by_old_id[t["id"]] = tower
        return by_old_id

    def _seed_floors(self, towers):
        by_old_id = {}
        for f in FLOORS:
            tower = towers[f["tower_id"]]
            floor, _ = Floor.objects.update_or_create(
                tower=tower, number=f["number"],
                defaults={"name": f["name"], "project": tower.project},
            )
            by_old_id[f["id"]] = floor
        return by_old_id

    def _seed_units(self, floors):
        by_old_id = {}
        i = 0
        for f in FLOORS:
            floor = floors[f["id"]]
            for old_unit_id in f["units"]:
                idx = int(old_unit_id.replace("un", "")) - 1
                type_idx = idx % 4
                unit, _ = Unit.objects.update_or_create(
                    floor=floor, name=f"Unit {f['number'] * 100 + (idx % 4) + 1}",
                    defaults={"tower": floor.tower, "project": floor.project,
                              "type": UNIT_TYPES[type_idx], "area": UNIT_AREAS[type_idx]},
                )
                by_old_id[old_unit_id] = unit
                i += 1
        return by_old_id

    # -- tasks -------------------------------------------------------------
    def _seed_tasks(self, users, projects, towers, floors, units):
        by_old_id = {}
        for t in TASKS:
            task, _ = Task.objects.update_or_create(
                title=t["title"], project=projects[t["project_id"]],
                defaults={
                    "description": t["description"], "department": t["department"],
                    "assigned_hod": users.get(t.get("assigned_hod")),
                    "start_date": t.get("start_date"), "end_date": t.get("end_date"),
                    "actual_start_date": t.get("actual_start_date"), "actual_end_date": t.get("actual_end_date"),
                    "priority": t["priority"], "status": t["status"], "progress": t["progress"],
                    "delay_days": t["delay_days"], "delay_reason": t.get("delay_reason", ""),
                    "critical_path": t["critical_path"], "tower": towers.get(t.get("tower_id")),
                    "floor": floors.get(t.get("floor_id")), "unit": units.get(t.get("unit_id")),
                    "phase": t["phase"],
                },
            )
            task.assigned_users.set([users[uid] for uid in t["assigned_users"] if uid in users])

            task.checklist_items.all().delete()
            TaskChecklistItem.objects.bulk_create([
                TaskChecklistItem(task=task, title=title, completed=done, order=i)
                for i, (title, done) in enumerate(zip(t["checklist"], t["checklist_completed"]))
            ])

            task.comments.all().delete()
            for c in t["comments"]:
                author = next((u for u in users.values() if u.name == c["user"]), None)
                comment = TaskComment.objects.create(task=task, author=author, text=c["text"])
                TaskComment.objects.filter(pk=comment.pk).update(date=c["date"])

            by_old_id[t["id"]] = task

        # second pass: dependencies (all tasks now exist)
        for t in TASKS:
            task = by_old_id[t["id"]]
            task.dependencies.set([by_old_id[dep_id] for dep_id in t["dependencies"]])

        return by_old_id

    # -- hurdles -------------------------------------------------------------
    def _seed_hurdles(self, tasks, projects):
        for h in HURDLES:
            Hurdle.objects.update_or_create(
                title=h["title"], project=projects[h["project_id"]],
                defaults={
                    "description": h["description"], "type": h["type"],
                    "affected_task": tasks.get(h.get("affected_task_id")),
                    "affected_tower": h["affected_tower"], "responsible_department": h["responsible_department"],
                    "impact_days": h["impact_days"], "severity": h["severity"], "status": h["status"],
                    "resolution_notes": h.get("resolution_notes", ""), "resolved_date": h.get("resolved_date"),
                },
            )
            Hurdle.objects.filter(title=h["title"], project=projects[h["project_id"]]).update(
                reported_date=h["reported_date"]
            )

    # -- checklist templates -------------------------------------------------
    def _seed_checklist_templates(self):
        created = []
        for ct in CHECKLIST_TEMPLATES:
            template, _ = ChecklistTemplate.objects.update_or_create(
                name=ct["name"], category=ct["category"]
            )
            template.items.all().delete()
            ChecklistTemplateItem.objects.bulk_create([
                ChecklistTemplateItem(template=template, text=text, order=i)
                for i, text in enumerate(ct["items"])
            ])
            created.append(template)
        return created

    # -- resources -------------------------------------------------------------
    def _seed_resources(self, tasks):
        for r in RESOURCES:
            task = tasks.get(r["task_id"])
            if not task:
                continue
            resource, _ = Resource.objects.update_or_create(
                task=task, defaults={"labour": r["labour"], "vendor": r["vendor"]}
            )
            resource.machines.all().delete()
            resource.materials.all().delete()
            ResourceMachine.objects.bulk_create([
                ResourceMachine(resource=resource, name=m["name"], qty=m["qty"]) for m in r["machines"]
            ])
            ResourceMaterial.objects.bulk_create([
                ResourceMaterial(resource=resource, name=m["name"], qty=m["qty"], unit=m["unit"])
                for m in r["materials"]
            ])

    # -- compliance / handover / society / escalation -----------------------
    def _seed_compliance(self, projects):
        by_name = {p["name"]: projects[p["id"]] for p in PROJECTS}
        for c in COMPLIANCE_ITEMS:
            ComplianceItem.objects.update_or_create(
                name=c["name"], project=by_name[c["project"]],
                defaults={"status": c["status"], "progress": c["progress"], "due_date": c["due_date"]},
            )

    def _seed_handover(self, projects):
        by_name = {p["name"]: projects[p["id"]] for p in PROJECTS}
        for h in HANDOVER_UNITS:
            HandoverUnit.objects.update_or_create(
                unit=h["unit"], project=by_name[h["project"]],
                defaults={"tower": h["tower"], "status": h["status"], "progress": h["progress"], "buyer": h["buyer"]},
            )

    def _seed_society(self, projects):
        by_name = {p["name"]: projects[p["id"]] for p in PROJECTS}
        for s in SOCIETIES:
            society, _ = Society.objects.update_or_create(
                name=s["name"], project=by_name[s["project"]],
                defaults={"status": s["status"], "progress": s["progress"]},
            )
            society.steps.all().delete()
            SocietyStep.objects.bulk_create([
                SocietyStep(society=society, name=step["name"], completed=step["completed"], order=i)
                for i, step in enumerate(s["steps"])
            ])
            society.recalculate_progress()

    def _seed_escalation_rules(self):
        for r in ESCALATION_RULES:
            EscalationRule.objects.update_or_create(
                level=r["level"], defaults={"role": r["role"], "days": r["days"], "description": r["description"]}
            )

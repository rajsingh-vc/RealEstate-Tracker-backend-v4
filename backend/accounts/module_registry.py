"""
Central Module Registry, Access Policy Evaluation, and Audit Logging
for Konstruct Tracker.

Ensures fully configurable, database-backed module visibility and access
control across Super Admins, Site Admins, and standard users.
"""
from typing import Any, Dict, List, Optional
from django.db import models


DEFAULT_MODULES = [
    {
        "key": "dashboard",
        "name": "Dashboard",
        "description": "Portfolio and executive progress overview",
        "category": "Main",
        "route": "/",
        "icon": "LayoutDashboard",
        "order": 10,
        "default_enabled": True,
        "default_visible": True,
        "admin_only": False,
    },
    {
        "key": "projects",
        "name": "Projects",
        "description": "Project portfolio, towers, floors, and units",
        "category": "Main",
        "route": "/projects",
        "icon": "Building2",
        "order": 20,
        "default_enabled": True,
        "default_visible": True,
        "admin_only": False,
    },
    {
        "key": "digital-twin",
        "name": "Digital Twin",
        "description": "Interactive 3D building visualizer and spatial status",
        "category": "Main",
        "route": "/digital-twin",
        "icon": "Map",
        "order": 30,
        "default_enabled": True,
        "default_visible": True,
        "admin_only": False,
    },
    {
        "key": "tasks",
        "name": "Tasks",
        "description": "Activity tracking, task assignments, and progress updates",
        "category": "Main",
        "route": "/tasks",
        "icon": "ListChecks",
        "order": 40,
        "default_enabled": True,
        "default_visible": True,
        "admin_only": False,
    },
    {
        "key": "timeline",
        "name": "Timeline",
        "description": "Gantt schedules, milestones, and project baselines",
        "category": "Main",
        "route": "/timeline",
        "icon": "CalendarRange",
        "order": 50,
        "default_enabled": True,
        "default_visible": True,
        "admin_only": False,
    },
    {
        "key": "hurdles",
        "name": "Hurdle Tracker",
        "description": "Site impediments, bottlenecks, and issue resolutions",
        "category": "Operations",
        "route": "/hurdles",
        "icon": "AlertTriangle",
        "order": 60,
        "default_enabled": True,
        "default_visible": True,
        "admin_only": False,
    },
    {
        "key": "resources",
        "name": "Resources",
        "description": "Labor, materials, machinery allocation, and site utilization",
        "category": "Operations",
        "route": "/resources",
        "icon": "Package",
        "order": 70,
        "default_enabled": True,
        "default_visible": True,
        "admin_only": False,
    },
    {
        "key": "checklists",
        "name": "Checklists",
        "description": "Quality assurance checklists and site inspections",
        "category": "Operations",
        "route": "/checklists",
        "icon": "ClipboardList",
        "order": 80,
        "default_enabled": True,
        "default_visible": True,
        "admin_only": False,
    },
    {
        "key": "category-management",
        "name": "Category Management",
        "description": "Project structural hierarchy, categories, and stages",
        "category": "Operations",
        "route": "/category-management",
        "icon": "Tags",
        "order": 90,
        "default_enabled": True,
        "default_visible": True,
        "admin_only": True,
    },
    {
        "key": "compliance",
        "name": "Compliance",
        "description": "Regulatory permits, approvals, and legal certifications",
        "category": "Management",
        "route": "/compliance",
        "icon": "ShieldCheck",
        "order": 100,
        "default_enabled": True,
        "default_visible": True,
        "admin_only": False,
    },
    {
        "key": "handover",
        "name": "Handover",
        "description": "Unit snag lists, buyer handovers, and transition packages",
        "category": "Management",
        "route": "/handover",
        "icon": "HandshakeIcon",
        "order": 110,
        "default_enabled": True,
        "default_visible": True,
        "admin_only": False,
    },
    {
        "key": "documents",
        "name": "Documents",
        "description": "Site drawings, architectural plans, and files repository",
        "category": "Management",
        "route": "/documents",
        "icon": "FileText",
        "order": 120,
        "default_enabled": True,
        "default_visible": True,
        "admin_only": False,
    },
    {
        "key": "reports",
        "name": "Reports",
        "description": "Project executive analytics, KPIs, and exportable reports",
        "category": "Management",
        "route": "/reports",
        "icon": "BarChart3",
        "order": 130,
        "default_enabled": True,
        "default_visible": True,
        "admin_only": False,
    },
    {
        "key": "delay-prediction",
        "name": "Delay Prediction",
        "description": "AI-driven forecasting and risk delay analysis",
        "category": "System",
        "route": "/delay-prediction",
        "icon": "TrendingUp",
        "order": 140,
        "default_enabled": True,
        "default_visible": True,
        "admin_only": False,
    },
    {
        "key": "ai-assistant",
        "name": "AI Assistant",
        "description": "Document analysis and intelligent project copilot",
        "category": "System",
        "route": "/ai-assistant",
        "icon": "Bot",
        "order": 150,
        "default_enabled": True,
        "default_visible": True,
        "admin_only": True,
    },
    {
        "key": "admin",
        "name": "Admin",
        "description": "User administration, roles, tenant settings, and module visibility",
        "category": "System",
        "route": "/admin",
        "icon": "Settings",
        "order": 160,
        "default_enabled": True,
        "default_visible": True,
        "admin_only": True,
    },
]


def sync_default_modules():
    """
    Idempotently seeds / updates AppModule records from DEFAULT_MODULES.
    Preserves existing admin overrides on is_active / default flags.
    """
    from .models import AppModule
    for data in DEFAULT_MODULES:
        mod, created = AppModule.objects.get_or_create(
            key=data["key"],
            defaults={
                "name": data["name"],
                "description": data["description"],
                "category": data["category"],
                "route": data["route"],
                "icon": data["icon"],
                "order": data["order"],
                "default_enabled": data["default_enabled"],
                "default_visible": data["default_visible"],
                "admin_only": data["admin_only"],
                "is_active": True,
            }
        )
        if not created and mod.key == "dashboard" and mod.name != data["name"]:
            mod.name = data["name"]
            mod.save(update_fields=["name"])


def get_user_effective_modules(user, project_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Computes the effective access and visibility permissions for each module
    for a given user, optionally scoped to a project.
    
    Resolution order:
      1. Global Module active switch (if False, module is disabled for non-superusers).
      2. SuperAdmin always has full access and visibility.
      3. UserModulePermission override (project-specific first, then project=None).
         - if is_enabled is not None -> takes precedence.
         - if is_visible is not None -> takes precedence.
      4. RoleModulePermission policy (for user.role and user.company / global).
         - if is_enabled defined -> applies.
         - if is_visible defined -> applies.
      5. AppModule default_enabled / default_visible:
         - if admin_only: enabled only if user is an admin or superadmin.
         - otherwise: module.default_enabled / module.default_visible.
      6. Invariance: if is_enabled is False, is_visible is forced to False.
    """
    from .models import AppModule, RoleModulePermission, UserModulePermission
    from .permissions import is_admin_or_superadmin

    sync_default_modules()
    all_modules = list(AppModule.objects.all().order_by("order", "name"))

    if not user or not user.is_authenticated:
        return [
            {
                "key": m.key,
                "name": m.name,
                "category": m.category,
                "route": m.route,
                "icon": m.icon,
                "order": m.order,
                "is_enabled": False,
                "is_visible": False,
                "source": "unauthenticated",
            }
            for m in all_modules
        ]

    # Pre-fetch role permissions for user's role
    role_perms_by_module: Dict[int, Any] = {}
    if user.role_id:
        role_q = RoleModulePermission.objects.filter(role_id=user.role_id)
        if user.company_id:
            role_q = role_q.filter(models.Q(organization_id=user.company_id) | models.Q(organization__isnull=True))
        for rp in role_q:
            # Prefer organization-specific policy over global
            if rp.module_id not in role_perms_by_module or rp.organization_id is not None:
                role_perms_by_module[rp.module_id] = rp

    # Pre-fetch user overrides
    user_overrides_by_module: Dict[int, Any] = {}
    u_q = UserModulePermission.objects.filter(user=user)
    if project_id:
        u_q = u_q.filter(models.Q(project_id=project_id) | models.Q(project__isnull=True))
    else:
        u_q = u_q.filter(project__isnull=True)

    for uo in u_q:
        # Prefer project-specific override over global
        if uo.module_id not in user_overrides_by_module or uo.project_id is not None:
            user_overrides_by_module[uo.module_id] = uo

    user_is_admin = is_admin_or_superadmin(user)
    def resolve_module_name(m) -> str:
        if m.key == "dashboard":
            if user.is_superuser:
                return "Dashboard"
            org_name = user.company.name if (user.company and user.company.name) else (getattr(user, "company_name", None) or "")
            if org_name and org_name != "Primary Tenant":
                return f"{org_name} Dashboard"
            return "Dashboard"
        return m.name

    results = []
    for module in all_modules:
        m_name = resolve_module_name(module)

        # SuperAdmin has full access to active modules
        if user.is_superuser:
            results.append({
                "key": module.key,
                "name": m_name,
                "description": module.description,
                "category": module.category,
                "route": module.route,
                "icon": module.icon,
                "order": module.order,
                "is_active": module.is_active,
                "is_enabled": True,
                "is_visible": True,
                "source": "superadmin",
                "override_enabled": None,
                "override_visible": None,
            })
            continue

        # If module is globally disabled, non-superusers cannot access
        if not module.is_active:
            results.append({
                "key": module.key,
                "name": m_name,
                "description": module.description,
                "category": module.category,
                "route": module.route,
                "icon": module.icon,
                "order": module.order,
                "is_active": False,
                "is_enabled": False,
                "is_visible": False,
                "source": "globally_disabled",
                "override_enabled": None,
                "override_visible": None,
            })
            continue

        uo = user_overrides_by_module.get(module.id)
        rp = role_perms_by_module.get(module.id)

        effective_enabled: Optional[bool] = None
        effective_visible: Optional[bool] = None
        source = "default"

        # Check User override first
        if uo:
            if uo.is_enabled is not None:
                effective_enabled = uo.is_enabled
                source = "user_override"
            if uo.is_visible is not None:
                effective_visible = uo.is_visible
                source = "user_override"

        # Check Role policy if not determined
        if effective_enabled is None and rp is not None:
            effective_enabled = rp.is_enabled
            source = "role_policy"
        if effective_visible is None and rp is not None:
            effective_visible = rp.is_visible
            source = "role_policy"

        # Fallback to module defaults
        if effective_enabled is None:
            if module.admin_only:
                effective_enabled = user_is_admin
            else:
                effective_enabled = module.default_enabled

        if effective_visible is None:
            if module.admin_only:
                effective_visible = user_is_admin
            else:
                effective_visible = module.default_visible

        # If access is disabled, visibility must also be false
        if not effective_enabled:
            effective_visible = False

        results.append({
            "key": module.key,
            "name": m_name,
            "description": module.description,
            "category": module.category,
            "route": module.route,
            "icon": module.icon,
            "order": module.order,
            "is_active": module.is_active,
            "is_enabled": bool(effective_enabled),
            "is_visible": bool(effective_visible),
            "source": source,
            "override_enabled": uo.is_enabled if uo else None,
            "override_visible": uo.is_visible if uo else None,
        })

    return results


def is_module_enabled_for_user(user, module_key: str, project_id: Optional[int] = None) -> bool:
    """Fast check whether a module is enabled for a user."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    modules = get_user_effective_modules(user, project_id=project_id)
    for m in modules:
        if m["key"] == module_key:
            return m["is_enabled"]
    return False


def is_module_visible_for_user(user, module_key: str, project_id: Optional[int] = None) -> bool:
    """Fast check whether a module is visible in navigation for a user."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    modules = get_user_effective_modules(user, project_id=project_id)
    for m in modules:
        if m["key"] == module_key:
            return m["is_visible"]
    return False


def log_module_audit(
    actor,
    action: str,
    module_key: str = "",
    target_user=None,
    target_role=None,
    target_project=None,
    target_project_id: Optional[int] = None,
    organization=None,
    previous_value: Optional[Dict[str, Any]] = None,
    new_value: Optional[Dict[str, Any]] = None,
    details: str = "",
):
    """Records an audit log entry for module permission changes."""
    from .models import ModuleAuditLog
    try:
        project_obj = target_project
        if not project_obj and target_project_id:
            try:
                from projects.models import Project
                project_obj = Project.objects.filter(id=target_project_id).first()
            except Exception:
                project_obj = None

        ModuleAuditLog.objects.create(
            actor=actor if (actor and actor.is_authenticated) else None,
            action=action,
            module_key=module_key,
            target_user=target_user,
            target_role=target_role,
            target_project=project_obj,
            organization=organization or (actor.company if actor and getattr(actor, 'company', None) else None),
            previous_value=previous_value or {},
            new_value=new_value or {},
            details=details,
        )
    except Exception as exc:
        print(f"Warning: Failed to create ModuleAuditLog: {exc}")

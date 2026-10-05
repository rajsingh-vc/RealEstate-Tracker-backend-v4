"""
Pure Python ports of the client-side analytics logic that today lives in
src/pages/DelayPrediction.tsx, src/pages/AIAssistant.tsx and the
`departmentStats` block of src/data/demo-data.ts. Keeping the same math
server-side means the frontend can eventually delete its local copies and
just render whatever these endpoints return.
"""

from datetime import date

from django.db.models import Count, Q

from hurdles.models import Hurdle
from projects.models import Project, Tower
from tasks.models import Task


def department_stats():
    """Equivalent of the `departmentStats` array in demo-data.ts, computed live."""
    rows = (
        Task.objects.filter(project__isnull=False)
        .values("department")
        .annotate(
            completed=Count("id", filter=Q(status="completed")),
            in_progress=Count("id", filter=Q(status="in_progress")),
            delayed=Count("id", filter=Q(status__in=["delayed", "blocked"])),
            total=Count("id"),
        )
        .order_by("department")
    )
    return [
        {
            "name": row["department"],
            "completed": row["completed"],
            "inProgress": row["in_progress"],
            "delayed": row["delayed"],
            "total": row["total"],
        }
        for row in rows
    ]


def calculate_risk_score(task: Task, hurdles_by_tower) -> int:
    """Direct port of calculateRiskScore() in src/pages/DelayPrediction.tsx."""
    score = 0

    if task.delay_days > 0:
        score += min(task.delay_days * 3, 30)

    dep_ids = list(task.dependencies.values_list("id", flat=True))
    if dep_ids:
        delayed_deps = Task.objects.filter(id__in=dep_ids, status__in=["delayed", "blocked"]).count()
        score += delayed_deps * 15

    tower_hurdles = [h for h in hurdles_by_tower.get(task.tower_id, []) if h.status != "resolved"]
    score += len(tower_hurdles) * 10
    score += sum(1 for h in tower_hurdles if h.severity == "critical") * 10

    if task.start_date and task.end_date:
        total_duration = (task.end_date - task.start_date).days
        elapsed = (date.today() - task.start_date).days
        if total_duration > 0:
            expected_progress = min(100, max(0, (elapsed / total_duration) * 100))
            progress_gap = expected_progress - task.progress
            if progress_gap > 20:
                score += 20
            elif progress_gap > 10:
                score += 10

    if task.critical_path:
        score = round(score * 1.3)

    if task.status == "blocked":
        score += 25
    if task.status == "delayed":
        score += 20

    return min(100, max(0, score))


def risk_level(score: int):
    if score >= 60:
        return {"label": "High Risk", "band": "high"}
    if score >= 30:
        return {"label": "Medium Risk", "band": "medium"}
    return {"label": "Low Risk", "band": "low"}


def delay_predictions():
    """Equivalent of the `predictions` array built in DelayPrediction.tsx."""
    tasks = (
        Task.objects.filter(project__isnull=False)
        .exclude(status="completed")
        .select_related("project", "tower")
        .prefetch_related("dependencies")
    )

    hurdles_by_tower = {}
    for h in Hurdle.objects.exclude(status="resolved").select_related("affected_task"):
        if h.affected_task and h.affected_task.tower_id:
            hurdles_by_tower.setdefault(h.affected_task.tower_id, []).append(h)

    results = []
    for task in tasks:
        score = calculate_risk_score(task, hurdles_by_tower)
        results.append(
            {
                "taskId": task.id,
                "title": task.title,
                "department": task.department,
                "progress": task.progress,
                "delayDays": task.delay_days,
                "criticalPath": task.critical_path,
                "projectName": task.project.name if task.project_id else None,
                "towerName": task.tower.name if task.tower_id else None,
                "riskScore": score,
                "risk": risk_level(score),
            }
        )
    results.sort(key=lambda r: r["riskScore"], reverse=True)
    return results


def generate_ai_response(message: str) -> str:
    q = message.lower()
    projects = Project.objects.all()
    tasks = Task.objects.filter(project__isnull=False).select_related("project", "tower")
    hurdles = Hurdle.objects.all()

    if not projects.exists():
        return "There are currently no active projects in your workspace. Once you create a project, I will provide live progress metrics, risk predictions, and intelligent reporting."

    # Check if a specific existing project is mentioned
    for p in projects:
        if p.name.lower() in q:
            p_tasks = tasks.filter(project=p)
            p_delayed = p_tasks.filter(Q(status="delayed") | Q(delay_days__gt=0))
            p_completed = p_tasks.filter(status="completed").count()
            p_total = p_tasks.count()
            return (
                f"🏗️ **{p.name}**\n\n"
                f"• **Status:** {p.status}\n"
                f"• **Location:** {p.location}\n"
                f"• **Overall Completion:** {p.progress}%\n"
                f"• **Tasks:** {p_completed}/{p_total} completed\n"
                f"• **Delayed Tasks:** {p_delayed.count()} ({sum(t.delay_days for t in p_delayed)} delay days)\n"
                f"• **RERA:** {p.rera_number or 'N/A'}"
            )

    if "delayed" in q or "overdue" in q:
        delayed = list(tasks.filter(Q(status="delayed") | Q(delay_days__gt=0)))
        if not delayed:
            return "✅ **No overdue or delayed tasks** found across your active projects! Everything is currently on schedule."
        lines = [
            f"• **{t.title}** ({t.project.name}) — {t.delay_days} days delayed ({t.delay_reason or 'No reason specified'})"
            for t in delayed
        ]
        total_impact = sum(t.delay_days for t in delayed)

        by_project: dict[str, int] = {}
        for t in delayed:
            by_project[t.project.name] = by_project.get(t.project.name, 0) + 1
        top_project = max(by_project, key=by_project.get) if by_project else None

        result = (
            f"📊 **Delayed Tasks Analysis**\n\nFound {len(delayed)} tasks with delays:\n\n"
            + "\n".join(lines[:10])
            + f"\n\n**Total impact:** {total_impact} days across all active projects."
        )
        if top_project:
            result += f"\n\nThe most impacted project is **{top_project}** with {by_project[top_project]} delayed tasks."
        return result

    if "hurdle" in q:
        # Check if query mentions a specific tower from existing towers
        existing_towers = Tower.objects.filter(project__isnull=False)
        matched_tower = None
        for tow in existing_towers:
            if tow.name.lower() in q:
                matched_tower = tow
                break

        if matched_tower:
            tower_hurdles = list(hurdles.filter(affected_tower__iexact=matched_tower.name))
            if not tower_hurdles:
                return f"No open hurdles currently affecting **{matched_tower.name}**."
            lines = [
                f"• **{h.title}** — {h.severity} severity, {h.impact_days} days impact, Status: {h.status}"
                for h in tower_hurdles
            ]
            critical = sum(1 for h in tower_hurdles if h.severity == "critical")
            unresolved = sum(1 for h in tower_hurdles if h.status != "resolved")
            return (
                f"🚧 **Hurdles Affecting {matched_tower.name}**\n\nFound {len(tower_hurdles)} hurdles:\n\n"
                + "\n".join(lines)
                + f"\n\n**Critical issues:** {critical} critical, {unresolved} unresolved."
            )
        else:
            open_hurdles = list(hurdles.exclude(status="resolved"))
            if not open_hurdles:
                return "✅ No unresolved hurdles currently reported across your active projects."
            lines = [
                f"• **{h.title}** ({h.affected_tower or 'General'}) — {h.severity} severity, {h.impact_days}d impact"
                for h in open_hurdles[:8]
            ]
            return (
                f"🚧 **Active Hurdles ({len(open_hurdles)})**\n\n"
                + "\n".join(lines)
            )

    if "progress" in q or "summary" in q:
        completed = tasks.filter(status="completed").count()
        in_prog = tasks.filter(status="in_progress").count()
        lines = [f"• **{p.name}** — {p.progress}% complete ({p.status})" for p in projects]
        active_towers = Tower.objects.filter(project__isnull=False, status="Construction").count()
        return (
            "📈 **Portfolio Progress Summary**\n\n"
            + "\n".join(lines)
            + f"\n\n**Task Breakdown:**\n• Completed: {completed}/{tasks.count()}\n• In Progress: {in_prog}"
            f"\n• Blocked: {tasks.filter(status='blocked').count()}\n• Delayed: {tasks.filter(status='delayed').count()}"
            f"\n\n**Active Towers:** {active_towers} under construction."
        )

    if "predict" in q or "risk" in q:
        # Deliberately the same simple heuristic as the original AIAssistant.tsx
        # (critical-path + not-completed, then delayed-or-blocked) -- NOT the
        # more sophisticated scoring in delay_predictions() used by the
        # dedicated DelayPrediction page. These are two intentionally distinct
        # views in the original app; keeping them distinct here too.
        critical_tasks = tasks.filter(critical_path=True).exclude(status="completed")
        high_risk = [t for t in critical_tasks if t.delay_days > 0 or t.status == "blocked"]
        lines = [
            f"• **{t.title}** — {f'{t.delay_days} days behind' if t.delay_days > 0 else 'Blocked'}, {t.department}"
            for t in high_risk
        ]

        top_hurdles = list(hurdles.exclude(status="resolved").order_by("-impact_days")[:2])
        if top_hurdles:
            names = " and ".join(h.title for h in top_hurdles)
            noun = "hurdles" if len(top_hurdles) > 1 else "hurdle"
            recommendation = f"Focus on resolving the {names} {noun} to reduce cascading delays."
        else:
            recommendation = "No major unresolved hurdles detected right now."

        return (
            f"🔮 **Delay Risk Prediction**\n\n**High-risk tasks ({len(high_risk)}):**\n"
            + "\n".join(lines)
            + f"\n\n**Risk factors detected:**\n• {hurdles.exclude(status='resolved').count()} unresolved hurdles"
            f"\n• {tasks.filter(status='blocked').count()} blocked tasks"
            f"\n• Critical path tasks at risk: {len(high_risk)}"
            f"\n\n**Recommendation:** {recommendation}"
        )

    if "department" in q or "performance" in q:
        stats = department_stats()
        lines = [
            f"• **{d['name']}** — {d['completed']} completed, {d['delayed']} delayed "
            f"({round((d['completed'] / d['total']) * 100) if d['total'] else 0}% rate)"
            for d in stats
        ]
        rated = [
            {
                "name": d["name"],
                "completion_rate": (d["completed"] / d["total"]) if d["total"] else 0,
                "delay_rate": (d["delayed"] / d["total"]) if d["total"] else 0,
            }
            for d in stats
            if d["total"]
        ]
        top = max(rated, key=lambda d: d["completion_rate"], default=None)
        attention = max(rated, key=lambda d: d["delay_rate"], default=None)

        result = "🏢 **Department Performance**\n\n" + "\n".join(lines)
        if top:
            result += f"\n\nTop performer: **{top['name']}** with highest completion rate."
        if attention:
            result += f"\nNeeds attention: **{attention['name']}** with proportionally higher delays."
        return result

    completion_rate = round((tasks.filter(status="completed").count() / tasks.count()) * 100) if tasks.count() else 0
    return (
        "I can help you with project insights! Here's a quick snapshot:\n\n"
        f"• **{projects.count()} projects** in portfolio\n"
        f"• **{completion_rate}%** overall completion\n"
        f"• **{hurdles.exclude(status='resolved').count()}** active hurdles\n"
        f"• **{tasks.filter(status='delayed').count()}** delayed tasks\n\n"
        'Try asking:\n• "Which project is most delayed?"\n• "Show hurdles affecting Tower A"\n• "Predict next delay risk"'
    )

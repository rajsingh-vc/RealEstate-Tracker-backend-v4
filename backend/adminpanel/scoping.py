"""
Dynamic multi-tenant queryset scoping.

The old EscalationRuleViewSet hardcoded "if user.company: return everything"
as a placeholder. This module replaces that pattern with logic that's driven
entirely by what the requesting user actually has access to, discovered at
call time rather than assumed up front:

  1. Superusers / users with role == "SuperAdmin" -> full queryset.
  2. Users exposing a many-to-many `organizations` relation (e.g. an admin
     or CEO who can operate across several tenants) -> scoped to that set.
  3. Users exposing a single `organization_id` FK -> scoped to that one org.
  4. Anyone else (or an unauthenticated request slipping through) -> empty
     queryset. No silent "allow all" fallback.

This is intentionally introspective (hasattr/getattr) rather than coupled to
one specific User model shape, so it keeps working if the accounts app later
adds/changes how users relate to organizations.
"""

from __future__ import annotations

from django.db.models import QuerySet


def user_organization_ids(user) -> list[int]:
    """Resolve the set of organization IDs a (non-superadmin) user can access.

    ✅ FIXED: accounts.User has no `organizations` M2M and no `organization`
    FK — its actual tenant link is `User.company` (a FK to accounts.Company,
    which is what this whole codebase calls "Organization" everywhere else;
    see the aliasing note at the top of projects/models.py). The previous
    version of this function only ever checked for `user.organizations` and
    `user.organization_id`, neither of which exists on User, so it fell
    through to `return []` for every non-superadmin user — silently
    emptying out every org-scoped queryset (Projects, Tasks, Documents,
    Checklists, Compliance, Handover, Hurdles, Resources, Society,
    CategoryManagement) regardless of what access they'd actually been
    granted. Checking `company_id` first (the field that really exists)
    fixes that, while still supporting an `organizations` M2M or an
    `organization_id` FK if either gets added to User later.
    """
    if hasattr(user, "organizations"):
        # M2M: users who can operate across multiple organizations.
        return list(user.organizations.values_list("id", flat=True))

    org_id = getattr(user, "company_id", None) or getattr(user, "organization_id", None)
    if org_id:
        # Single-tenant user: one FK to their organization.
        return [org_id]

    return []


def is_unrestricted(user) -> bool:
    return bool(user and user.is_authenticated and (user.is_superuser or getattr(user, "role", None) == "SuperAdmin"))


def scope_organizations(user, queryset: QuerySet) -> QuerySet:
    """Scope a queryset of Organization rows themselves (filter by `id`)."""
    if not user or not user.is_authenticated:
        return queryset.none()
    if is_unrestricted(user):
        return queryset
    org_ids = user_organization_ids(user)
    if not org_ids:
        return queryset.none()
    return queryset.filter(id__in=org_ids)


def scope_by_organization_fk(user, queryset: QuerySet, fk_name: str = "organization") -> QuerySet:
    """Scope a queryset of rows that have an `organization` FK (Company, Entity, ...)."""
    if not user or not user.is_authenticated:
        return queryset.none()
    if is_unrestricted(user):
        return queryset
    org_ids = user_organization_ids(user)
    if not org_ids:
        return queryset.none()
    return queryset.filter(**{f"{fk_name}_id__in": org_ids})
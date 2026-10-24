from typing import Any, Dict, List
from django.db import models, transaction
from rest_framework import permissions, status, views, viewsets
from rest_framework.response import Response

from .models import (
    AppModule,
    Company,
    Invitation,
    ModuleAuditLog,
    Role,
    RoleModulePermission,
    User,
    UserModulePermission,
)
from .module_registry import (
    get_user_effective_modules,
    is_module_enabled_for_user,
    log_module_audit,
    sync_default_modules,
)
from .module_serializers import (
    AppModuleSerializer,
    ModuleAuditLogSerializer,
    RoleModulePermissionSerializer,
    UserModulePermissionSerializer,
)
from .permissions import is_admin_or_superadmin


class MyModulePermissionsView(views.APIView):
    """
    Returns effective module permissions for the currently authenticated user.
    Called on app load, project switch, or after permission updates.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        project_id_raw = request.query_params.get("project_id")
        project_id = int(project_id_raw) if (project_id_raw and project_id_raw.isdigit()) else None

        effective_list = get_user_effective_modules(request.user, project_id=project_id)
        module_map = {m["key"]: {"is_enabled": m["is_enabled"], "is_visible": m["is_visible"]} for m in effective_list}

        return Response({
            "user_id": request.user.id,
            "is_superuser": request.user.is_superuser,
            "project_id": project_id,
            "modules": effective_list,
            "module_map": module_map,
        })


class AppModuleViewSet(viewsets.ModelViewSet):
    """
    Registry of all modules.
    - Read: Any authenticated user.
    - Create/Update/Delete: Super Admin only.
    """
    serializer_class = AppModuleSerializer
    queryset = AppModule.objects.all().order_by("order", "name")

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [permissions.IsAuthenticated()]
        return [permissions.IsAdminUser()]

    def list(self, request, *args, **kwargs):
        sync_default_modules()
        qs = self.get_queryset()
        category = request.query_params.get("category")
        if category:
            qs = qs.filter(category=category)
        search = request.query_params.get("search")
        if search:
            qs = qs.filter(models.Q(name__icontains=search) | models.Q(key__icontains=search))

        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)


class ToggleGlobalModuleView(views.APIView):
    """
    SuperAdmin-exclusive endpoint to globally enable/disable a module.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if not request.user.is_superuser:
            return Response(
                {"detail": "Only Super Admin can toggle global module activation."},
                status=status.HTTP_403_FORBIDDEN,
            )

        module_key = request.data.get("module_key")
        is_active = request.data.get("is_active")

        if not module_key or is_active is None:
            return Response(
                {"detail": "Both module_key and is_active are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            module = AppModule.objects.get(key=module_key)
        except AppModule.DoesNotExist:
            return Response({"detail": f"Module '{module_key}' not found."}, status=status.HTTP_404_NOT_FOUND)

        prev_active = module.is_active
        module.is_active = bool(is_active)
        module.save(update_fields=["is_active", "updated_at"])

        log_module_audit(
            actor=request.user,
            action="toggle_global",
            module_key=module.key,
            previous_value={"is_active": prev_active},
            new_value={"is_active": module.is_active},
            details=f"Global active state changed to {module.is_active} for {module.name}",
        )

        return Response({
            "message": f"Module '{module.name}' global state updated.",
            "module": AppModuleSerializer(module).data,
        })


class UserModuleConfigView(views.APIView):
    """
    Inspect, update, or reset module visibility and access overrides for an individual user.
    """
    permission_classes = [permissions.IsAuthenticated]

    def _check_scope(self, request_user, target_user) -> bool:
        """Verifies that request_user is authorized to manage target_user."""
        if request_user.is_superuser:
            return True
        if not is_admin_or_superadmin(request_user):
            return False
        if target_user.is_superuser:
            return False
        # Site Admin: can manage users within their own company/tenant or users they invited
        if request_user.company_id is not None and target_user.company_id == request_user.company_id:
            return True
        if Invitation.objects.filter(accepted_by=target_user, invited_by=request_user).exists():
            return True
        return False

    def get(self, request, user_id: int):
        try:
            target_user = User.objects.select_related("role", "company").get(id=user_id)
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        if not self._check_scope(request.user, target_user):
            return Response(
                {"detail": "You do not have permission to view module configurations for this user."},
                status=status.HTTP_403_FORBIDDEN,
            )

        project_id_raw = request.query_params.get("project_id")
        project_id = int(project_id_raw) if (project_id_raw and project_id_raw.isdigit()) else None

        effective_modules = get_user_effective_modules(target_user, project_id=project_id)

        # Also fetch raw overrides
        overrides = UserModulePermission.objects.filter(user=target_user)
        if project_id:
            overrides = overrides.filter(project_id=project_id)
        else:
            overrides = overrides.filter(project__isnull=True)

        overrides_data = {o.module.key: {"is_enabled": o.is_enabled, "is_visible": o.is_visible} for o in overrides}

        return Response({
            "user": {
                "id": target_user.id,
                "name": target_user.name,
                "email": target_user.email,
                "role": target_user.role.name if target_user.role else "No Role",
                "company_id": target_user.company_id,
            },
            "project_id": project_id,
            "modules": effective_modules,
            "overrides": overrides_data,
        })

    def post(self, request, user_id: int):
        try:
            target_user = User.objects.select_related("role", "company").get(id=user_id)
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        if not self._check_scope(request.user, target_user):
            return Response(
                {"detail": "You do not have permission to configure modules for this user."},
                status=status.HTTP_403_FORBIDDEN,
            )

        project_id_raw = request.data.get("project_id")
        project_id = int(project_id_raw) if (project_id_raw and str(project_id_raw).isdigit()) else None

        overrides_list = request.data.get("overrides", [])
        if not isinstance(overrides_list, list):
            return Response({"detail": "overrides must be a list."}, status=status.HTTP_400_BAD_REQUEST)

        # Pre-fetch modules
        modules_by_key = {m.key: m for m in AppModule.objects.all()}

        # Verify Site Admin scope restriction:
        # A Site Admin cannot grant a module that is disabled for their own scope
        if not request.user.is_superuser:
            site_admin_effective = {m["key"]: m["is_enabled"] for m in get_user_effective_modules(request.user, project_id=project_id)}

        prev_overrides = {
            uo.module.key: {"is_enabled": uo.is_enabled, "is_visible": uo.is_visible}
            for uo in UserModulePermission.objects.filter(user=target_user, project_id=project_id)
        }

        updated_keys = []
        with transaction.atomic():
            for item in overrides_list:
                key = item.get("module_key")
                if not key or key not in modules_by_key:
                    continue

                module = modules_by_key[key]
                new_enabled = item.get("is_enabled")  # can be True, False, or None (inherit)
                new_visible = item.get("is_visible")  # can be True, False, or None (inherit)

                # Site Admin restriction check
                if not request.user.is_superuser and new_enabled is True:
                    if not site_admin_effective.get(key, False):
                        return Response(
                            {"detail": f"You cannot grant access to '{module.name}' as it is not enabled for your organization."},
                            status=status.HTTP_403_FORBIDDEN,
                        )

                if new_enabled is None and new_visible is None:
                    # Inherit: delete override record
                    UserModulePermission.objects.filter(
                        user=target_user,
                        module=module,
                        project_id=project_id,
                    ).delete()
                else:
                    UserModulePermission.objects.update_or_create(
                        user=target_user,
                        module=module,
                        project_id=project_id,
                        defaults={
                            "is_enabled": new_enabled,
                            "is_visible": new_visible,
                            "created_by": request.user,
                        },
                    )
                updated_keys.append(key)

            log_module_audit(
                actor=request.user,
                action="update_user_override",
                module_key=",".join(updated_keys) if updated_keys else "none",
                target_user=target_user,
                target_project_id=project_id,
                organization=target_user.company,
                previous_value=prev_overrides,
                new_value={item.get("module_key"): item for item in overrides_list},
                details=f"Updated module overrides for {target_user.name} ({len(updated_keys)} modules modified)",
            )

        # Return updated effective modules
        fresh_effective = get_user_effective_modules(target_user, project_id=project_id)
        return Response({
            "message": f"Module permissions updated for {target_user.name}.",
            "modules": fresh_effective,
        })


class ResetUserModuleConfigView(views.APIView):
    """
    Resets all custom overrides for a user back to role inheritance.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, user_id: int):
        try:
            target_user = User.objects.select_related("role", "company").get(id=user_id)
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        if not request.user.is_superuser:
            can_manage = is_admin_or_superadmin(request.user) and (
                (request.user.company_id and request.user.company_id == target_user.company_id)
                or Invitation.objects.filter(accepted_by=target_user, invited_by=request.user).exists()
            )
            if not can_manage:
                return Response({"detail": "Unauthorized to reset permissions for this user."}, status=status.HTTP_403_FORBIDDEN)

        project_id_raw = request.data.get("project_id")
        project_id = int(project_id_raw) if (project_id_raw and str(project_id_raw).isdigit()) else None

        qs = UserModulePermission.objects.filter(user=target_user)
        if project_id:
            qs = qs.filter(project_id=project_id)

        count = qs.count()
        qs.delete()

        log_module_audit(
            actor=request.user,
            action="reset_user_override",
            module_key="all",
            target_user=target_user,
            target_project_id=project_id,
            organization=target_user.company,
            details=f"Reset all {count} custom module overrides for {target_user.name} to role inheritance",
        )

        return Response({
            "message": f"Successfully reset {count} module overrides for {target_user.name}.",
            "modules": get_user_effective_modules(target_user, project_id=project_id),
        })


class BulkUserModuleConfigView(views.APIView):
    """
    Bulk update module overrides across multiple selected users.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if not is_admin_or_superadmin(request.user):
            return Response({"detail": "Unauthorized."}, status=status.HTTP_403_FORBIDDEN)

        user_ids = request.data.get("user_ids", [])
        overrides = request.data.get("overrides", [])
        project_id_raw = request.data.get("project_id")
        project_id = int(project_id_raw) if (project_id_raw and str(project_id_raw).isdigit()) else None

        if not user_ids or not overrides:
            return Response({"detail": "Both user_ids and overrides are required."}, status=status.HTTP_400_BAD_REQUEST)

        # Scoping filter
        users_qs = User.objects.filter(id__in=user_ids)
        if not request.user.is_superuser:
            users_qs = users_qs.filter(company_id=request.user.company_id).exclude(is_superuser=True)

        users = list(users_qs)
        modules_by_key = {m.key: m for m in AppModule.objects.all()}

        modified_count = 0
        with transaction.atomic():
            for target_user in users:
                for item in overrides:
                    key = item.get("module_key")
                    if not key or key not in modules_by_key:
                        continue
                    mod = modules_by_key[key]
                    new_enabled = item.get("is_enabled")
                    new_visible = item.get("is_visible")

                    if new_enabled is None and new_visible is None:
                        UserModulePermission.objects.filter(
                            user=target_user,
                            module=mod,
                            project_id=project_id,
                        ).delete()
                    else:
                        UserModulePermission.objects.update_or_create(
                            user=target_user,
                            module=mod,
                            project_id=project_id,
                            defaults={
                                "is_enabled": new_enabled,
                                "is_visible": new_visible,
                                "created_by": request.user,
                            },
                        )
                modified_count += 1

                log_module_audit(
                    actor=request.user,
                    action="bulk_update",
                    module_key="multiple",
                    target_user=target_user,
                    target_project_id=project_id,
                    organization=target_user.company,
                    new_value={"overrides": overrides},
                    details=f"Bulk applied {len(overrides)} module policies to {target_user.name}",
                )

        return Response({
            "message": f"Successfully updated module permissions for {modified_count} users.",
            "modified_count": modified_count,
        })


class RoleModuleConfigView(views.APIView):
    """
    Get or update module policies for a specific Role.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, role_id: int):
        try:
            role = Role.objects.get(id=role_id)
        except Role.DoesNotExist:
            return Response({"detail": "Role not found."}, status=status.HTTP_404_NOT_FOUND)

        if not request.user.is_superuser:
            if not is_admin_or_superadmin(request.user) or (role.company_id and role.company_id != request.user.company_id):
                return Response({"detail": "Unauthorized to view this role's policies."}, status=status.HTTP_403_FORBIDDEN)

        sync_default_modules()
        all_modules = list(AppModule.objects.all().order_by("order", "name"))
        role_perms = {
            rp.module_id: rp
            for rp in RoleModulePermission.objects.filter(role=role)
        }

        modules_data = []
        for m in all_modules:
            rp = role_perms.get(m.id)
            is_enabled = rp.is_enabled if rp else (False if m.admin_only and not ("admin" in role.name.lower() or "super" in role.name.lower()) else m.default_enabled)
            is_visible = rp.is_visible if rp else (False if m.admin_only and not ("admin" in role.name.lower() or "super" in role.name.lower()) else m.default_visible)

            modules_data.append({
                "key": m.key,
                "name": m.name,
                "category": m.category,
                "route": m.route,
                "icon": m.icon,
                "order": m.order,
                "is_active": m.is_active,
                "is_enabled": is_enabled,
                "is_visible": is_visible,
                "has_explicit_policy": rp is not None,
            })

        return Response({
            "role": {"id": role.id, "name": role.name, "company_id": role.company_id},
            "modules": modules_data,
        })

    def post(self, request, role_id: int):
        try:
            role = Role.objects.get(id=role_id)
        except Role.DoesNotExist:
            return Response({"detail": "Role not found."}, status=status.HTTP_404_NOT_FOUND)

        if not request.user.is_superuser:
            if not is_admin_or_superadmin(request.user) or (role.company_id and role.company_id != request.user.company_id):
                return Response({"detail": "Unauthorized to configure this role."}, status=status.HTTP_403_FORBIDDEN)

        policies = request.data.get("policies", [])
        if not isinstance(policies, list):
            return Response({"detail": "policies must be a list."}, status=status.HTTP_400_BAD_REQUEST)

        modules_by_key = {m.key: m for m in AppModule.objects.all()}
        prev_policies = {
            rp.module.key: {"is_enabled": rp.is_enabled, "is_visible": rp.is_visible}
            for rp in RoleModulePermission.objects.filter(role=role)
        }

        with transaction.atomic():
            for item in policies:
                key = item.get("module_key")
                if not key or key not in modules_by_key:
                    continue
                mod = modules_by_key[key]
                new_enabled = bool(item.get("is_enabled", True))
                new_visible = bool(item.get("is_visible", True))

                RoleModulePermission.objects.update_or_create(
                    role=role,
                    module=mod,
                    organization=role.company,
                    defaults={
                        "is_enabled": new_enabled,
                        "is_visible": new_visible,
                    },
                )

            log_module_audit(
                actor=request.user,
                action="update_role_policy",
                module_key="multiple",
                target_role=role,
                organization=role.company,
                previous_value=prev_policies,
                new_value={item.get("module_key"): item for item in policies},
                details=f"Updated role module policies for {role.name}",
            )

        return Response({
            "message": f"Role module policies updated for {role.name}.",
        })


class ModuleMatrixView(views.APIView):
    """
    Overview matrix of all modules across dynamic users and roles for authorized Admins.
    Dynamically includes SuperAdmin and users who have accepted invitations (or all scoped users if requested).
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not is_admin_or_superadmin(request.user):
            return Response({"detail": "Unauthorized."}, status=status.HTTP_403_FORBIDDEN)

        sync_default_modules()
        all_modules = list(AppModule.objects.all().order_by("order", "name"))

        # Scoped roles
        roles_qs = Role.objects.all()
        if not request.user.is_superuser and request.user.company_id:
            roles_qs = roles_qs.filter(models.Q(company_id=request.user.company_id) | models.Q(company__isnull=True))
        roles = list(roles_qs.order_by("name"))

        # Role permissions map
        role_perms = {
            (rp.role_id, rp.module_id): rp
            for rp in RoleModulePermission.objects.filter(role__in=roles)
        }

        # Dynamic Users query:
        # Per requirement: "this should be dynamic not static right now only superadmin is there so...
        # keep that only if i invite someone and that person accepts that invite that person according
        # Dynamic Users query:
        include_all = request.query_params.get("include_all", "").lower() in ("true", "1", "yes")

        base_users = User.objects.select_related("role", "company").filter(is_active=True)
        if not request.user.is_superuser and request.user.company_id:
            base_users = base_users.filter(company_id=request.user.company_id)

        accepted_invites = Invitation.objects.filter(status=Invitation.Status.ACCEPTED)
        if not request.user.is_superuser:
            if request.user.company_id:
                accepted_invites = accepted_invites.filter(
                    models.Q(company_id=request.user.company_id) | models.Q(invited_by=request.user)
                )
            else:
                accepted_invites = accepted_invites.filter(invited_by=request.user)

        accepted_emails_lower = {e.strip().lower() for e in accepted_invites.values_list("email", flat=True) if e}
        accepted_user_ids = set(accepted_invites.filter(accepted_by__isnull=False).values_list("accepted_by_id", flat=True))

        email_q = models.Q()
        for em in accepted_emails_lower:
            email_q |= models.Q(email__iexact=em)

        if include_all:
            matrix_users_qs = base_users.filter(is_superuser=False).order_by("name", "username")
        else:
            # Non-superuser accounts who were invited and accepted their invite
            matrix_users_qs = base_users.filter(
                models.Q(is_superuser=False) & (
                    models.Q(id__in=accepted_user_ids) |
                    email_q |
                    models.Q(accepted_invitation__status=Invitation.Status.ACCEPTED)
                )
            ).distinct().order_by("name", "username")

            # Fallback: if no users specifically match accepted invite filter, show active non-superusers in company
            if not matrix_users_qs.exists() and base_users.filter(is_superuser=False).exists():
                matrix_users_qs = base_users.filter(is_superuser=False).order_by("name", "username")

        matrix_users = list(matrix_users_qs)

        # Pre-fetch user overrides for these users
        user_overrides_map = {
            (uo.user_id, uo.module_id): uo
            for uo in UserModulePermission.objects.filter(user__in=matrix_users, project__isnull=True)
        }

        # Total user overrides count across all active users
        overrides_count_by_module = {}
        for row in UserModulePermission.objects.filter(user__in=base_users).values("module__key").annotate(total=models.Count("id")):
            overrides_count_by_module[row["module__key"]] = row["total"]

        matrix = []
        for m in all_modules:
            role_map = {}
            for r in roles:
                rp = role_perms.get((r.id, m.id))
                role_map[r.id] = {
                    "role_name": r.name,
                    "is_enabled": rp.is_enabled if rp else (False if m.admin_only and not ("admin" in r.name.lower() or "super" in r.name.lower()) else m.default_enabled),
                    "is_visible": rp.is_visible if rp else (False if m.admin_only and not ("admin" in r.name.lower() or "super" in r.name.lower()) else m.default_visible),
                    "has_override": rp is not None,
                }

            user_map = {}
            for u in matrix_users:
                override = user_overrides_map.get((u.id, m.id))
                is_enabled = is_module_enabled_for_user(u, m.key)
                user_map[u.id] = {
                    "is_enabled": is_enabled,
                    "is_visible": is_enabled,
                    "has_override": override is not None,
                    "source": "superadmin" if (u.is_superuser and override is None) else ("override" if override is not None else "role"),
                }

            matrix.append({
                "module_id": m.id,
                "key": m.key,
                "name": m.name,
                "category": m.category,
                "route": m.route,
                "icon": m.icon,
                "is_active": m.is_active,
                "default_enabled": m.default_enabled,
                "default_visible": m.default_visible,
                "admin_only": m.admin_only,
                "user_overrides_count": overrides_count_by_module.get(m.key, 0),
                "roles": role_map,
                "users": user_map,
            })

        user_list = []
        for u in matrix_users:
            u_email_lower = (u.email or "").strip().lower()
            is_invited_user = bool(
                u.id in accepted_user_ids
                or (u_email_lower and u_email_lower in accepted_emails_lower)
                or getattr(u, "accepted_invitation", None) is not None
            )
            user_list.append({
                "id": u.id,
                "name": u.name or u.username,
                "username": u.username,
                "email": u.email,
                "role_name": u.role.name if u.role else ("Super Admin" if u.is_superuser else "User"),
                "is_superuser": u.is_superuser,
                "is_invited": is_invited_user,
                "company_name": (getattr(u.company, "name", None) or getattr(u.company, "company_name", None)) if u.company else None,
            })

        return Response({
            "modules": matrix,
            "roles": [{"id": r.id, "name": r.name} for r in roles],
            "users": user_list,
            "total_users": base_users.count(),
            "filtered_users_count": len(user_list),
        })


class ModuleAuditLogListView(views.APIView):
    """
    Retrieve audit history of module configuration changes.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not is_admin_or_superadmin(request.user):
            return Response({"detail": "Unauthorized."}, status=status.HTTP_403_FORBIDDEN)

        qs = ModuleAuditLog.objects.select_related("actor", "target_user", "target_role").all()
        if not request.user.is_superuser and request.user.company_id:
            qs = qs.filter(models.Q(organization_id=request.user.company_id) | models.Q(actor__company_id=request.user.company_id))

        logs = qs[:100]
        serializer = ModuleAuditLogSerializer(logs, many=True)
        return Response(serializer.data)

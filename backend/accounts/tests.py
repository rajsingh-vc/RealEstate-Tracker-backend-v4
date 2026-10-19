from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import AppModule, Company, ModuleAuditLog, Role, RoleModulePermission, User, UserModulePermission
from accounts.module_registry import get_user_effective_modules, is_module_enabled_for_user, sync_default_modules


class ModuleVisibilityAndPermissionTests(TestCase):
    def setUp(self):
        sync_default_modules()
        self.client = APIClient()

        # Company
        self.company = Company.objects.create(name="Notandas Realty", subdomain="notandas")

        # Super Admin
        self.super_admin = User.objects.create_superuser(
            username="superadmin", email="super@notandas.com", password="password123", name="Super Admin"
        )

        # Site Admin Role & User
        self.admin_role = Role.objects.create(name="Site Admin", company=self.company)
        self.site_admin = User.objects.create_user(
            username="siteadmin", email="admin@notandas.com", password="password123",
            name="Site Admin", company=self.company, role=self.admin_role
        )

        # Standard Users
        self.member_role = Role.objects.create(name="Site Engineer", company=self.company)
        self.user_a = User.objects.create_user(
            username="user_a", email="user_a@notandas.com", password="password123",
            name="User Alpha", company=self.company, role=self.member_role
        )
        self.user_b = User.objects.create_user(
            username="user_b", email="user_b@notandas.com", password="password123",
            name="User Beta", company=self.company, role=self.member_role
        )

    def test_default_modules_registered(self):
        """All 16 standard modules are seeded in AppModule."""
        self.assertEqual(AppModule.objects.count(), 16)
        hurdles = AppModule.objects.get(key="hurdles")
        self.assertEqual(hurdles.name, "Hurdle Tracker")
        self.assertEqual(hurdles.category, "Operations")

    def test_super_admin_has_full_access(self):
        """Super Admin has enabled & visible on all active modules."""
        modules = get_user_effective_modules(self.super_admin)
        for m in modules:
            self.assertTrue(m["is_enabled"])
            self.assertTrue(m["is_visible"])
            self.assertEqual(m["source"], "superadmin")

    def test_standard_users_default_permissions(self):
        """Standard users receive default permissions based on AppModule defaults and role."""
        modules_a = {m["key"]: m for m in get_user_effective_modules(self.user_a)}
        # Hurdle Tracker, Resources, Checklists are enabled by default
        self.assertTrue(modules_a["hurdles"]["is_enabled"])
        self.assertTrue(modules_a["resources"]["is_enabled"])
        self.assertTrue(modules_a["checklists"]["is_enabled"])
        # Category Management is admin-only by default
        self.assertFalse(modules_a["category-management"]["is_enabled"])

    def test_user_specific_override_disables_module_for_one_user_only(self):
        """Disabling Hurdle Tracker for user_a does not affect user_b."""
        hurdles_mod = AppModule.objects.get(key="hurdles")
        UserModulePermission.objects.create(
            user=self.user_a,
            module=hurdles_mod,
            is_enabled=False,
            is_visible=False,
            created_by=self.super_admin,
        )

        # Verify user_a has hurdle tracker disabled
        self.assertFalse(is_module_enabled_for_user(self.user_a, "hurdles"))
        modules_a = {m["key"]: m for m in get_user_effective_modules(self.user_a)}
        self.assertFalse(modules_a["hurdles"]["is_enabled"])
        self.assertFalse(modules_a["hurdles"]["is_visible"])
        self.assertEqual(modules_a["hurdles"]["source"], "user_override")

        # Verify user_b still has hurdle tracker enabled
        self.assertTrue(is_module_enabled_for_user(self.user_b, "hurdles"))
        modules_b = {m["key"]: m for m in get_user_effective_modules(self.user_b)}
        self.assertTrue(modules_b["hurdles"]["is_enabled"])
        self.assertTrue(modules_b["hurdles"]["is_visible"])

    def test_api_user_module_config_and_audit_log(self):
        """Updating user module config via API persists changes and writes audit log."""
        self.client.force_authenticate(user=self.super_admin)
        url = f"/api/modules/users/{self.user_a.id}/"
        payload = {
            "overrides": [
                {"module_key": "hurdles", "is_enabled": False, "is_visible": False},
                {"module_key": "resources", "is_enabled": False, "is_visible": False},
            ]
        }
        res = self.client.post(url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        # Verify backend evaluation
        self.assertFalse(is_module_enabled_for_user(self.user_a, "hurdles"))
        self.assertFalse(is_module_enabled_for_user(self.user_a, "resources"))
        self.assertTrue(is_module_enabled_for_user(self.user_a, "checklists"))

        # Verify audit log
        audit = ModuleAuditLog.objects.filter(target_user=self.user_a).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.actor, self.super_admin)
        self.assertEqual(audit.action, "update_user_override")

    def test_reset_user_overrides_restores_defaults(self):
        """Resetting user overrides restores inherited permissions."""
        hurdles_mod = AppModule.objects.get(key="hurdles")
        UserModulePermission.objects.create(
            user=self.user_a, module=hurdles_mod, is_enabled=False, is_visible=False
        )
        self.assertFalse(is_module_enabled_for_user(self.user_a, "hurdles"))

        self.client.force_authenticate(user=self.super_admin)
        res = self.client.post(f"/api/modules/users/{self.user_a.id}/reset/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.assertTrue(is_module_enabled_for_user(self.user_a, "hurdles"))

    def test_backend_enforcement_blocks_direct_api_access(self):
        """When a module is disabled for a user, direct API calls return HTTP 403."""
        hurdles_mod = AppModule.objects.get(key="hurdles")
        UserModulePermission.objects.create(
            user=self.user_a, module=hurdles_mod, is_enabled=False, is_visible=False
        )

        # user_a attempts to access /api/hurdles/
        self.client.force_authenticate(user=self.user_a)
        res_a = self.client.get("/api/hurdles/")
        self.assertEqual(res_a.status_code, status.HTTP_403_FORBIDDEN)

        # user_b attempts to access /api/hurdles/ -> allowed
        self.client.force_authenticate(user=self.user_b)
        res_b = self.client.get("/api/hurdles/")
        self.assertEqual(res_b.status_code, status.HTTP_200_OK)

    def test_my_permissions_endpoint(self):
        """GET /api/modules/my-permissions/ returns the caller's effective module mapping."""
        self.client.force_authenticate(user=self.user_b)
        res = self.client.get("/api/modules/my-permissions/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        module_map = data.get("module_map") or data.get("moduleMap")
        self.assertIsNotNone(module_map)
        hurdles_access = module_map.get("hurdles", {})
        is_enabled = hurdles_access.get("is_enabled") if "is_enabled" in hurdles_access else hurdles_access.get("isEnabled")
        self.assertTrue(is_enabled)

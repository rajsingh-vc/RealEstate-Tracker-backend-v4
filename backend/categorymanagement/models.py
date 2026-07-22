"""
The frontend's Category Management page (src/pages/CategoryManagement.tsx)
treats "Category" as a Tower and "Sub Category" as a Floor — there is no
separate table for either concept, it reuses the existing
Project -> Tower -> Floor hierarchy from the `projects` app.

This app gives that concept its own home (its own admin section,
serializers, viewsets and /api/categories/ + /api/subcategories/ endpoints)
without duplicating data: Category and SubCategory are Django *proxy*
models over projects.Tower and projects.Floor, so they share the same
database table and stay perfectly in sync with /api/towers/ and
/api/floors/. No new migrations touch the underlying schema.
"""

from projects.models import Floor, Tower


class Category(Tower):
    """Proxy over projects.Tower — the "Category" concept in the UI."""

    class Meta:
        proxy = True
        verbose_name = "Category"
        verbose_name_plural = "Categories"

    def __str__(self):
        return f"{self.name} ({self.project.name})"


class SubCategory(Floor):
    """Proxy over projects.Floor — the "Sub Category" concept in the UI."""

    class Meta:
        proxy = True
        verbose_name = "Sub Category"
        verbose_name_plural = "Sub Categories"

    def __str__(self):
        return f"{self.name} - {self.tower.name}"

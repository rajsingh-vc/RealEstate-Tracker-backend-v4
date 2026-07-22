from django.db import models
from accounts.models import Company
from categorymanagement.models import Category, SubCategory
from projects.models import Project, Tower, Floor, Unit


class ChecklistStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    COMPLETED = "completed", "Completed"


class ChecklistTemplate(models.Model):
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=100, default="General")
    # Do NOT add company here – filter via project when needed.

    # ---- Category Management linkage ------------------------------------
    # Optional link from a template to where it applies in the project
    # hierarchy, backed by the categorymanagement app (Category = Tower,
    # SubCategory = Floor). Kept separate from the free-text `category`
    # field above, which is just a label/tag (e.g. "Foundation", "MEP") —
    # this is the dropdown-driven link to a real Category/Sub Category
    # record instead of typed text.
    project = models.ForeignKey(
        Project,
        related_name="checklist_templates",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    linked_category = models.ForeignKey(
        Category,
        related_name="checklist_templates",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="The Category (Tower) this template applies to, from Category Management.",
    )
    linked_sub_category = models.ForeignKey(
        SubCategory,
        related_name="checklist_templates",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="The Sub Category (Floor) this template applies to, from Category Management.",
    )

    class Meta:
        ordering = ["category", "name"]

    def __str__(self):
        return self.name


class ChecklistTemplateItem(models.Model):
    template = models.ForeignKey(ChecklistTemplate, related_name="items", on_delete=models.CASCADE)
    text = models.CharField(max_length=255)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.text


class Checklist(models.Model):
    """A per-task checklist instance (distinct from ChecklistTemplate,
    which is just a reusable list of item titles)."""
    task = models.ForeignKey("tasks.Task", related_name="checklists", on_delete=models.CASCADE)
    unit = models.ForeignKey(Unit, related_name="checklists", null=True, blank=True, on_delete=models.CASCADE)
    floor = models.ForeignKey(Floor, related_name="checklists", null=True, blank=True, on_delete=models.CASCADE)
    tower = models.ForeignKey(Tower, related_name="checklists", null=True, blank=True, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, related_name="checklists", on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    status = models.CharField(max_length=32, default="Pending", blank=True)
    progress = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.name


class SubTask(models.Model):
    checklist = models.ForeignKey(Checklist, related_name="sub_tasks", on_delete=models.CASCADE)
    task = models.ForeignKey("tasks.Task", related_name="sub_tasks", on_delete=models.CASCADE)
    unit = models.ForeignKey(Unit, related_name="sub_tasks", null=True, blank=True, on_delete=models.CASCADE)
    floor = models.ForeignKey(Floor, related_name="sub_tasks", null=True, blank=True, on_delete=models.CASCADE)
    tower = models.ForeignKey(Tower, related_name="sub_tasks", null=True, blank=True, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, related_name="sub_tasks", on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    status = models.CharField(max_length=32, default="Pending", blank=True)
    progress = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.name
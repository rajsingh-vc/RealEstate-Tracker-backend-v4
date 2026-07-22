from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

# ✅ Correct import – from accounts, not from .models
from accounts.models import Company, User

# Import the existing Project, Tower, Floor, Unit from projects app
from projects.models import Project, Tower, Floor, Unit


class TaskStatus(models.TextChoices):
    NOT_STARTED = "not_started", "Not Started"
    READY = "ready", "Ready"
    IN_PROGRESS = "in_progress", "In Progress"
    BLOCKED = "blocked", "Blocked"
    REVIEW = "review", "Review"
    COMPLETED = "completed", "Completed"
    DELAYED = "delayed", "Delayed"


class Priority(models.TextChoices):
    # ✅ "Critical" removed — High / Medium / Low only, matching the
    # priority Select in NewTaskDialog.tsx / Tasks.tsx.
    HIGH = "high", "High"
    MEDIUM = "medium", "Medium"
    LOW = "low", "Low"


class RepeatFrequency(models.TextChoices):
    DAILY = "daily", "Daily"
    WEEKLY = "weekly", "Weekly"
    MONTHLY = "monthly", "Monthly"


class Task(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    # ✅ Free text now — the old nine-value Department TextChoices enum has
    # been removed entirely. This field just stores whatever string the
    # frontend sends (e.g. "Civil", "MEP", or anything a client types).
    department = models.CharField(max_length=100, blank=True)

    assigned_hod = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="hod_tasks", null=True, blank=True, on_delete=models.SET_NULL
    )
    assigned_users = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="assigned_tasks", blank=True)

    # ------------------------------------------------------------------
    # Single primary owner, distinct from assigned_users above (which
    # supports multiple people). Backs the "Assigned To" select in
    # TaskRelationsPanel (Tasks.tsx).
    # ------------------------------------------------------------------
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="owned_tasks",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    actual_start_date = models.DateField(null=True, blank=True)
    actual_end_date = models.DateField(null=True, blank=True)

    priority = models.CharField(max_length=16, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=32, default="Not Started", blank=True)

    dependencies = models.ManyToManyField("self", symmetrical=False, related_name="dependents", blank=True)

    # ------------------------------------------------------------------
    # Single predecessor task, distinct from the `dependencies` M2M above
    # (which supports multiple). Backs the "Depends On" select in
    # TaskRelationsPanel (Tasks.tsx), which is currently single-choice.
    # If "Depends On" later becomes multi-select in the UI, drop this
    # field and have the frontend write to `dependencies` instead.
    # ------------------------------------------------------------------
    depends_on = models.ForeignKey(
        "self",
        related_name="dependent_tasks",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    # ------------------------------------------------------------------
    # Repeating-task support. Backs the "Repetitive task" checkbox +
    # frequency select in TaskRelationsPanel (Tasks.tsx). This only tags a
    # task as repeating and records its cadence — it doesn't itself spawn
    # future task instances; that would need a separate scheduled job.
    # ------------------------------------------------------------------
    is_repetitive = models.BooleanField(default=False)
    repeat_frequency = models.CharField(
        max_length=10, choices=RepeatFrequency.choices, null=True, blank=True
    )

    # ------------------------------------------------------------------
    # Marks a task as personal/self-assigned (e.g. no HOD required).
    # Backs the "Self task" checkbox in TaskRelationsPanel (Tasks.tsx).
    # ------------------------------------------------------------------
    is_self_task = models.BooleanField(default=False)

    progress = models.PositiveSmallIntegerField(default=0)
    delay_days = models.IntegerField(default=0)
    delay_reason = models.CharField(max_length=255, blank=True)
    critical_path = models.BooleanField(default=False)

    project = models.ForeignKey(Project, related_name="tasks", on_delete=models.CASCADE)
    tower = models.ForeignKey(Tower, related_name="tasks", null=True, blank=True, on_delete=models.SET_NULL)
    floor = models.ForeignKey(Floor, related_name="tasks", null=True, blank=True, on_delete=models.SET_NULL)
    unit = models.ForeignKey(Unit, related_name="tasks", null=True, blank=True, on_delete=models.SET_NULL)
    phase = models.CharField(max_length=64, blank=True)  # free text, no choices

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def clean(self):
        # ✅ NEW — model-level backstop for the same rule TaskSerializer
        # enforces at the API boundary. This doesn't run automatically on
        # .save() unless full_clean() is called first (the serializer path
        # already validates before save), so this mainly protects against
        # tasks created via the Django admin or a management shell.
        if self.project_id is None:
            return
        mode = self.project.hierarchy_mode
        if mode == Project.HIERARCHY_FULL:
            if not (self.tower_id and self.floor_id and self.unit_id):
                raise ValidationError(
                    "This project uses the full Tower → Floor → Unit hierarchy — "
                    "tower, floor, and unit are all required."
                )
        elif mode == Project.HIERARCHY_DIRECT_TASK:
            if self.tower_id or self.floor_id or self.unit_id:
                raise ValidationError(
                    "This project is in Direct-to-Task mode — tasks can't be "
                    "attached to a tower, floor, or unit."
                )

    def recalculate_progress_from_checklist(self):
        items = list(TaskChecklistItem.objects.filter(task=self))
        if not items:
            return
        completed = sum(1 for i in items if i.completed)
        self.progress = round((completed / len(items)) * 100)
        self.save(update_fields=["progress"])


class TaskChecklistItem(models.Model):
    task = models.ForeignKey(Task, related_name="checklist_items", on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    completed = models.BooleanField(default=False)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.title


class TaskComment(models.Model):
    task = models.ForeignKey(Task, related_name="comments", on_delete=models.CASCADE)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="task_comments", null=True, blank=True, on_delete=models.SET_NULL
    )
    text = models.TextField()
    date = models.DateField(auto_now_add=True)

    class Meta:
        ordering = ["date", "id"]

    def __str__(self):
        return f"Comment by {self.author} on {self.task_id}"


class TaskChatMessage(models.Model):
    task = models.ForeignKey(Task, related_name="chat_messages", on_delete=models.CASCADE)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="task_chat_messages", null=True, blank=True, on_delete=models.SET_NULL
    )
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"Chat message by {self.author} on task {self.task_id}"
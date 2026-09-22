from django.conf import settings
from django.db import models
from apps.common.models.base import TimeStampedModel


class TaskStatus(models.TextChoices):
    OPEN = "OPEN", "Open"
    DONE = "DONE", "Done"
    CANCELLED = "CANCELLED", "Cancelled"


class Task(TimeStampedModel):
    """
    Follow-up reminder attached to a lead, e.g. "call back Thursday".
    Surfaced in the agent's "My Tasks" panel and swept by a Celery Beat
    job that fires reminder notifications as due_at approaches.
    """

    inquiry = models.ForeignKey(
        "inquiries.Inquiry",
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    assigned_agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="crm_tasks",
    )
    title = models.CharField(max_length=255)
    due_at = models.DateTimeField(db_index=True)
    status = models.CharField(
        max_length=20,
        choices=TaskStatus.choices,
        default=TaskStatus.OPEN,
        db_index=True,
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    reminder_sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "crm_tasks"
        ordering = ["due_at"]
        indexes = [
            models.Index(fields=["assigned_agent", "status", "due_at"], name="task_agent_status_due_idx"),
        ]

    def __str__(self):
        return f"{self.title} ({self.status}) - {self.inquiry.inquiry_number}"

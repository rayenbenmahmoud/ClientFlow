from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.models import TimeStampedModel


class Interaction(TimeStampedModel):
    """A logged call, meeting, email or note linked to one or more CRM records."""

    class Type(models.TextChoices):
        CALL = "call", "Call"
        MEETING = "meeting", "Meeting"
        EMAIL = "email", "Email"
        NOTE = "note", "Note"

    type = models.CharField(max_length=10, choices=Type.choices, default=Type.NOTE)
    subject = models.CharField(max_length=200)
    notes = models.TextField(blank=True)
    occurred_at = models.DateTimeField(default=timezone.now)
    contact = models.ForeignKey(
        "crm.Contact", null=True, blank=True, on_delete=models.CASCADE, related_name="interactions"
    )
    company = models.ForeignKey(
        "crm.Company", null=True, blank=True, on_delete=models.CASCADE, related_name="interactions"
    )
    deal = models.ForeignKey("sales.Deal", null=True, blank=True, on_delete=models.CASCADE, related_name="interactions")
    lead = models.ForeignKey("sales.Lead", null=True, blank=True, on_delete=models.CASCADE, related_name="interactions")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    is_system = models.BooleanField(default=False, help_text="Created automatically by a workflow; read-only.")

    class Meta:
        ordering = ["-occurred_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(contact__isnull=False)
                | Q(company__isnull=False)
                | Q(deal__isnull=False)
                | Q(lead__isnull=False),
                name="interaction_has_target",
            )
        ]
        indexes = [models.Index(fields=["-occurred_at"])]

    def __str__(self):
        return f"{self.get_type_display()}: {self.subject}"


class Task(TimeStampedModel):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        DONE = "done", "Done"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    due_date = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="tasks")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    lead = models.ForeignKey("sales.Lead", null=True, blank=True, on_delete=models.CASCADE, related_name="tasks")
    deal = models.ForeignKey("sales.Deal", null=True, blank=True, on_delete=models.CASCADE, related_name="tasks")
    contact = models.ForeignKey("crm.Contact", null=True, blank=True, on_delete=models.SET_NULL, related_name="tasks")
    completed_at = models.DateTimeField(null=True, blank=True, editable=False)
    auto_created = models.BooleanField(default=False, help_text="Created by a workflow rule.")

    class Meta:
        ordering = ["due_date", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(Q(status="done") & Q(completed_at__isnull=False))
                | (Q(status="open") & Q(completed_at__isnull=True)),
                name="task_completed_at_matches_status",
            )
        ]
        indexes = [
            models.Index(fields=["assignee", "status", "due_date"]),
            models.Index(fields=["due_date"]),
        ]

    @property
    def is_overdue(self) -> bool:
        return self.status == self.Status.OPEN and self.due_date < timezone.localdate()

    def __str__(self):
        return self.title


class Notification(models.Model):
    class Kind(models.TextChoices):
        DEAL_STAGE = "deal_stage", "Deal stage changed"
        LEAD_OVERDUE = "lead_overdue", "Lead follow-up overdue"
        GENERAL = "general", "General"

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.GENERAL)
    title = models.CharField(max_length=200)
    message = models.CharField(max_length=500, blank=True)
    link = models.CharField(max_length=200, blank=True, help_text="Frontend route, e.g. /deals/12")
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["recipient", "read_at", "-created_at"])]

    def __str__(self):
        return self.title

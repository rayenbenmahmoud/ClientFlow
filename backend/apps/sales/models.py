from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.models import TimeStampedModel
from apps.core.validators import PHONE_VALIDATOR


class Lead(TimeStampedModel):
    class Source(models.TextChoices):
        WEBSITE = "website", "Website"
        REFERRAL = "referral", "Referral"
        COLD_OUTREACH = "cold_outreach", "Cold outreach"
        EVENT = "event", "Event"
        SOCIAL = "social", "Social media"
        PARTNER = "partner", "Partner"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        NEW = "new", "New"
        CONTACTED = "contacted", "Contacted"
        QUALIFIED = "qualified", "Qualified"
        UNQUALIFIED = "unqualified", "Unqualified"
        CONVERTED = "converted", "Converted"

    OPEN_STATUSES = (Status.NEW, Status.CONTACTED, Status.QUALIFIED)

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True, validators=[PHONE_VALIDATOR])
    company_name = models.CharField(max_length=200, blank=True)
    job_title = models.CharField(max_length=120, blank=True)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.OTHER)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="leads")
    follow_up_date = models.DateField(null=True, blank=True)
    estimated_value = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)]
    )
    notes = models.TextField(blank=True)
    overdue_flagged_at = models.DateTimeField(null=True, blank=True, editable=False)
    converted_deal = models.OneToOneField(
        "sales.Deal", null=True, blank=True, editable=False, on_delete=models.SET_NULL, related_name="source_lead"
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(estimated_value__isnull=True) | Q(estimated_value__gte=0),
                name="lead_estimated_value_non_negative",
            ),
        ]
        indexes = [
            models.Index(fields=["owner", "status"]),
            models.Index(fields=["status", "follow_up_date"]),
            models.Index(fields=["source"]),
        ]

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def is_overdue(self) -> bool:
        return bool(
            self.follow_up_date and self.status in self.OPEN_STATUSES and self.follow_up_date < timezone.localdate()
        )

    def __str__(self):
        return self.full_name


class Deal(TimeStampedModel):
    class Stage(models.TextChoices):
        NEW = "new", "New"
        QUALIFIED = "qualified", "Qualified"
        PROPOSAL = "proposal", "Proposal"
        NEGOTIATION = "negotiation", "Negotiation"
        WON = "won", "Won"
        LOST = "lost", "Lost"

    OPEN_STAGES = (Stage.NEW, Stage.QUALIFIED, Stage.PROPOSAL, Stage.NEGOTIATION)
    CLOSED_STAGES = (Stage.WON, Stage.LOST)

    # Server-side source of truth for the pipeline. A deal can move one step forward or back,
    # be lost from any open stage, be won only from Negotiation, and a lost deal can be reopened.
    ALLOWED_TRANSITIONS = {
        Stage.NEW: (Stage.QUALIFIED, Stage.LOST),
        Stage.QUALIFIED: (Stage.NEW, Stage.PROPOSAL, Stage.LOST),
        Stage.PROPOSAL: (Stage.QUALIFIED, Stage.NEGOTIATION, Stage.LOST),
        Stage.NEGOTIATION: (Stage.PROPOSAL, Stage.WON, Stage.LOST),
        Stage.WON: (),
        Stage.LOST: (Stage.NEW,),
    }

    title = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    stage = models.CharField(max_length=20, choices=Stage.choices, default=Stage.NEW)
    expected_close_date = models.DateField(null=True, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="deals")
    company = models.ForeignKey("crm.Company", on_delete=models.PROTECT, related_name="deals")
    contact = models.ForeignKey("crm.Contact", null=True, blank=True, on_delete=models.SET_NULL, related_name="deals")
    lost_reason = models.TextField(blank=True)
    closed_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gte=0), name="deal_amount_non_negative"),
            models.CheckConstraint(condition=~Q(stage="lost") | ~Q(lost_reason=""), name="deal_lost_requires_reason"),
            models.CheckConstraint(
                condition=(Q(stage__in=["won", "lost"]) & Q(closed_at__isnull=False))
                | (~Q(stage__in=["won", "lost"]) & Q(closed_at__isnull=True)),
                name="deal_closed_at_matches_stage",
            ),
        ]
        indexes = [
            models.Index(fields=["stage"]),
            models.Index(fields=["owner", "stage"]),
            models.Index(fields=["expected_close_date"]),
        ]

    def __str__(self):
        return self.title


class DealStageHistory(models.Model):
    deal = models.ForeignKey(Deal, on_delete=models.CASCADE, related_name="stage_history")
    from_stage = models.CharField(max_length=20, blank=True, choices=Deal.Stage.choices)
    to_stage = models.CharField(max_length=20, choices=Deal.Stage.choices)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    changed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-changed_at", "-id"]
        verbose_name_plural = "deal stage history"
        indexes = [models.Index(fields=["deal", "-changed_at"])]

    def __str__(self):
        return f"{self.deal_id}: {self.from_stage or '-'} -> {self.to_stage}"

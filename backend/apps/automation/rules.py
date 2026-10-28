"""Workflow rules. Pure functions so they can be unit-tested and run from signals, commands or the API."""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.activities.models import Interaction, Notification, Task
from apps.sales.models import Deal, Lead

DEFAULT_FOLLOW_UP_DAYS = 2


def create_followup_task(lead: Lead) -> Task:
    """Rule 1: every new lead gets a follow-up task for its owner (defaults to +2 days)."""
    due = lead.follow_up_date
    if due is None:
        due = timezone.localdate() + timedelta(days=DEFAULT_FOLLOW_UP_DAYS)
        lead.follow_up_date = due
        lead.save(update_fields=["follow_up_date", "updated_at"])
    return Task.objects.create(
        title=f"Follow up with {lead.full_name}",
        description=f"Automatic follow-up for new lead from {lead.get_source_display().lower()}."
        + (f" Company: {lead.company_name}." if lead.company_name else ""),
        due_date=due,
        priority=Task.Priority.MEDIUM,
        assignee=lead.owner,
        lead=lead,
        auto_created=True,
    )


@transaction.atomic
def flag_overdue_leads() -> dict:
    """Rule 2: flag open leads whose follow-up date has passed and notify their owner once.

    Leads that are no longer overdue (date moved, qualified out, converted) are un-flagged.
    Returns counts so callers (command / API) can report what happened.
    """
    today = timezone.localdate()
    overdue = Lead.objects.filter(status__in=Lead.OPEN_STATUSES, follow_up_date__lt=today)

    newly = list(overdue.filter(overdue_flagged_at__isnull=True).select_related("owner"))
    now = timezone.now()
    for lead in newly:
        days = (today - lead.follow_up_date).days
        Notification.objects.create(
            recipient=lead.owner,
            kind=Notification.Kind.LEAD_OVERDUE,
            title="Lead follow-up overdue",
            message=f"{lead.full_name} was due {days} day{'s' if days != 1 else ''} ago.",
            link=f"/leads/{lead.pk}",
        )
    Lead.objects.filter(pk__in=[lead.pk for lead in newly]).update(overdue_flagged_at=now)

    cleared = (
        Lead.objects.filter(overdue_flagged_at__isnull=False)
        .exclude(pk__in=overdue.values("pk"))
        .update(overdue_flagged_at=None)
    )
    return {"flagged": len(newly), "cleared": cleared}


def notify_deal_stage_change(deal: Deal, from_stage: str, to_stage: str, actor) -> Notification:
    """Rule 3a: tell the deal owner when the deal changes stage."""
    by = f" by {actor.display_name}" if actor else ""
    return Notification.objects.create(
        recipient=deal.owner,
        kind=Notification.Kind.DEAL_STAGE,
        title=f"Deal moved to {Deal.Stage(to_stage).label}",
        message=f"'{deal.title}' moved from {Deal.Stage(from_stage).label} to {Deal.Stage(to_stage).label}{by}.",
        link=f"/deals/{deal.pk}",
    )


def log_deal_stage_change(deal: Deal, from_stage: str, to_stage: str, actor) -> Interaction:
    """Rule 3b: leave a read-only note on the deal timeline."""
    return Interaction.objects.create(
        type=Interaction.Type.NOTE,
        subject=f"Stage changed: {Deal.Stage(from_stage).label} → {Deal.Stage(to_stage).label}",
        deal=deal,
        company=deal.company,
        contact=deal.contact,
        created_by=actor,
        is_system=True,
    )

"""Business operations that touch several records. Each runs in a single transaction."""

from django.db import transaction
from django.db.models.functions import Lower
from django.utils import timezone

from apps.crm.models import Company, Contact

from .models import Deal, DealStageHistory, Lead
from .signals import deal_stage_changed


class DealStageError(Exception):
    """Raised when a requested stage change is not allowed."""


class LeadConversionError(Exception):
    """Raised when a lead cannot be converted."""


@transaction.atomic
def create_deal(*, actor=None, **fields) -> Deal:
    """Create a deal in the New stage together with its first history entry."""
    deal = Deal.objects.create(stage=Deal.Stage.NEW, **fields)
    DealStageHistory.objects.create(deal=deal, from_stage="", to_stage=Deal.Stage.NEW, changed_by=actor)
    return deal


@transaction.atomic
def change_deal_stage(deal: Deal, to_stage: str, *, actor, lost_reason: str = "") -> Deal:
    """Validate and apply a stage transition, record history and emit `deal_stage_changed`.

    The row is locked so two concurrent requests cannot both apply a transition from the same stage.
    If any workflow receiver raises, the whole change (stage + history + side effects) rolls back.
    """
    deal = Deal.objects.select_for_update().get(pk=deal.pk)
    from_stage = deal.stage

    if to_stage not in Deal.Stage.values:
        raise DealStageError(f"Unknown stage '{to_stage}'.")
    if to_stage == from_stage:
        raise DealStageError(f"Deal is already in the {Deal.Stage(from_stage).label} stage.")
    if to_stage not in Deal.ALLOWED_TRANSITIONS[from_stage]:
        allowed = ", ".join(Deal.Stage(s).label for s in Deal.ALLOWED_TRANSITIONS[from_stage]) or "none"
        raise DealStageError(
            f"Cannot move a deal from {Deal.Stage(from_stage).label} to {Deal.Stage(to_stage).label}. "
            f"Allowed: {allowed}."
        )
    lost_reason = (lost_reason or "").strip()
    if to_stage == Deal.Stage.LOST and not lost_reason:
        raise DealStageError("A reason is required when marking a deal as lost.")

    deal.stage = to_stage
    deal.closed_at = timezone.now() if to_stage in Deal.CLOSED_STAGES else None
    deal.lost_reason = lost_reason if to_stage == Deal.Stage.LOST else ""
    deal.save(update_fields=["stage", "closed_at", "lost_reason", "updated_at"])
    DealStageHistory.objects.create(deal=deal, from_stage=from_stage, to_stage=to_stage, changed_by=actor)

    deal_stage_changed.send(sender=Deal, deal=deal, from_stage=from_stage, to_stage=to_stage, actor=actor)
    return deal


@transaction.atomic
def convert_lead(lead: Lead, *, actor, deal_title: str, amount, expected_close_date=None) -> Deal:
    """Turn a lead into company + contact + deal and mark it converted - all or nothing."""
    from apps.activities.models import Interaction  # local import: activities depends on sales models

    lead = Lead.objects.select_for_update().get(pk=lead.pk)
    if lead.status == Lead.Status.CONVERTED:
        raise LeadConversionError("This lead has already been converted.")
    if lead.status == Lead.Status.UNQUALIFIED:
        raise LeadConversionError("Unqualified leads cannot be converted. Change the status first.")
    if not lead.company_name.strip():
        raise LeadConversionError("Add a company name to the lead before converting it.")

    company = Company.objects.annotate(n=Lower("name")).filter(n=lead.company_name.strip().lower()).first()
    if company is None:
        company = Company.objects.create(name=lead.company_name.strip(), owner=lead.owner)

    contact = None
    if lead.email:
        contact = Contact.objects.annotate(e=Lower("email")).filter(e=lead.email.lower()).first()
    if contact is None:
        contact = Contact.objects.create(
            first_name=lead.first_name,
            last_name=lead.last_name,
            email=lead.email.lower(),
            phone=lead.phone,
            job_title=lead.job_title,
            company=company,
            owner=lead.owner,
        )

    deal = create_deal(
        actor=actor,
        title=deal_title,
        amount=amount,
        expected_close_date=expected_close_date,
        owner=lead.owner,
        company=company,
        contact=contact,
    )

    lead.status = Lead.Status.CONVERTED
    lead.converted_deal = deal
    lead.overdue_flagged_at = None
    lead.save(update_fields=["status", "converted_deal", "overdue_flagged_at", "updated_at"])

    lead.tasks.filter(status="open", auto_created=True).update(status="done", completed_at=timezone.now())
    Interaction.objects.create(
        type=Interaction.Type.NOTE,
        subject=f"Lead converted to deal '{deal.title}'",
        deal=deal,
        company=company,
        contact=contact,
        lead=lead,
        created_by=actor,
        is_system=True,
    )
    return deal

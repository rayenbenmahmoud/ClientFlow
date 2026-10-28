from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.sales.models import Lead
from apps.sales.signals import deal_stage_changed

from . import rules


@receiver(post_save, sender=Lead, dispatch_uid="automation.lead_created")
def on_lead_created(sender, instance, created, raw=False, **kwargs):
    if created and not raw:
        rules.create_followup_task(instance)


@receiver(deal_stage_changed, dispatch_uid="automation.deal_stage_changed")
def on_deal_stage_changed(sender, deal, from_stage, to_stage, actor, **kwargs):
    rules.notify_deal_stage_change(deal, from_stage, to_stage, actor)
    rules.log_deal_stage_change(deal, from_stage, to_stage, actor)

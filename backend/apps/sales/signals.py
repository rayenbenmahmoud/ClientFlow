"""Domain events emitted by the sales app. The automation app subscribes to them."""

from django.dispatch import Signal

# kwargs: deal, from_stage, to_stage, actor
deal_stage_changed = Signal()

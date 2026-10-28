from decimal import Decimal

from django.db.models import Count, DecimalField, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.activities.models import Interaction, Task
from apps.core.permissions import is_privileged
from apps.sales.models import Deal, Lead

from .serializers import DashboardSerializer

ZERO = Value(Decimal("0"), output_field=DecimalField())


class DashboardView(APIView):
    """Aggregated numbers for the home dashboard. Reps see their own pipeline; managers/admins see the team's."""

    @extend_schema(responses=DashboardSerializer)
    def get(self, request):
        user = request.user
        today = timezone.localdate()
        month_start = timezone.make_aware(timezone.datetime(today.year, today.month, 1))

        leads, deals, tasks = Lead.objects.all(), Deal.objects.all(), Task.objects.all()
        if not is_privileged(user):
            leads, deals, tasks = leads.filter(owner=user), deals.filter(owner=user), tasks.filter(assignee=user)

        open_leads = leads.filter(status__in=Lead.OPEN_STATUSES)
        overdue_leads = open_leads.filter(follow_up_date__lt=today)
        open_deals = deals.filter(stage__in=Deal.OPEN_STAGES)
        won_month = deals.filter(stage=Deal.Stage.WON, closed_at__gte=month_start).aggregate(
            value=Coalesce(Sum("amount"), ZERO), count=Count("id")
        )
        open_tasks = tasks.filter(status=Task.Status.OPEN)

        kpis = {
            "open_leads": open_leads.count(),
            "overdue_leads": overdue_leads.count(),
            "active_deals": open_deals.count(),
            "pipeline_value": open_deals.aggregate(v=Coalesce(Sum("amount"), ZERO))["v"],
            "won_this_month_value": won_month["value"],
            "won_this_month_count": won_month["count"],
            "tasks_due_today": open_tasks.filter(due_date=today).count(),
            "tasks_overdue": open_tasks.filter(due_date__lt=today).count(),
            "tasks_open": open_tasks.count(),
        }

        by_stage = {
            row["stage"]: row
            for row in deals.values("stage").annotate(count=Count("id"), value=Coalesce(Sum("amount"), ZERO))
        }
        pipeline = [
            {
                "stage": s.value,
                "label": s.label,
                "count": by_stage.get(s.value, {}).get("count", 0),
                "value": by_stage.get(s.value, {}).get("value", Decimal("0")),
            }
            for s in Deal.Stage
        ]

        by_source = {r["source"]: r["count"] for r in open_leads.values("source").annotate(count=Count("id"))}
        leads_by_source = [
            {"source": s.value, "label": s.label, "count": by_source[s.value]}
            for s in Lead.Source
            if by_source.get(s.value)
        ]

        payload = {
            "scope": "all" if is_privileged(user) else "mine",
            "kpis": kpis,
            "pipeline": pipeline,
            "leads_by_source": leads_by_source,
            "upcoming_tasks": open_tasks.select_related("assignee", "lead", "deal", "contact").order_by(
                "due_date", "id"
            )[:8],
            "overdue_leads": overdue_leads.select_related("owner").order_by("follow_up_date")[:5],
            "recent_activities": Interaction.objects.select_related("contact", "company", "deal", "lead", "created_by")[
                :8
            ],
        }
        return Response(DashboardSerializer(payload, context={"request": request}).data)

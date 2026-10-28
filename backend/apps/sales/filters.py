from django.db.models import Q
from django.utils import timezone
from django_filters import rest_framework as filters

from .models import Deal, Lead


class LeadFilter(filters.FilterSet):
    overdue = filters.BooleanFilter(method="filter_overdue")
    follow_up_before = filters.DateFilter("follow_up_date", lookup_expr="lte")
    follow_up_after = filters.DateFilter("follow_up_date", lookup_expr="gte")

    class Meta:
        model = Lead
        fields = ["status", "source", "owner"]

    def filter_overdue(self, queryset, name, value):
        overdue = Q(status__in=Lead.OPEN_STATUSES, follow_up_date__lt=timezone.localdate())
        return queryset.filter(overdue) if value else queryset.exclude(overdue)


class DealFilter(filters.FilterSet):
    open = filters.BooleanFilter(method="filter_open")
    min_amount = filters.NumberFilter("amount", lookup_expr="gte")
    max_amount = filters.NumberFilter("amount", lookup_expr="lte")
    close_after = filters.DateFilter("expected_close_date", lookup_expr="gte")
    close_before = filters.DateFilter("expected_close_date", lookup_expr="lte")

    class Meta:
        model = Deal
        fields = ["stage", "owner", "company", "contact"]

    def filter_open(self, queryset, name, value):
        return queryset.filter(stage__in=Deal.OPEN_STAGES) if value else queryset.exclude(stage__in=Deal.OPEN_STAGES)

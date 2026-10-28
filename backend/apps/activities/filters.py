from django.db.models import Q
from django.utils import timezone
from django_filters import rest_framework as filters

from .models import Interaction, Notification, Task


class InteractionFilter(filters.FilterSet):
    occurred_after = filters.DateTimeFilter("occurred_at", lookup_expr="gte")
    occurred_before = filters.DateTimeFilter("occurred_at", lookup_expr="lte")

    class Meta:
        model = Interaction
        fields = ["type", "contact", "company", "deal", "lead", "created_by"]


class TaskFilter(filters.FilterSet):
    overdue = filters.BooleanFilter(method="filter_overdue")
    due_after = filters.DateFilter("due_date", lookup_expr="gte")
    due_before = filters.DateFilter("due_date", lookup_expr="lte")

    class Meta:
        model = Task
        fields = ["status", "priority", "assignee", "lead", "deal", "contact"]

    def filter_overdue(self, queryset, name, value):
        overdue = Q(status=Task.Status.OPEN, due_date__lt=timezone.localdate())
        return queryset.filter(overdue) if value else queryset.exclude(overdue)


class NotificationFilter(filters.FilterSet):
    unread = filters.BooleanFilter(method="filter_unread")

    class Meta:
        model = Notification
        fields = ["kind"]

    def filter_unread(self, queryset, name, value):
        return queryset.filter(read_at__isnull=value)

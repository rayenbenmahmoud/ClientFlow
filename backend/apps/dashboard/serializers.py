from rest_framework import serializers

from apps.activities.serializers import InteractionSerializer, TaskSerializer
from apps.sales.serializers import LeadSerializer


class KpiSerializer(serializers.Serializer):
    open_leads = serializers.IntegerField()
    overdue_leads = serializers.IntegerField()
    active_deals = serializers.IntegerField()
    pipeline_value = serializers.DecimalField(max_digits=14, decimal_places=2)
    won_this_month_value = serializers.DecimalField(max_digits=14, decimal_places=2)
    won_this_month_count = serializers.IntegerField()
    tasks_due_today = serializers.IntegerField()
    tasks_overdue = serializers.IntegerField()
    tasks_open = serializers.IntegerField()


class PipelineStageSerializer(serializers.Serializer):
    stage = serializers.CharField()
    label = serializers.CharField()
    count = serializers.IntegerField()
    value = serializers.DecimalField(max_digits=14, decimal_places=2)


class LeadSourceSerializer(serializers.Serializer):
    source = serializers.CharField()
    label = serializers.CharField()
    count = serializers.IntegerField()


class DashboardSerializer(serializers.Serializer):
    scope = serializers.ChoiceField(choices=["all", "mine"])
    kpis = KpiSerializer()
    pipeline = PipelineStageSerializer(many=True)
    leads_by_source = LeadSourceSerializer(many=True)
    upcoming_tasks = TaskSerializer(many=True)
    overdue_leads = LeadSerializer(many=True)
    recent_activities = InteractionSerializer(many=True)

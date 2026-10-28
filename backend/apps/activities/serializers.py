from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from apps.core.serializers import OwnerAssignmentMixin

from .models import Interaction, Notification, Task


class InteractionSerializer(serializers.ModelSerializer):
    type_label = serializers.CharField(source="get_type_display", read_only=True)
    contact_name = serializers.CharField(source="contact.full_name", read_only=True, allow_null=True)
    company_name = serializers.CharField(source="company.name", read_only=True, allow_null=True)
    deal_title = serializers.CharField(source="deal.title", read_only=True, allow_null=True)
    lead_name = serializers.CharField(source="lead.full_name", read_only=True, allow_null=True)
    created_by_name = serializers.CharField(source="created_by.display_name", read_only=True, allow_null=True)

    class Meta:
        model = Interaction
        fields = [
            "id",
            "type",
            "type_label",
            "subject",
            "notes",
            "occurred_at",
            "contact",
            "contact_name",
            "company",
            "company_name",
            "deal",
            "deal_title",
            "lead",
            "lead_name",
            "created_by",
            "created_by_name",
            "is_system",
            "created_at",
        ]
        read_only_fields = ["created_by", "is_system", "created_at"]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        targets = ["contact", "company", "deal", "lead"]
        merged = {t: attrs.get(t, getattr(self.instance, t, None)) for t in targets}
        if not any(merged.values()):
            raise serializers.ValidationError(
                {"non_field_errors": ["Link the interaction to a contact, company, lead or deal."]}
            )
        return attrs

    def validate_occurred_at(self, value):
        if value > timezone.now() + timedelta(minutes=5):
            raise serializers.ValidationError("An interaction cannot be logged in the future.")
        return value


class TaskSerializer(OwnerAssignmentMixin, serializers.ModelSerializer):
    owner_field = "assignee"

    assignee_name = serializers.CharField(source="assignee.display_name", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    priority_label = serializers.CharField(source="get_priority_display", read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    lead_name = serializers.CharField(source="lead.full_name", read_only=True, allow_null=True)
    deal_title = serializers.CharField(source="deal.title", read_only=True, allow_null=True)
    contact_name = serializers.CharField(source="contact.full_name", read_only=True, allow_null=True)

    class Meta:
        model = Task
        fields = [
            "id",
            "title",
            "description",
            "due_date",
            "status",
            "status_label",
            "priority",
            "priority_label",
            "assignee",
            "assignee_name",
            "lead",
            "lead_name",
            "deal",
            "deal_title",
            "contact",
            "contact_name",
            "is_overdue",
            "completed_at",
            "auto_created",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["status", "completed_at", "auto_created", "created_at", "updated_at"]
        extra_kwargs = {"assignee": {"required": False}}


class NotificationSerializer(serializers.ModelSerializer):
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)
    is_read = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ["id", "kind", "kind_label", "title", "message", "link", "is_read", "read_at", "created_at"]
        read_only_fields = fields

    def get_is_read(self, obj) -> bool:
        return obj.read_at is not None

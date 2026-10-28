from django.utils import timezone
from rest_framework import serializers

from apps.core.serializers import OwnerAssignmentMixin

from . import services
from .models import Deal, DealStageHistory, Lead


class LeadSerializer(OwnerAssignmentMixin, serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    owner_name = serializers.CharField(source="owner.display_name", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    source_label = serializers.CharField(source="get_source_display", read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = Lead
        fields = [
            "id",
            "first_name",
            "last_name",
            "full_name",
            "email",
            "phone",
            "company_name",
            "job_title",
            "source",
            "source_label",
            "status",
            "status_label",
            "owner",
            "owner_name",
            "follow_up_date",
            "estimated_value",
            "notes",
            "is_overdue",
            "overdue_flagged_at",
            "converted_deal",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["overdue_flagged_at", "converted_deal", "created_at", "updated_at"]
        extra_kwargs = {"owner": {"required": False}}

    def validate_email(self, value):
        return value.strip().lower()

    def validate_status(self, value):
        if value == Lead.Status.CONVERTED and (self.instance is None or self.instance.status != value):
            raise serializers.ValidationError("Use the convert action to convert a lead into a deal.")
        if (
            self.instance is not None
            and self.instance.status == Lead.Status.CONVERTED
            and value != self.instance.status
        ):
            raise serializers.ValidationError("A converted lead can no longer change status.")
        return value

    def validate_follow_up_date(self, value):
        changed = self.instance is None or self.instance.follow_up_date != value
        if value and changed and value < timezone.localdate():
            raise serializers.ValidationError("Follow-up date cannot be in the past.")
        return value


class ConvertLeadSerializer(serializers.Serializer):
    deal_title = serializers.CharField(max_length=200)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0)
    expected_close_date = serializers.DateField(required=False, allow_null=True)


class DealSerializer(OwnerAssignmentMixin, serializers.ModelSerializer):
    owner_name = serializers.CharField(source="owner.display_name", read_only=True)
    company_name = serializers.CharField(source="company.name", read_only=True)
    contact_name = serializers.CharField(source="contact.full_name", read_only=True, allow_null=True)
    stage_label = serializers.CharField(source="get_stage_display", read_only=True)

    class Meta:
        model = Deal
        fields = [
            "id",
            "title",
            "amount",
            "stage",
            "stage_label",
            "expected_close_date",
            "owner",
            "owner_name",
            "company",
            "company_name",
            "contact",
            "contact_name",
            "lost_reason",
            "closed_at",
            "created_at",
            "updated_at",
        ]
        # The stage is only changed through POST /deals/{id}/change-stage/ so every move is validated and audited.
        read_only_fields = ["stage", "lost_reason", "closed_at", "created_at", "updated_at"]
        extra_kwargs = {"owner": {"required": False}, "contact": {"required": False, "allow_null": True}}

    def validate(self, attrs):
        attrs = super().validate(attrs)
        company = attrs.get("company", getattr(self.instance, "company", None))
        contact = attrs.get("contact", getattr(self.instance, "contact", None))
        if contact and company and contact.company_id and contact.company_id != company.id:
            raise serializers.ValidationError({"contact": "This contact does not belong to the selected company."})
        return attrs

    def create(self, validated_data):
        return services.create_deal(actor=self.context["request"].user, **validated_data)


class ChangeStageSerializer(serializers.Serializer):
    stage = serializers.ChoiceField(choices=Deal.Stage.choices)
    lost_reason = serializers.CharField(required=False, allow_blank=True)


class DealStageHistorySerializer(serializers.ModelSerializer):
    from_stage_label = serializers.CharField(source="get_from_stage_display", read_only=True)
    to_stage_label = serializers.CharField(source="get_to_stage_display", read_only=True)
    changed_by_name = serializers.CharField(source="changed_by.display_name", read_only=True, allow_null=True)

    class Meta:
        model = DealStageHistory
        fields = [
            "id",
            "from_stage",
            "from_stage_label",
            "to_stage",
            "to_stage_label",
            "changed_by_name",
            "changed_at",
        ]
        read_only_fields = fields


class PipelineColumnSerializer(serializers.Serializer):
    stage = serializers.CharField()
    label = serializers.CharField()
    count = serializers.IntegerField()
    total = serializers.DecimalField(max_digits=14, decimal_places=2)
    deals = DealSerializer(many=True)

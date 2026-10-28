from decimal import Decimal

from django.db.models import Count, DecimalField, Sum, Value
from django.db.models.functions import Coalesce
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.core.csv_export import CsvExportMixin
from apps.core.permissions import CrmObjectPermission, OwnerScopedMixin

from . import services
from .filters import DealFilter, LeadFilter
from .models import Deal, Lead
from .serializers import (
    ChangeStageSerializer,
    ConvertLeadSerializer,
    DealSerializer,
    DealStageHistorySerializer,
    LeadSerializer,
    PipelineColumnSerializer,
)

PIPELINE_CARD_LIMIT = 50


class LeadViewSet(OwnerScopedMixin, CsvExportMixin, viewsets.ModelViewSet):
    serializer_class = LeadSerializer
    permission_classes = [CrmObjectPermission]
    filterset_class = LeadFilter
    search_fields = ["first_name", "last_name", "email", "company_name", "phone"]
    ordering_fields = ["first_name", "last_name", "company_name", "status", "source", "follow_up_date", "created_at"]
    ordering = ["-created_at"]
    rep_can_delete_own = True
    csv_basename = "leads"
    csv_fields = [
        ("ID", "id"),
        ("First name", "first_name"),
        ("Last name", "last_name"),
        ("Email", "email"),
        ("Phone", "phone"),
        ("Company", "company_name"),
        ("Source", "get_source_display"),
        ("Status", "get_status_display"),
        ("Owner", "owner.display_name"),
        ("Follow-up date", "follow_up_date"),
        ("Overdue", "is_overdue"),
        ("Estimated value", "estimated_value"),
        ("Created", "created_at"),
    ]

    def get_queryset(self):
        return self.scope(Lead.objects.select_related("owner"))

    @extend_schema(request=ConvertLeadSerializer, responses={201: DealSerializer})
    @action(detail=True, methods=["post"])
    def convert(self, request, pk=None):
        """Convert the lead into a company, contact and deal in one transaction."""
        lead = self.get_object()
        serializer = ConvertLeadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            deal = services.convert_lead(lead, actor=request.user, **serializer.validated_data)
        except services.LeadConversionError as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        return Response(
            DealSerializer(deal, context=self.get_serializer_context()).data, status=status.HTTP_201_CREATED
        )


class DealViewSet(OwnerScopedMixin, CsvExportMixin, viewsets.ModelViewSet):
    serializer_class = DealSerializer
    permission_classes = [CrmObjectPermission]
    filterset_class = DealFilter
    search_fields = ["title", "company__name", "contact__first_name", "contact__last_name"]
    ordering_fields = ["title", "amount", "stage", "expected_close_date", "created_at", "updated_at", "company__name"]
    ordering = ["-updated_at"]
    csv_basename = "deals"
    csv_fields = [
        ("ID", "id"),
        ("Title", "title"),
        ("Amount", "amount"),
        ("Stage", "get_stage_display"),
        ("Expected close", "expected_close_date"),
        ("Company", "company.name"),
        ("Contact", "contact.full_name"),
        ("Owner", "owner.display_name"),
        ("Lost reason", "lost_reason"),
        ("Closed at", "closed_at"),
        ("Created", "created_at"),
    ]

    def get_queryset(self):
        return self.scope(Deal.objects.select_related("owner", "company", "contact"))

    @extend_schema(request=ChangeStageSerializer, responses=DealSerializer)
    @action(detail=True, methods=["post"], url_path="change-stage")
    def change_stage(self, request, pk=None):
        """Move the deal to another stage (validated against the allowed transitions)."""
        deal = self.get_object()
        serializer = ChangeStageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            deal = services.change_deal_stage(
                deal,
                serializer.validated_data["stage"],
                actor=request.user,
                lost_reason=serializer.validated_data.get("lost_reason", ""),
            )
        except services.DealStageError as exc:
            raise ValidationError({"stage": [str(exc)]}) from exc
        deal = self.get_queryset().get(pk=deal.pk)
        return Response(DealSerializer(deal, context=self.get_serializer_context()).data)

    @extend_schema(responses=DealStageHistorySerializer(many=True))
    @action(detail=True, methods=["get"], pagination_class=None)
    def history(self, request, pk=None):
        deal = self.get_object()
        entries = deal.stage_history.select_related("changed_by")
        return Response(DealStageHistorySerializer(entries, many=True).data)

    @extend_schema(responses=PipelineColumnSerializer(many=True), filters=True)
    @action(detail=False, methods=["get"], pagination_class=None)
    def pipeline(self, request):
        """Deals grouped by stage for the Kanban board. Honours the same filters/search as the list."""
        queryset = self.filter_queryset(self.get_queryset()).order_by("-updated_at")
        totals = {
            row["stage"]: row
            for row in queryset.order_by()
            .values("stage")
            .annotate(
                count=Count("id"),
                total=Coalesce(Sum("amount"), Value(Decimal("0")), output_field=DecimalField()),
            )
        }
        columns = []
        for stage in Deal.Stage:
            row = totals.get(stage.value, {"count": 0, "total": Decimal("0")})
            ordering = "-closed_at" if stage in Deal.CLOSED_STAGES else "-updated_at"
            deals = queryset.filter(stage=stage.value).order_by(ordering)[:PIPELINE_CARD_LIMIT]
            columns.append(
                {
                    "stage": stage.value,
                    "label": stage.label,
                    "count": row["count"],
                    "total": row["total"],
                    "deals": deals,
                }
            )
        return Response(PipelineColumnSerializer(columns, many=True, context=self.get_serializer_context()).data)

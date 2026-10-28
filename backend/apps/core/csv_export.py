"""CSV export mixin with spreadsheet-formula-injection protection."""

import csv
import re
from datetime import date, datetime

from django.http import HttpResponse
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action

_DANGEROUS_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


# International phone numbers ("+1 555-0100", "+44 (0) 20 7946 0000") start with "+" but contain only digits and
# separators, so they cannot call functions or reference cells. Everything else with a risky prefix is neutralised.
_PHONE_LIKE = re.compile(r"^\+\d[\d\s().-]*$")


def safe_cell(value):
    """Neutralise cells that spreadsheets would interpret as formulas (CSV injection)."""
    if isinstance(value, str) and value.startswith(_DANGEROUS_PREFIXES) and not _PHONE_LIKE.match(value):
        return "'" + value
    return value


def _resolve(obj, accessor):
    if callable(accessor):
        return accessor(obj)
    for part in accessor.split("."):
        if obj is None:
            return ""
        obj = getattr(obj, part)
        if callable(obj):
            obj = obj()
    return "" if obj is None else obj


def _format(value):
    if isinstance(value, datetime):
        return timezone.localtime(value).strftime("%Y-%m-%d %H:%M")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, bool):
        return "yes" if value else "no"
    return value


class CsvExportMixin:
    """Adds GET <list>/export/ honouring the same search, filters, ordering and permissions as the list."""

    csv_fields: list[tuple[str, object]] = []
    csv_basename = "export"

    @extend_schema(responses={(200, "text/csv"): OpenApiTypes.STR}, filters=True)
    @action(detail=False, methods=["get"], url_path="export", pagination_class=None)
    def export(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        stamp = timezone.localdate().isoformat()
        response["Content-Disposition"] = f'attachment; filename="{self.csv_basename}-{stamp}.csv"'
        response.write("\ufeff")  # BOM so Excel detects UTF-8
        writer = csv.writer(response)
        writer.writerow([header for header, _ in self.csv_fields])
        for obj in queryset:
            writer.writerow([safe_cell(_format(_resolve(obj, acc))) for _, acc in self.csv_fields])
        return response

from django.db.models import Count
from rest_framework import viewsets

from apps.core.csv_export import CsvExportMixin
from apps.core.permissions import CrmObjectPermission

from .filters import CompanyFilter, ContactFilter
from .models import Company, Contact, Tag
from .serializers import CompanySerializer, ContactSerializer, TagSerializer


class TagViewSet(viewsets.ModelViewSet):
    """Tags are shared labels. Anyone can create one; deleting is limited to managers/admins."""

    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [CrmObjectPermission]
    pagination_class = None
    search_fields = ["name"]


class CompanyViewSet(CsvExportMixin, viewsets.ModelViewSet):
    serializer_class = CompanySerializer
    permission_classes = [CrmObjectPermission]
    filterset_class = CompanyFilter
    search_fields = ["name", "industry", "city", "email", "website"]
    ordering_fields = ["name", "industry", "city", "created_at", "contact_count", "deal_count"]
    ordering = ["name"]
    csv_basename = "companies"
    csv_fields = [
        ("ID", "id"),
        ("Name", "name"),
        ("Industry", "industry"),
        ("Website", "website"),
        ("Email", "email"),
        ("Phone", "phone"),
        ("Address", "address"),
        ("City", "city"),
        ("Country", "country"),
        ("Owner", "owner.display_name"),
        ("Contacts", "contact_count"),
        ("Deals", "deal_count"),
        ("Created", "created_at"),
    ]

    def get_queryset(self):
        return Company.objects.select_related("owner").annotate(
            contact_count=Count("contacts", distinct=True), deal_count=Count("deals", distinct=True)
        )


class ContactViewSet(CsvExportMixin, viewsets.ModelViewSet):
    serializer_class = ContactSerializer
    permission_classes = [CrmObjectPermission]
    filterset_class = ContactFilter
    search_fields = ["first_name", "last_name", "email", "phone", "job_title", "company__name"]
    ordering_fields = ["first_name", "last_name", "email", "company__name", "created_at"]
    ordering = ["last_name", "first_name"]
    csv_basename = "contacts"
    csv_fields = [
        ("ID", "id"),
        ("First name", "first_name"),
        ("Last name", "last_name"),
        ("Email", "email"),
        ("Phone", "phone"),
        ("Job title", "job_title"),
        ("Company", "company.name"),
        ("Tags", lambda c: ", ".join(t.name for t in c.tags.all())),
        ("Owner", "owner.display_name"),
        ("Created", "created_at"),
    ]

    def get_queryset(self):
        return Contact.objects.select_related("company", "owner").prefetch_related("tags")

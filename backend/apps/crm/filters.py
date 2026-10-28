from django_filters import rest_framework as filters

from .models import Company, Contact


class CompanyFilter(filters.FilterSet):
    class Meta:
        model = Company
        fields = ["industry", "city", "country", "owner"]


class ContactFilter(filters.FilterSet):
    tag = filters.NumberFilter(field_name="tags__id", distinct=True)

    class Meta:
        model = Contact
        fields = ["company", "owner"]

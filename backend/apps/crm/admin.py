from django.contrib import admin

from .models import Company, Contact, Tag

admin.site.register(Tag)


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "industry", "city", "owner")
    search_fields = ("name", "industry")


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ("full_name", "email", "company", "owner")
    search_fields = ("first_name", "last_name", "email")

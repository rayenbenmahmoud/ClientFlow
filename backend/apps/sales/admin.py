from django.contrib import admin

from .models import Deal, DealStageHistory, Lead


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("full_name", "company_name", "status", "owner", "follow_up_date")
    list_filter = ("status", "source")
    search_fields = ("first_name", "last_name", "company_name", "email")


@admin.register(Deal)
class DealAdmin(admin.ModelAdmin):
    list_display = ("title", "company", "amount", "stage", "owner")
    list_filter = ("stage",)
    search_fields = ("title", "company__name")


admin.site.register(DealStageHistory)

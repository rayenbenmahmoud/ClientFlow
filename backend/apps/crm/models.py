from django.conf import settings
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower

from apps.core.models import TimeStampedModel
from apps.core.validators import HEX_COLOR_VALIDATOR, PHONE_VALIDATOR


class Tag(TimeStampedModel):
    name = models.CharField(max_length=50)
    color = models.CharField(max_length=7, default="#64748b", validators=[HEX_COLOR_VALIDATOR])

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(Lower("name"), name="uniq_tag_name_ci")]

    def __str__(self):
        return self.name


class Company(TimeStampedModel):
    name = models.CharField(max_length=200)
    industry = models.CharField(max_length=100, blank=True)
    website = models.URLField(blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True, validators=[PHONE_VALIDATOR])
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="owned_companies"
    )

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "companies"
        constraints = [models.UniqueConstraint(Lower("name"), name="uniq_company_name_ci")]
        indexes = [models.Index(fields=["industry"]), models.Index(fields=["city"])]

    def __str__(self):
        return self.name


class Contact(TimeStampedModel):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True, validators=[PHONE_VALIDATOR])
    job_title = models.CharField(max_length=120, blank=True)
    company = models.ForeignKey(Company, null=True, blank=True, on_delete=models.SET_NULL, related_name="contacts")
    notes = models.TextField(blank=True)
    tags = models.ManyToManyField(Tag, blank=True, related_name="contacts")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="owned_contacts"
    )

    class Meta:
        ordering = ["last_name", "first_name"]
        constraints = [models.UniqueConstraint(Lower("email"), condition=~Q(email=""), name="uniq_contact_email_ci")]
        indexes = [models.Index(fields=["last_name", "first_name"])]

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def __str__(self):
        return self.full_name

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.crm.models import Company, Contact
from apps.sales import services
from apps.sales.models import Deal, Lead

PASSWORD = "Sup3r-Secret-Test-Pw"


def make_user(username, role, **extra):
    return User.objects.create_user(
        username=username,
        email=f"{username}@demo.test",
        password=PASSWORD,
        role=role,
        first_name=username.capitalize(),
        last_name="Tester",
        **extra,
    )


@pytest.fixture
def admin(db):
    return make_user("admin", Role.ADMIN)


@pytest.fixture
def manager(db):
    return make_user("manager", Role.MANAGER)


@pytest.fixture
def rep(db):
    return make_user("rep", Role.SALES_REP)


@pytest.fixture
def rep2(db):
    return make_user("rep2", Role.SALES_REP)


def client_for(user):
    client = APIClient()
    if user is not None:
        client.force_authenticate(user)
    return client


@pytest.fixture
def anon():
    return client_for(None)


@pytest.fixture
def admin_api(admin):
    return client_for(admin)


@pytest.fixture
def manager_api(manager):
    return client_for(manager)


@pytest.fixture
def rep_api(rep):
    return client_for(rep)


@pytest.fixture
def rep2_api(rep2):
    return client_for(rep2)


@pytest.fixture
def company(db):
    return Company.objects.create(name="Acme Landscaping", industry="Landscaping", city="Springfield")


@pytest.fixture
def contact(company):
    return Contact.objects.create(first_name="Ada", last_name="Lovelace", email="ada@acme.example", company=company)


@pytest.fixture
def make_lead(db):
    def _make(owner, **kw):
        defaults = dict(
            first_name="Lena",
            last_name="Prospect",
            email="",
            company_name="Prospect Co",
            source=Lead.Source.WEBSITE,
            follow_up_date=timezone.localdate() + timedelta(days=3),
        )
        defaults.update(kw)
        return Lead.objects.create(owner=owner, **defaults)

    return _make


@pytest.fixture
def make_deal(company, contact):
    def _make(owner, stage=Deal.Stage.NEW, **kw):
        defaults = dict(title="Website redesign", amount="5000.00", company=company, contact=contact)
        defaults.update(kw)
        deal = services.create_deal(actor=owner, owner=owner, **defaults)
        path = {
            Deal.Stage.NEW: [],
            Deal.Stage.QUALIFIED: ["qualified"],
            Deal.Stage.PROPOSAL: ["qualified", "proposal"],
            Deal.Stage.NEGOTIATION: ["qualified", "proposal", "negotiation"],
            Deal.Stage.WON: ["qualified", "proposal", "negotiation", "won"],
        }
        for step in path.get(stage, []):
            deal = services.change_deal_stage(deal, step, actor=owner)
        if stage == Deal.Stage.LOST:
            deal = services.change_deal_stage(deal, "lost", actor=owner, lost_reason="Budget")
        return deal

    return _make


def results(response):
    """Return the list of items from a paginated or plain list response."""
    data = response.json()
    return data["results"] if isinstance(data, dict) and "results" in data else data

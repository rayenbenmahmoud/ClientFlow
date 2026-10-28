from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.db import IntegrityError
from django.utils import timezone

from apps.activities.models import Interaction, Notification, Task
from apps.automation import rules
from apps.crm.models import Company, Contact
from apps.sales import services
from apps.sales.models import Deal
from tests.conftest import results

pytestmark = pytest.mark.django_db
today = timezone.localdate


# ---- Rule 1: follow-up task ----
def test_creating_a_lead_creates_followup_task_for_owner(rep_api, rep):
    due = today() + timedelta(days=5)
    r = rep_api.post(
        "/api/leads/",
        {
            "first_name": "Mia",
            "last_name": "Hart",
            "company_name": "Hart & Co",
            "source": "referral",
            "follow_up_date": due.isoformat(),
        },
        format="json",
    )
    assert r.status_code == 201
    task = Task.objects.get(lead_id=r.json()["id"])
    assert task.assignee == rep and task.due_date == due and task.auto_created and task.status == "open"
    assert "Mia Hart" in task.title


def test_lead_without_follow_up_date_gets_default_two_days(rep_api, rep):
    r = rep_api.post("/api/leads/", {"first_name": "No", "last_name": "Date"}, format="json")
    assert r.status_code == 201
    expected = today() + timedelta(days=2)
    assert r.json()["follow_up_date"] == expected.isoformat()
    assert Task.objects.get(lead_id=r.json()["id"]).due_date == expected


def test_followup_task_is_assigned_to_lead_owner_not_creator(manager_api, rep):
    r = manager_api.post("/api/leads/", {"first_name": "Zed", "last_name": "Q", "owner": rep.id}, format="json")
    assert Task.objects.get(lead_id=r.json()["id"]).assignee == rep


def test_updating_a_lead_does_not_create_another_task(rep, make_lead):
    lead = make_lead(rep)
    lead.notes = "changed"
    lead.save()
    assert Task.objects.filter(lead=lead).count() == 1


def test_past_follow_up_rejected_on_create_and_when_changed(rep_api, rep, make_lead):
    yesterday = (today() - timedelta(days=1)).isoformat()
    r = rep_api.post("/api/leads/", {"first_name": "A", "last_name": "B", "follow_up_date": yesterday}, format="json")
    assert r.status_code == 400 and "follow_up_date" in r.json()
    lead = make_lead(rep, follow_up_date=today() - timedelta(days=4))  # already overdue
    # editing other fields keeps the (past) date without error
    assert rep_api.patch(f"/api/leads/{lead.id}/", {"notes": "ok"}, format="json").status_code == 200
    assert rep_api.patch(f"/api/leads/{lead.id}/", {"follow_up_date": yesterday}, format="json").status_code == 400


def test_lead_validation_errors(rep_api):
    r = rep_api.post("/api/leads/", {"last_name": "B", "email": "not-an-email", "phone": "abc"}, format="json")
    body = r.json()
    assert r.status_code == 400 and {"first_name", "email", "phone"} <= set(body)
    r = rep_api.post("/api/leads/", {"first_name": "A", "last_name": "B", "estimated_value": "-1"}, format="json")
    assert r.status_code == 400 and "estimated_value" in r.json()


# ---- Rule 2: overdue flagging ----
def test_overdue_flag_is_computed_live_and_filterable(rep, rep_api, make_lead):
    overdue = make_lead(rep, first_name="Late", follow_up_date=today() - timedelta(days=3))
    ok = make_lead(rep, first_name="Fine", follow_up_date=today() + timedelta(days=3))
    done = make_lead(rep, first_name="Closed", follow_up_date=today() - timedelta(days=9), status="unqualified")
    by_id = {x["id"]: x for x in results(rep_api.get("/api/leads/"))}
    assert by_id[overdue.id]["is_overdue"] is True
    assert by_id[ok.id]["is_overdue"] is False and by_id[done.id]["is_overdue"] is False
    assert {x["id"] for x in results(rep_api.get("/api/leads/?overdue=true"))} == {overdue.id}
    assert {x["id"] for x in results(rep_api.get("/api/leads/?overdue=false"))} == {ok.id, done.id}


def test_flag_overdue_leads_flags_notifies_once_and_clears(rep, make_lead):
    late = make_lead(rep, follow_up_date=today() - timedelta(days=2))
    make_lead(rep, first_name="OnTime")
    Notification.objects.all().delete()

    assert rules.flag_overdue_leads() == {"flagged": 1, "cleared": 0}
    late.refresh_from_db()
    assert late.overdue_flagged_at is not None
    note = Notification.objects.get(kind="lead_overdue")
    assert note.recipient == rep and "2 days" in note.message

    # idempotent: second run does not notify again
    assert rules.flag_overdue_leads() == {"flagged": 0, "cleared": 0}
    assert Notification.objects.filter(kind="lead_overdue").count() == 1

    # moving the follow-up date clears the flag
    late.follow_up_date = today() + timedelta(days=1)
    late.save()
    assert rules.flag_overdue_leads() == {"flagged": 0, "cleared": 1}
    late.refresh_from_db()
    assert late.overdue_flagged_at is None


def test_run_workflows_command(rep, make_lead):
    make_lead(rep, follow_up_date=today() - timedelta(days=1))
    out = StringIO()
    call_command("run_workflows", stdout=out)
    assert "flagged: 1" in out.getvalue()


# ---- Lead conversion ----
def test_convert_lead_creates_company_contact_deal_atomically(rep, rep_api, make_lead):
    lead = make_lead(rep, email="Mia@Hart.example", company_name="Hart & Co", job_title="Owner")
    r = rep_api.post(
        f"/api/leads/{lead.id}/convert/",
        {"deal_title": "Hart website", "amount": "7500.00", "expected_close_date": "2030-01-31"},
        format="json",
    )
    assert r.status_code == 201, r.content
    deal = Deal.objects.get(pk=r.json()["id"])
    lead.refresh_from_db()
    assert lead.status == "converted" and lead.converted_deal == deal
    assert deal.company.name == "Hart & Co" and deal.contact.email == "mia@hart.example"
    assert deal.owner == rep and deal.stage == "new" and deal.stage_history.count() == 1
    assert Task.objects.get(lead=lead).status == "done"  # auto follow-up closed
    assert Interaction.objects.filter(deal=deal, is_system=True).exists()


def test_convert_reuses_existing_company_and_contact(rep, rep_api, make_lead, company, contact):
    lead = make_lead(rep, email=contact.email, company_name=company.name.upper())
    rep_api.post(f"/api/leads/{lead.id}/convert/", {"deal_title": "Reuse", "amount": "1"}, format="json")
    assert Company.objects.filter(name__iexact=company.name).count() == 1
    assert Contact.objects.filter(email__iexact=contact.email).count() == 1


def test_convert_rolls_back_everything_on_failure(rep, make_lead, monkeypatch):
    lead = make_lead(rep, email="roll@back.example", company_name="Rollback Ltd")

    def explode(**kwargs):
        raise IntegrityError("simulated failure while creating the deal")

    monkeypatch.setattr(services, "create_deal", explode)
    with pytest.raises(IntegrityError):
        services.convert_lead(lead, actor=rep, deal_title="X", amount="1")
    lead.refresh_from_db()
    assert lead.status == "new" and lead.converted_deal is None
    assert not Company.objects.filter(name="Rollback Ltd").exists()
    assert not Contact.objects.filter(email="roll@back.example").exists()


@pytest.mark.parametrize(
    "kwargs,fragment",
    [
        ({"status": "converted"}, "already"),
        ({"status": "unqualified"}, "Unqualified"),
        ({"company_name": ""}, "company name"),
    ],
)
def test_convert_guards(rep, rep_api, make_lead, kwargs, fragment):
    lead = make_lead(rep, **kwargs)
    r = rep_api.post(f"/api/leads/{lead.id}/convert/", {"deal_title": "X", "amount": "1"}, format="json")
    assert r.status_code == 400 and fragment.lower() in str(r.json()).lower()


def test_cannot_convert_by_setting_status_directly(rep, rep_api, make_lead):
    lead = make_lead(rep)
    r = rep_api.patch(f"/api/leads/{lead.id}/", {"status": "converted"}, format="json")
    assert r.status_code == 400 and "status" in r.json()


def test_lead_filters_search_ordering_pagination(rep, rep_api, make_lead):
    for i in range(25):
        make_lead(rep, first_name=f"Lead{i:02d}", last_name="Batch", source="event" if i % 2 else "website")
    page = rep_api.get("/api/leads/?ordering=first_name").json()
    assert page["count"] == 25 and len(page["results"]) == 20 and page["next"]
    assert page["results"][0]["first_name"] == "Lead00"
    assert rep_api.get("/api/leads/?page=2&ordering=first_name").json()["results"][0]["first_name"] == "Lead20"
    assert rep_api.get("/api/leads/?source=event").json()["count"] == 12
    assert rep_api.get("/api/leads/?search=lead07").json()["count"] == 1
    assert len(rep_api.get("/api/leads/?page_size=5").json()["results"]) == 5
    assert len(rep_api.get("/api/leads/?page_size=5000").json()["results"]) == 25  # capped at 100

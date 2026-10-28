import csv
import io
from datetime import timedelta

import pytest
from django.core.management import CommandError, call_command
from django.utils import timezone

from apps.accounts.models import User
from apps.activities.models import Notification, Task
from apps.crm.models import Company, Contact
from apps.sales.models import Deal, Lead
from tests.conftest import results

pytestmark = pytest.mark.django_db
today = timezone.localdate


def mk_task(user, title="T", offset=0, **kw):
    return Task.objects.create(title=title, due_date=today() + timedelta(days=offset), assignee=user, **kw)


# ---- tasks ----
def test_task_lifecycle_complete_and_reopen(rep, rep_api):
    r = rep_api.post(
        "/api/tasks/", {"title": "Call back", "due_date": today().isoformat(), "priority": "high"}, format="json"
    )
    assert r.status_code == 201 and r.json()["assignee"] == rep.id and r.json()["status"] == "open"
    tid = r.json()["id"]
    done = rep_api.post(f"/api/tasks/{tid}/complete/").json()
    assert done["status"] == "done" and done["completed_at"]
    reopened = rep_api.post(f"/api/tasks/{tid}/reopen/").json()
    assert reopened["status"] == "open" and reopened["completed_at"] is None


def test_task_validation_and_status_is_read_only(rep_api, rep):
    assert rep_api.post("/api/tasks/", {"title": "No date"}, format="json").status_code == 400
    assert rep_api.post("/api/tasks/", {"title": "x", "due_date": "garbage"}, format="json").status_code == 400
    assert (
        rep_api.post(
            "/api/tasks/", {"title": "x", "due_date": "2030-01-01", "priority": "urgent"}, format="json"
        ).status_code
        == 400
    )
    t = mk_task(rep)
    rep_api.patch(f"/api/tasks/{t.id}/", {"status": "done"}, format="json")
    t.refresh_from_db()
    assert t.status == "open" and t.completed_at is None


def test_task_filters_overdue_and_date_range(rep, rep_api):
    late, soon, far = mk_task(rep, "late", -3), mk_task(rep, "soon", 1), mk_task(rep, "far", 30)
    done = mk_task(rep, "done-late", -5)
    rep_api.post(f"/api/tasks/{done.id}/complete/")
    assert {t["id"] for t in results(rep_api.get("/api/tasks/?overdue=true"))} == {late.id}
    ids = {
        t["id"]
        for t in results(rep_api.get(f"/api/tasks/?due_after={today()}&due_before={today() + timedelta(days=7)}"))
    }
    assert ids == {soon.id}
    assert {t["id"] for t in results(rep_api.get("/api/tasks/?status=done"))} == {done.id}
    assert [t["id"] for t in results(rep_api.get("/api/tasks/?ordering=-due_date"))][0] == far.id


def test_rep_sees_only_own_tasks(rep, rep2, rep_api, manager_api):
    mine, theirs = mk_task(rep), mk_task(rep2)
    assert {t["id"] for t in results(rep_api.get("/api/tasks/"))} == {mine.id}
    assert rep_api.post(f"/api/tasks/{theirs.id}/complete/").status_code == 404
    assert {t["id"] for t in results(manager_api.get("/api/tasks/"))} == {mine.id, theirs.id}


# ---- notifications ----
def test_notifications_are_private_and_markable(rep, rep2, rep_api, rep2_api):
    a = Notification.objects.create(recipient=rep, title="A")
    Notification.objects.create(recipient=rep, title="B")
    other = Notification.objects.create(recipient=rep2, title="Other")
    assert rep_api.get("/api/notifications/unread-count/").json() == {"unread": 2}
    assert other.id not in {n["id"] for n in results(rep_api.get("/api/notifications/"))}
    assert rep_api.post(f"/api/notifications/{other.id}/read/").status_code == 404
    assert rep_api.post(f"/api/notifications/{a.id}/read/").json()["is_read"] is True
    assert rep_api.get("/api/notifications/?unread=true").json()["count"] == 1
    assert rep_api.post("/api/notifications/read-all/").json() == {"marked": 1}
    assert rep_api.get("/api/notifications/unread-count/").json() == {"unread": 0}
    assert rep2_api.get("/api/notifications/unread-count/").json() == {"unread": 1}


# ---- CSV export ----
def _rows(response):
    assert response.status_code == 200 and response["Content-Type"].startswith("text/csv")
    assert "attachment" in response["Content-Disposition"]
    text = response.content.decode("utf-8-sig")
    return list(csv.reader(io.StringIO(text)))


def test_contacts_csv_export_with_tags_and_filter(rep_api, company):
    from apps.crm.models import Tag

    t = Tag.objects.create(name="VIP")
    c = Contact.objects.create(first_name="Ada", last_name="Lovelace", email="ada@x.example", company=company)
    c.tags.add(t)
    Contact.objects.create(first_name="Bob", last_name="Other")
    rows = _rows(rep_api.get("/api/contacts/export/?search=lovelace"))
    assert rows[0][:4] == ["ID", "First name", "Last name", "Email"]
    assert len(rows) == 2 and rows[1][1] == "Ada" and "VIP" in rows[1]
    assert len(_rows(rep_api.get("/api/contacts/export/"))) == 3


def test_csv_neutralises_formula_injection(rep_api):
    Contact.objects.create(first_name='=HYPERLINK("http://evil.example")', last_name="+SUM(1+1)", job_title="@cmd")
    Company.objects.create(name="-2+3 Corp")
    row = _rows(rep_api.get("/api/contacts/export/"))[1]
    assert row[1].startswith("'=") and row[2].startswith("'+") and "'@cmd" in row
    assert _rows(rep_api.get("/api/companies/export/"))[1][1] == "'-2+3 Corp"


def test_csv_keeps_phone_numbers_intact_but_still_blocks_formulas(rep_api):
    from apps.core.csv_export import safe_cell

    Contact.objects.create(first_name="Pat", last_name="Phone", phone="+1 555-0100")
    assert "+1 555-0100" in _rows(rep_api.get("/api/contacts/export/"))[1]
    assert safe_cell("+44 (0) 20 7946 0000") == "+44 (0) 20 7946 0000"
    for evil in ["+1+1", "+SUM(A1)", "=1+1", "-2+3", "@SUM(A1)", "+1 555-0100;=cmd", "\t=1"]:
        assert safe_cell(evil).startswith("'"), evil
    assert safe_cell("normal text") == "normal text" and safe_cell(12) == 12


def test_csv_export_respects_role_scoping(rep, rep2, rep_api, manager_api, make_lead, make_deal):
    make_lead(rep, first_name="Mine")
    make_lead(rep2, first_name="Theirs")
    assert [r[1] for r in _rows(rep_api.get("/api/leads/export/"))[1:]] == ["Mine"]
    assert len(_rows(manager_api.get("/api/leads/export/"))) == 3
    make_deal(rep)
    assert len(_rows(rep_api.get("/api/deals/export/"))) == 2
    assert len(_rows(rep_api.get("/api/tasks/export/"))) >= 2


def test_csv_export_requires_authentication(anon):
    for path in ("contacts", "companies", "leads", "deals", "tasks"):
        assert anon.get(f"/api/{path}/export/").status_code == 401


# ---- dashboard ----
def test_dashboard_numbers_for_manager_and_rep(rep, rep2, rep_api, manager_api, make_lead, make_deal):
    make_lead(rep, follow_up_date=today() - timedelta(days=2))  # overdue
    make_lead(rep, first_name="Fine")
    make_lead(rep2, first_name="Other")
    make_deal(rep, amount="1000.00")
    make_deal(rep, stage="negotiation", amount="4000.00")
    make_deal(rep2, stage="won", amount="9000.00")
    make_deal(rep2, stage="lost", amount="500.00")
    mk_task(rep, "due today", 0)

    mgr = manager_api.get("/api/dashboard/").json()
    assert mgr["scope"] == "all"
    k = mgr["kpis"]
    assert (k["open_leads"], k["overdue_leads"], k["active_deals"]) == (3, 1, 2)
    assert k["pipeline_value"] == "5000.00"
    assert k["won_this_month_value"] == "9000.00" and k["won_this_month_count"] == 1
    assert [p["stage"] for p in mgr["pipeline"]] == ["new", "qualified", "proposal", "negotiation", "won", "lost"]
    assert {p["stage"]: p["count"] for p in mgr["pipeline"]}["negotiation"] == 1

    mine = rep_api.get("/api/dashboard/").json()
    assert mine["scope"] == "mine"
    assert mine["kpis"]["open_leads"] == 2 and mine["kpis"]["won_this_month_count"] == 0
    assert mine["kpis"]["tasks_due_today"] >= 1
    assert mine["overdue_leads"][0]["is_overdue"] is True
    assert len(mine["recent_activities"]) >= 1
    assert {s["source"] for s in mine["leads_by_source"]} == {"website"}


def test_dashboard_empty_state(rep_api):
    body = rep_api.get("/api/dashboard/").json()
    assert body["kpis"]["pipeline_value"] == "0.00" and body["upcoming_tasks"] == [] and body["recent_activities"] == []


# ---- seed + health + schema ----
def test_seed_demo_command(settings):
    settings.DEBUG = True  # the test runner forces DEBUG off; --reset requires it (or --yes-i-am-sure)
    call_command("seed_demo", stdout=io.StringIO())
    assert User.objects.count() == 4
    assert Company.objects.count() >= 10 and Contact.objects.count() >= 20
    assert Lead.objects.count() >= 10 and Deal.objects.count() >= 12
    assert Lead.objects.filter(follow_up_date__lt=today(), status__in=["new", "contacted", "qualified"]).exists()
    assert set(Deal.objects.values_list("stage", flat=True)) == {
        "new",
        "qualified",
        "proposal",
        "negotiation",
        "won",
        "lost",
    }
    assert Notification.objects.exists() and Task.objects.filter(auto_created=True).exists()
    assert not Deal.objects.filter(stage="lost", lost_reason="").exists()
    with pytest.raises(CommandError):
        call_command("seed_demo", stdout=io.StringIO())
    call_command("seed_demo", "--reset", stdout=io.StringIO())
    assert User.objects.count() == 4 and Company.objects.count() >= 10


def test_seed_reset_refused_without_debug(settings):
    settings.DEBUG = False
    with pytest.raises(CommandError):
        call_command("seed_demo", "--reset", stdout=io.StringIO())


def test_health_and_openapi_schema(anon):
    assert anon.get("/api/health/").json() == {"status": "ok", "database": "ok"}
    schema = anon.get("/api/schema/")
    assert schema.status_code == 200
    assert anon.get("/api/docs/").status_code == 200

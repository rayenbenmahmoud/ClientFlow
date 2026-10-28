import pytest

from apps.crm.models import Company
from apps.sales.models import Deal, Lead
from tests.conftest import results

pytestmark = pytest.mark.django_db


def test_rep_sees_only_own_leads_manager_sees_all(rep, rep2, rep_api, manager_api, make_lead):
    mine = make_lead(rep, first_name="Mine")
    theirs = make_lead(rep2, first_name="Theirs")
    assert {r["id"] for r in results(rep_api.get("/api/leads/"))} == {mine.id}
    assert {r["id"] for r in results(manager_api.get("/api/leads/"))} == {mine.id, theirs.id}


def test_rep_cannot_read_or_edit_other_reps_lead(rep, rep2, rep_api, make_lead):
    theirs = make_lead(rep2)
    assert rep_api.get(f"/api/leads/{theirs.id}/").status_code == 404
    assert rep_api.patch(f"/api/leads/{theirs.id}/", {"notes": "x"}, format="json").status_code == 404
    assert rep_api.delete(f"/api/leads/{theirs.id}/").status_code == 404


def test_rep_sees_only_own_deals_and_tasks(rep, rep2, rep_api, make_deal):
    mine, theirs = make_deal(rep), make_deal(rep2, title="Other")
    assert {d["id"] for d in results(rep_api.get("/api/deals/"))} == {mine.id}
    assert rep_api.get(f"/api/deals/{theirs.id}/").status_code == 404
    assert (
        rep_api.post(f"/api/deals/{theirs.id}/change-stage/", {"stage": "qualified"}, format="json").status_code == 404
    )


def test_rep_cannot_assign_records_to_others(rep, rep2, rep_api, company):
    r = rep_api.post("/api/leads/", {"first_name": "A", "last_name": "B", "owner": rep2.id}, format="json")
    assert r.status_code == 400 and "owner" in r.json()
    r = rep_api.post(
        "/api/deals/", {"title": "D", "amount": "10", "company": company.id, "owner": rep2.id}, format="json"
    )
    assert r.status_code == 400 and "owner" in r.json()
    r = rep_api.post("/api/tasks/", {"title": "T", "due_date": "2030-01-01", "assignee": rep2.id}, format="json")
    assert r.status_code == 400 and "assignee" in r.json()


def test_manager_can_assign_to_rep_and_reassign(manager_api, rep, company):
    r = manager_api.post(
        "/api/deals/", {"title": "D", "amount": "10", "company": company.id, "owner": rep.id}, format="json"
    )
    assert r.status_code == 201 and r.json()["owner"] == rep.id


def test_rep_cannot_reassign_own_lead_to_someone_else(rep, rep2, rep_api, make_lead):
    lead = make_lead(rep)
    r = rep_api.patch(f"/api/leads/{lead.id}/", {"owner": rep2.id}, format="json")
    assert r.status_code == 400


def test_cannot_assign_to_inactive_user(manager_api, rep, company):
    rep.is_active = False
    rep.save()
    r = manager_api.post(
        "/api/deals/", {"title": "D", "amount": "10", "company": company.id, "owner": rep.id}, format="json"
    )
    assert r.status_code == 400


def test_delete_rules_for_companies_and_deals(rep_api, manager_api, rep, make_deal):
    c = Company.objects.create(name="Deletable Inc")
    assert rep_api.delete(f"/api/companies/{c.id}/").status_code == 403
    assert manager_api.delete(f"/api/companies/{c.id}/").status_code == 204
    deal = make_deal(rep)
    assert rep_api.delete(f"/api/deals/{deal.id}/").status_code == 403
    assert manager_api.delete(f"/api/deals/{deal.id}/").status_code == 204


def test_rep_can_delete_own_lead(rep, rep_api, make_lead):
    lead = make_lead(rep)
    assert rep_api.delete(f"/api/leads/{lead.id}/").status_code == 204
    assert not Lead.objects.filter(pk=lead.pk).exists()


def test_user_management_is_admin_only(rep_api, manager_api, admin_api):
    payload = {
        "username": "newbie",
        "email": "newbie@demo.test",
        "password": "Another-Str0ng-Pass!",
        "role": "sales_rep",
    }
    assert rep_api.post("/api/users/", payload, format="json").status_code == 403
    assert manager_api.post("/api/users/", payload, format="json").status_code == 403
    r = admin_api.post("/api/users/", payload, format="json")
    assert r.status_code == 201 and "password" not in r.json()


def test_user_creation_validates_password_and_email(admin_api, rep):
    base = {"username": "x1", "email": "x1@demo.test", "role": "sales_rep"}
    assert admin_api.post("/api/users/", {**base, "password": "123"}, format="json").status_code == 400
    assert admin_api.post("/api/users/", {**base}, format="json").status_code == 400
    dup = {**base, "username": "x2", "email": "REP@demo.test", "password": "Another-Str0ng-Pass!"}
    assert admin_api.post("/api/users/", dup, format="json").status_code == 400


def test_users_cannot_be_deleted_and_reps_only_see_active(rep_api, admin_api, rep, rep2):
    assert admin_api.delete(f"/api/users/{rep2.id}/").status_code == 405
    admin_api.patch(f"/api/users/{rep2.id}/", {"is_active": False}, format="json")
    ids = {u["id"] for u in results(rep_api.get("/api/users/?page_size=100"))}
    assert rep2.id not in ids and rep.id in ids


def test_interaction_edit_rules(rep, rep2, rep_api, rep2_api, manager_api, contact):
    r = rep_api.post("/api/interactions/", {"type": "call", "subject": "Intro", "contact": contact.id}, format="json")
    assert r.status_code == 201
    iid = r.json()["id"]
    assert rep2_api.patch(f"/api/interactions/{iid}/", {"subject": "hack"}, format="json").status_code == 403
    assert rep2_api.delete(f"/api/interactions/{iid}/").status_code == 403
    assert rep_api.patch(f"/api/interactions/{iid}/", {"subject": "Updated"}, format="json").status_code == 200
    assert manager_api.delete(f"/api/interactions/{iid}/").status_code == 204


def test_run_workflows_endpoint_is_privileged(rep_api, manager_api):
    assert rep_api.post("/api/automation/run/").status_code == 403
    r = manager_api.post("/api/automation/run/")
    assert r.status_code == 200 and set(r.json()) == {"flagged", "cleared"}


def test_stage_is_read_only_through_regular_updates(rep, rep_api, make_deal):
    deal = make_deal(rep)
    r = rep_api.patch(f"/api/deals/{deal.id}/", {"stage": "won", "title": "Renamed"}, format="json")
    assert r.status_code == 200
    deal.refresh_from_db()
    assert deal.stage == Deal.Stage.NEW and deal.title == "Renamed"

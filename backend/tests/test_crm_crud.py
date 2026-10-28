import pytest

from apps.crm.models import Company, Contact, Tag
from tests.conftest import results

pytestmark = pytest.mark.django_db


def test_company_crud_and_counts(rep_api, rep, manager_api):
    r = rep_api.post(
        "/api/companies/", {"name": "  Birch Bakery ", "industry": "Food", "phone": "+1 555-0100"}, format="json"
    )
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Birch Bakery" and body["owner"] == rep.id
    cid = body["id"]
    assert rep_api.patch(f"/api/companies/{cid}/", {"city": "Leeds"}, format="json").json()["city"] == "Leeds"
    Contact.objects.create(first_name="A", last_name="B", company_id=cid)
    detail = rep_api.get(f"/api/companies/{cid}/").json()
    assert detail["contact_count"] == 1 and detail["deal_count"] == 0


def test_company_name_unique_case_insensitive(rep_api, company):
    r = rep_api.post("/api/companies/", {"name": company.name.lower()}, format="json")
    assert r.status_code == 400 and "name" in r.json()
    other = Company.objects.create(name="Second Co")
    r = rep_api.patch(f"/api/companies/{other.id}/", {"name": company.name.upper()}, format="json")
    assert r.status_code == 400
    assert rep_api.patch(f"/api/companies/{other.id}/", {"name": "Second Co"}, format="json").status_code == 200


def test_company_validation_messages(rep_api):
    r = rep_api.post("/api/companies/", {"name": "", "email": "bad", "website": "nope", "phone": "x"}, format="json")
    assert r.status_code == 400 and {"name", "email", "website", "phone"} <= set(r.json())


def test_contact_with_tags_company_and_email_rules(rep_api, company):
    tag = Tag.objects.create(name="VIP", color="#ff0000")
    r = rep_api.post(
        "/api/contacts/",
        {
            "first_name": "Grace",
            "last_name": "Hopper",
            "email": "Grace@Navy.EXAMPLE",
            "company": company.id,
            "tag_ids": [tag.id],
        },
        format="json",
    )
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "grace@navy.example" and body["company_name"] == company.name
    assert body["tags"] == [{"id": tag.id, "name": "VIP", "color": "#ff0000"}]
    dup = rep_api.post(
        "/api/contacts/", {"first_name": "G", "last_name": "H", "email": "GRACE@navy.example"}, format="json"
    )
    assert dup.status_code == 400 and "email" in dup.json()
    # blank emails are allowed many times
    for n in range(2):
        assert (
            rep_api.post("/api/contacts/", {"first_name": f"N{n}", "last_name": "Mail"}, format="json").status_code
            == 201
        )


def test_contact_requires_names(rep_api):
    r = rep_api.post("/api/contacts/", {"email": "x@y.example"}, format="json")
    assert r.status_code == 400 and {"first_name", "last_name"} <= set(r.json())


def test_contact_search_filter_sort(rep_api, company):
    other = Company.objects.create(name="Other Co")
    tag = Tag.objects.create(name="Partner")
    a = Contact.objects.create(first_name="Zoe", last_name="Adams", email="zoe@a.example", company=company)
    b = Contact.objects.create(first_name="Yan", last_name="Brown", company=other)
    a.tags.add(tag)
    assert [c["id"] for c in results(rep_api.get(f"/api/contacts/?company={other.id}"))] == [b.id]
    assert [c["id"] for c in results(rep_api.get(f"/api/contacts/?tag={tag.id}"))] == [a.id]
    assert [c["id"] for c in results(rep_api.get("/api/contacts/?search=acme"))] == [a.id]  # via company name
    assert [c["id"] for c in results(rep_api.get("/api/contacts/?ordering=-last_name"))] == [b.id, a.id]


def test_tags_unique_ci_color_validation_and_delete_rules(rep_api, manager_api):
    assert rep_api.post("/api/tags/", {"name": "Hot", "color": "#112233"}, format="json").status_code == 201
    assert rep_api.post("/api/tags/", {"name": "hot"}, format="json").status_code == 400
    assert rep_api.post("/api/tags/", {"name": "Bad", "color": "red"}, format="json").status_code == 400
    tid = Tag.objects.get(name="Hot").id
    assert rep_api.delete(f"/api/tags/{tid}/").status_code == 403
    assert manager_api.delete(f"/api/tags/{tid}/").status_code == 204


def test_deleting_company_with_deals_is_blocked_with_409(manager_api, rep, make_deal, company):
    make_deal(rep)
    r = manager_api.delete(f"/api/companies/{company.id}/")
    assert r.status_code == 409 and "depend" in r.json()["detail"]
    assert Company.objects.filter(pk=company.pk).exists()


def test_deleting_contact_keeps_company_and_deal(manager_api, rep, make_deal, contact, company):
    deal = make_deal(rep)
    assert manager_api.delete(f"/api/contacts/{contact.id}/").status_code == 204
    deal.refresh_from_db()
    assert deal.contact is None and deal.company == company


def test_interaction_requires_a_target_and_rejects_future(rep_api, contact):
    r = rep_api.post("/api/interactions/", {"type": "note", "subject": "Orphan"}, format="json")
    assert r.status_code == 400
    r = rep_api.post(
        "/api/interactions/",
        {"type": "call", "subject": "Future", "contact": contact.id, "occurred_at": "2999-01-01T10:00:00Z"},
        format="json",
    )
    assert r.status_code == 400 and "occurred_at" in r.json()
    ok = rep_api.post(
        "/api/interactions/", {"type": "meeting", "subject": "Kickoff", "contact": contact.id}, format="json"
    )
    assert ok.status_code == 201 and ok.json()["contact_name"] == contact.full_name
    assert [i["id"] for i in results(rep_api.get(f"/api/interactions/?contact={contact.id}"))] == [ok.json()["id"]]


def test_system_interactions_are_immutable(rep, rep_api, manager_api, make_deal):
    from apps.activities.models import Interaction
    from apps.sales import services

    deal = make_deal(rep)
    services.change_deal_stage(deal, "qualified", actor=rep)
    system = Interaction.objects.filter(is_system=True).first()
    assert manager_api.patch(f"/api/interactions/{system.id}/", {"subject": "x"}, format="json").status_code == 403
    assert manager_api.delete(f"/api/interactions/{system.id}/").status_code == 403

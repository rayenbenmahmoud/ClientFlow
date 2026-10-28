import pytest

from apps.activities.models import Interaction, Notification
from apps.sales import services
from apps.sales.models import Deal, DealStageHistory
from apps.sales.signals import deal_stage_changed

pytestmark = pytest.mark.django_db

S = Deal.Stage
ALLOWED = [
    (S.NEW, S.QUALIFIED),
    (S.NEW, S.LOST),
    (S.QUALIFIED, S.NEW),
    (S.QUALIFIED, S.PROPOSAL),
    (S.QUALIFIED, S.LOST),
    (S.PROPOSAL, S.QUALIFIED),
    (S.PROPOSAL, S.NEGOTIATION),
    (S.PROPOSAL, S.LOST),
    (S.NEGOTIATION, S.PROPOSAL),
    (S.NEGOTIATION, S.WON),
    (S.NEGOTIATION, S.LOST),
    (S.LOST, S.NEW),
]
FORBIDDEN = [
    (S.NEW, S.PROPOSAL),
    (S.NEW, S.NEGOTIATION),
    (S.NEW, S.WON),
    (S.QUALIFIED, S.NEGOTIATION),
    (S.QUALIFIED, S.WON),
    (S.PROPOSAL, S.WON),
    (S.PROPOSAL, S.NEW),
    (S.NEGOTIATION, S.NEW),
    (S.NEGOTIATION, S.QUALIFIED),
    (S.WON, S.NEW),
    (S.WON, S.LOST),
    (S.WON, S.NEGOTIATION),
    (S.LOST, S.QUALIFIED),
    (S.LOST, S.PROPOSAL),
    (S.LOST, S.NEGOTIATION),
    (S.LOST, S.WON),
    (S.WON, S.QUALIFIED),
    (S.WON, S.PROPOSAL),
]


def test_transition_table_is_complete():
    pairs = {(a, b) for a in S for b in S if a != b}
    declared = {(a, b) for a, targets in Deal.ALLOWED_TRANSITIONS.items() for b in targets}
    assert set(ALLOWED) | set(FORBIDDEN) == pairs
    assert declared == set(ALLOWED)


def _deal_in(make_deal, rep, stage):
    return make_deal(rep, stage=stage)


@pytest.mark.parametrize("src,dst", ALLOWED)
def test_allowed_transitions_via_service(rep, make_deal, src, dst):
    deal = _deal_in(make_deal, rep, src)
    deal = services.change_deal_stage(deal, dst, actor=rep, lost_reason="Went with a competitor")
    assert deal.stage == dst


@pytest.mark.parametrize("src,dst", FORBIDDEN)
def test_forbidden_transitions_via_service(rep, make_deal, src, dst):
    deal = _deal_in(make_deal, rep, src)
    with pytest.raises(services.DealStageError):
        services.change_deal_stage(deal, dst, actor=rep, lost_reason="x")
    deal.refresh_from_db()
    assert deal.stage == src


def test_same_stage_and_unknown_stage_rejected(rep, make_deal):
    deal = make_deal(rep)
    with pytest.raises(services.DealStageError):
        services.change_deal_stage(deal, S.NEW, actor=rep)
    with pytest.raises(services.DealStageError):
        services.change_deal_stage(deal, "bogus", actor=rep)


def test_lost_requires_reason_and_sets_closed_at(rep, make_deal):
    deal = make_deal(rep)
    with pytest.raises(services.DealStageError):
        services.change_deal_stage(deal, S.LOST, actor=rep, lost_reason="   ")
    deal = services.change_deal_stage(deal, S.LOST, actor=rep, lost_reason="  Too expensive ")
    assert deal.lost_reason == "Too expensive" and deal.closed_at is not None


def test_reopening_clears_closed_state(rep, make_deal):
    deal = make_deal(rep, stage=S.LOST)
    deal = services.change_deal_stage(deal, S.NEW, actor=rep)
    assert deal.closed_at is None and deal.lost_reason == ""


def test_won_sets_closed_at_and_is_terminal(rep, make_deal):
    deal = make_deal(rep, stage=S.WON)
    assert deal.closed_at is not None
    with pytest.raises(services.DealStageError):
        services.change_deal_stage(deal, S.NEW, actor=rep)


def test_history_is_recorded_from_creation(rep, make_deal):
    deal = make_deal(rep, stage=S.PROPOSAL)
    steps = list(DealStageHistory.objects.filter(deal=deal).order_by("id").values_list("from_stage", "to_stage"))
    assert steps == [("", "new"), ("new", "qualified"), ("qualified", "proposal")]


def test_stage_change_notifies_owner_and_logs_timeline(rep, manager, make_deal):
    deal = make_deal(rep)
    Notification.objects.all().delete()
    services.change_deal_stage(deal, S.QUALIFIED, actor=manager)
    note = Notification.objects.get()
    assert note.recipient == rep and note.kind == "deal_stage" and f"/deals/{deal.id}" == note.link
    assert "Qualified" in note.title and manager.display_name in note.message
    entry = Interaction.objects.filter(deal=deal, is_system=True).latest("id")
    assert "New" in entry.subject and "Qualified" in entry.subject


def test_failed_side_effect_rolls_back_the_whole_change(rep, make_deal):
    deal = make_deal(rep)
    history_before = DealStageHistory.objects.filter(deal=deal).count()

    def boom(sender, **kwargs):
        raise RuntimeError("workflow failure")

    deal_stage_changed.connect(boom, dispatch_uid="test-boom")
    try:
        with pytest.raises(RuntimeError):
            services.change_deal_stage(deal, S.QUALIFIED, actor=rep)
    finally:
        deal_stage_changed.disconnect(dispatch_uid="test-boom")
    deal.refresh_from_db()
    assert deal.stage == S.NEW
    assert DealStageHistory.objects.filter(deal=deal).count() == history_before


# ---- API level ----
def test_api_change_stage_success(rep, rep_api, make_deal):
    deal = make_deal(rep)
    r = rep_api.post(f"/api/deals/{deal.id}/change-stage/", {"stage": "qualified"}, format="json")
    assert r.status_code == 200 and r.json()["stage"] == "qualified"
    assert Notification.objects.filter(recipient=rep, kind="deal_stage").exists()


def test_api_change_stage_invalid_transition_returns_400(rep, rep_api, make_deal):
    deal = make_deal(rep)
    r = rep_api.post(f"/api/deals/{deal.id}/change-stage/", {"stage": "won"}, format="json")
    assert r.status_code == 400 and "Cannot move" in r.json()["stage"][0]


def test_api_lost_without_reason_is_400_and_with_reason_ok(rep, rep_api, make_deal):
    deal = make_deal(rep)
    assert rep_api.post(f"/api/deals/{deal.id}/change-stage/", {"stage": "lost"}, format="json").status_code == 400
    r = rep_api.post(
        f"/api/deals/{deal.id}/change-stage/", {"stage": "lost", "lost_reason": "No budget"}, format="json"
    )
    assert r.status_code == 200 and r.json()["lost_reason"] == "No budget"


def test_api_unknown_stage_is_400(rep, rep_api, make_deal):
    deal = make_deal(rep)
    assert rep_api.post(f"/api/deals/{deal.id}/change-stage/", {"stage": "nope"}, format="json").status_code == 400


def test_api_history_and_pipeline(rep, rep_api, make_deal):
    deal = make_deal(rep, stage=S.QUALIFIED)
    make_deal(rep, title="Second", amount="1000.00")
    hist = rep_api.get(f"/api/deals/{deal.id}/history/").json()
    assert [h["to_stage"] for h in hist] == ["qualified", "new"]
    cols = {c["stage"]: c for c in rep_api.get("/api/deals/pipeline/").json()}
    assert list(cols) == ["new", "qualified", "proposal", "negotiation", "won", "lost"]
    assert cols["new"]["count"] == 1 and cols["new"]["total"] == "1000.00"
    assert cols["qualified"]["deals"][0]["id"] == deal.id


def test_database_constraints_back_up_the_rules(rep, make_deal):
    from django.db import IntegrityError, transaction

    deal = make_deal(rep)
    with pytest.raises(IntegrityError), transaction.atomic():
        Deal.objects.filter(pk=deal.pk).update(stage="lost", lost_reason="")  # no reason, no closed_at
    with pytest.raises(IntegrityError), transaction.atomic():
        Deal.objects.filter(pk=deal.pk).update(amount=-1)
    with pytest.raises(IntegrityError), transaction.atomic():
        Deal.objects.filter(pk=deal.pk).update(stage="won")  # closed_at missing


def test_deal_validation(rep_api, company, contact):
    from apps.crm.models import Company, Contact

    other = Company.objects.create(name="Other Co")
    r = rep_api.post("/api/deals/", {"title": "D", "amount": "-5", "company": company.id}, format="json")
    assert r.status_code == 400 and "amount" in r.json()
    stranger = Contact.objects.create(first_name="S", last_name="T", company=other)
    r = rep_api.post(
        "/api/deals/", {"title": "D", "amount": "5", "company": company.id, "contact": stranger.id}, format="json"
    )
    assert r.status_code == 400 and "contact" in r.json()
    r = rep_api.post("/api/deals/", {"amount": "5", "company": company.id}, format="json")
    assert r.status_code == 400 and "title" in r.json()
    ok = rep_api.post(
        "/api/deals/", {"title": "Good", "amount": "99.50", "company": company.id, "contact": contact.id}, format="json"
    )
    assert ok.status_code == 201 and ok.json()["stage"] == "new"

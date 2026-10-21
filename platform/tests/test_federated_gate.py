"""Google (federated) sign-in: a verified Google token proves WHO the user is, not that they are allowed to spend money.
Federated users stay pending until an admin approves their Cognito `sub`; admin-created (native) users are unaffected."""

import pytest

from navigator.gateway.auth import JwtVerifier

from test_api import CLIENT, KEY, POOL, app, call, tok  # noqa: F401  (fixtures/helpers reused)

GOOGLE_SUB = "google-sub-0001-aaaa"
GOOGLE_GROUP = f"{POOL}_Google"


def google(sub=GOOGLE_SUB, **over):
    # What Cognito really issues for a federated login: username "Google_<id>" and the auto-created provider group.
    return tok(sub=sub, groups=[GOOGLE_GROUP], username=f"Google_{sub}", **over)


def admin():
    return tok(sub="admin-sub-0001", groups=["pilot-admin"])


PAID_OR_DATA = [
    ("POST", "/api/v1/resources/search", {"zipCode": "10027", "resourceType": "food_assistance"}),
    ("GET", "/api/v1/resources/osm-node-1", None),
    ("GET", "/api/v1/route", None),
    ("GET", "/api/v1/maps/style", None),
    ("GET", "/api/v1/sync-status", None),
    ("POST", "/api/v1/assistant", {"message": "food near 10027", "sessionId": "session-abcdef-1234"}),
]


@pytest.mark.parametrize("method,path,body", PAID_OR_DATA)
def test_pending_google_user_is_blocked_everywhere_that_costs_money_or_returns_data(app, method, path, body):
    s, b, _ = call(app, method, path, body=body, token=google())
    assert s == 403 and b["error"]["code"] == "pending_approval"


def test_pending_google_user_never_reaches_the_assistant_pipeline(app):
    calls = []
    app.d.pipeline.invoker = type("Spy", (), {"invoke": lambda self, *a, **k: calls.append(1)})()
    call(app, "POST", "/api/v1/assistant", body={"message": "food near 10027", "sessionId": "session-abcdef-1234"}, token=google())
    assert calls == []


def test_pending_user_can_still_see_their_status(app):
    s, b, _ = call(app, "GET", "/api/v1/me/usage", token=google())
    assert s == 200 and b["accountStatus"] == "pending"


def test_admin_approval_unlocks_that_google_user_only(app):
    s, b, _ = call(app, "PUT", f"/api/v1/admin/users/{GOOGLE_SUB}", body={"approved": True}, token=admin())
    assert s == 200 and b["approved"] is True
    assert call(app, "GET", "/api/v1/me/usage", token=google())[1]["accountStatus"] == "approved"
    assert call(app, "POST", "/api/v1/resources/search", body=PAID_OR_DATA[0][2], token=google())[0] == 200
    # A different Google account is still pending.
    assert call(app, "POST", "/api/v1/resources/search", body=PAID_OR_DATA[0][2], token=google(sub="google-sub-0002-bbbb"))[0] == 403


def test_approval_can_be_revoked_and_disable_wins(app):
    call(app, "PUT", f"/api/v1/admin/users/{GOOGLE_SUB}", body={"approved": True}, token=admin())
    call(app, "PUT", f"/api/v1/admin/users/{GOOGLE_SUB}", body={"approved": False}, token=admin())
    assert call(app, "GET", "/api/v1/sync-status", token=google())[1]["error"]["code"] == "pending_approval"
    call(app, "PUT", f"/api/v1/admin/users/{GOOGLE_SUB}", body={"approved": True, "disabled": True}, token=admin())
    assert call(app, "GET", "/api/v1/me/usage", token=google())[1]["accountStatus"] == "disabled"


def test_native_admin_created_users_keep_working_with_no_approval_record(app):
    s, b, _ = call(app, "GET", "/api/v1/me/usage", token=tok(sub="invited-user-0001"))
    assert s == 200 and b["accountStatus"] == "approved"
    assert call(app, "POST", "/api/v1/resources/search", body=PAID_OR_DATA[0][2], token=tok(sub="invited-user-0001"))[0] == 200


def test_a_google_admin_must_be_approved_first(app):
    t = tok(sub=GOOGLE_SUB, groups=[GOOGLE_GROUP, "pilot-admin"], username=f"Google_{GOOGLE_SUB}")
    s, b, _ = call(app, "PUT", "/api/v1/admin/switch", body={"assistantEnabled": False}, token=t)
    assert s == 403 and b["error"]["code"] == "pending_approval"


def test_identity_is_the_token_sub_never_the_email_claim(app):
    """Approving alice's sub must not approve a different sub that merely claims alice's email."""
    call(app, "PUT", f"/api/v1/admin/users/{GOOGLE_SUB}", body={"approved": True}, token=admin())
    impostor = google(sub="google-sub-9999-zzzz", email="alice@example.com", email_verified=True)
    assert call(app, "GET", "/api/v1/sync-status", token=impostor)[0] == 403


def test_approved_flag_cannot_be_set_by_a_non_admin_or_with_a_bad_type(app):
    assert call(app, "PUT", f"/api/v1/admin/users/{GOOGLE_SUB}", body={"approved": True}, token=tok(sub="invited-user-0001"))[0] == 403
    assert call(app, "PUT", f"/api/v1/admin/users/{GOOGLE_SUB}", body={"approved": "yes"}, token=admin())[0] == 400


def test_federated_detection_from_verified_claims():
    v = JwtVerifier(POOL, CLIENT, key_resolver=lambda t: KEY.public_key())
    assert v.verify(f"Bearer {google()}").federated is True
    assert v.verify(f"Bearer {tok(groups=[GOOGLE_GROUP])}").federated is True      # group alone
    assert v.verify(f"Bearer {tok(username='Google_abc12345')}").federated is True  # username alone
    # Live Cognito issues LOWERCASE usernames ("google_<id>"); detection must not depend on letter case.
    assert v.verify(f"Bearer {tok(username='google_110466797490935057990')}").federated is True
    assert v.verify(f"Bearer {tok(groups=[POOL + '_google'])}").federated is True
    assert v.verify(f"Bearer {tok(sub='native-user-0001', username='native-user-0001')}").federated is False


def test_quota_is_still_keyed_by_the_cognito_sub_for_approved_google_users(app):
    call(app, "PUT", f"/api/v1/admin/users/{GOOGLE_SUB}", body={"approved": True, "overrides": {"requests_per_user_day": 1}}, token=admin())
    body = {"message": "food near 10027", "sessionId": "session-abcdef-1234"}
    assert call(app, "POST", "/api/v1/assistant", body=body, token=google())[0] == 200
    s, b, _ = call(app, "POST", "/api/v1/assistant", body={**body, "message": "food near 10025"}, token=google())
    assert s == 429
    # A second Google account is not limited by the first one's usage (and is still pending, not 429).
    assert call(app, "POST", "/api/v1/assistant", body=body, token=google(sub="google-sub-0002-bbbb"))[1]["error"]["code"] == "pending_approval"


def test_approve_user_script_approves_and_revokes(app):
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location("approve_user", Path(__file__).resolve().parents[1] / "scripts" / "approve_user.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    ledger = app.d.ledger
    mod.run(GOOGLE_SUB, False, ledger)
    assert call(app, "GET", "/api/v1/me/usage", token=google())[1]["accountStatus"] == "approved"
    mod.run(GOOGLE_SUB, True, ledger)
    assert call(app, "GET", "/api/v1/me/usage", token=google())[1]["accountStatus"] == "pending"
    with pytest.raises(SystemExit):
        mod.run("bad sub!", False, ledger)

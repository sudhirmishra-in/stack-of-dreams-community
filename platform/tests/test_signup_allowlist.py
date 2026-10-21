"""Cognito pre sign-up trigger: only invited emails may create a NEW account through Google.
Existing users and admin-created users are never affected (Cognito only calls this when an account is created)."""

import importlib.util
from pathlib import Path

import pytest

from navigator.signup import allowlist
from navigator.signup.handler import make_handler

ROOT = Path(__file__).resolve().parents[1]


def event(email, source="PreSignUp_ExternalProvider", verified="true", username="google_1100"):
    attrs = {"email": email} if email is not None else {}
    if verified is not None:
        attrs["email_verified"] = verified
    return {"triggerSource": source, "userName": username, "request": {"userAttributes": attrs}, "response": {}}


@pytest.fixture
def handler(aws):
    return make_handler(allowlist.Allowlist("usage-t", resource=aws)), allowlist.Allowlist("usage-t", resource=aws)


def test_invited_google_email_may_create_an_account(handler):
    h, al = handler
    al.add("Alice@Example.com")
    ev = event("alice@example.com")
    assert h(ev, None) is ev  # Cognito expects the event back; returning it lets sign-up proceed


def test_matching_ignores_case_and_whitespace(handler):
    h, al = handler
    al.add("  alice@example.com ")
    assert h(event("ALICE@EXAMPLE.COM"), None)


def test_uninvited_google_email_is_rejected_before_an_account_exists(handler):
    h, al = handler
    al.add("alice@example.com")
    with pytest.raises(Exception, match="not_invited"):
        h(event("stranger@example.com"), None)


def test_empty_allowlist_rejects_everyone(handler):
    h, _ = handler
    with pytest.raises(Exception, match="not_invited"):
        h(event("alice@example.com"), None)


@pytest.mark.parametrize("verified", ["false", None, "", "no"])
def test_unverified_email_is_rejected_even_if_listed(handler, verified):
    h, al = handler
    al.add("alice@example.com")
    with pytest.raises(Exception, match="not_invited"):
        h(event("alice@example.com", verified=verified), None)


@pytest.mark.parametrize("email", [None, "", "not-an-email", "a@b@c.com"])
def test_missing_or_malformed_email_is_rejected(handler, email):
    h, al = handler
    al.add("alice@example.com")
    with pytest.raises(Exception, match="not_invited"):
        h(event(email), None)


@pytest.mark.parametrize("source", ["PreSignUp_AdminCreateUser", "PreSignUp_SignUp"])
def test_admin_created_and_other_sign_up_paths_are_untouched(handler, source):
    h, _ = handler
    ev = event("anyone@example.com", source=source)
    assert h(ev, None) is ev  # allowlist is empty, yet these paths are not restricted by it


def test_store_failure_fails_closed_for_google_but_not_for_admin_created(aws):
    class Broken:
        def contains(self, email):
            raise RuntimeError("dynamodb down")

    h = make_handler(Broken())
    with pytest.raises(Exception, match="signup_unavailable"):
        h(event("alice@example.com"), None)
    ev = event("a@example.com", source="PreSignUp_AdminCreateUser")
    assert h(ev, None) is ev


def test_rejection_does_not_leak_the_email(handler):
    h, _ = handler
    with pytest.raises(Exception) as e:
        h(event("stranger@example.com"), None)
    assert "stranger" not in str(e.value)


def test_allowlist_add_remove_list_roundtrip(aws):
    al = allowlist.Allowlist("usage-t", resource=aws)
    assert al.list() == []
    al.add("B@x.com")
    al.add("a@x.com")
    al.add("a@x.com")  # idempotent
    assert al.list() == ["a@x.com", "b@x.com"]
    al.remove("A@X.com")
    assert al.list() == ["b@x.com"]
    al.remove("never-added@x.com")  # removing something absent is not an error
    with pytest.raises(ValueError):
        al.add("nope")


def test_allow_email_script_manages_the_list(aws):
    spec = importlib.util.spec_from_file_location("allow_email", ROOT / "scripts" / "allow_email.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    al = allowlist.Allowlist("usage-t", resource=aws)
    assert mod.run(["add", "x@y.com", "z@y.com"], al) == ["x@y.com", "z@y.com"]
    assert mod.run(["remove", "x@y.com"], al) == ["z@y.com"]
    assert mod.run(["list"], al) == ["z@y.com"]
    with pytest.raises(SystemExit):
        mod.run(["add", "bad"], al)

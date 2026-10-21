"""Cognito PRE SIGN-UP trigger.

Cognito calls this when it is about to create an account. For a first-time sign-in through an external provider
(Google) the email must be on the allowlist AND Google must have verified it; otherwise sign-up is rejected and no
account is created. Every other path (users an administrator creates, normal sign-up which the pool disables) is
passed through untouched, and the trigger never runs for people who already have an account.

Fails closed for Google sign-ups: if the allowlist cannot be read, nobody new gets in. Never logs the email."""

from __future__ import annotations

import os
from typing import Any

from navigator.logging_util import log

from .allowlist import Allowlist, normalize

EXTERNAL = "PreSignUp_ExternalProvider"
# These strings reach the browser as Cognito's error text; the web app maps them to friendly messages.
NOT_INVITED = "not_invited"
UNAVAILABLE = "signup_unavailable"


def make_handler(allowlist: Any):
    def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
        if event.get("triggerSource") != EXTERNAL:
            return event
        attrs = (event.get("request") or {}).get("userAttributes") or {}
        email = normalize(attrs.get("email"))
        verified = str(attrs.get("email_verified", "")).lower() == "true"
        if email is None or not verified:
            log("signup_rejected", reason="email_missing_or_unverified")
            raise Exception(NOT_INVITED)
        try:
            invited = allowlist.contains(email)
        except Exception as e:
            log("signup_allowlist_error", error=type(e).__name__)
            raise Exception(UNAVAILABLE) from None
        if not invited:
            log("signup_rejected", reason="not_on_allowlist")
            raise Exception(NOT_INVITED)
        log("signup_allowed")
        return event

    return handler


_HANDLER = None


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    global _HANDLER
    if _HANDLER is None:
        _HANDLER = make_handler(Allowlist(os.environ.get("USAGE_TABLE", "navigator-usage-pilot")))
    return _HANDLER(event, context)

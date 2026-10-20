"""Deterministic request validation and domain gating. No LLM, no network.

The result is one of:
  allow     clearly about community resources -> skip the classifier
  reject    clearly out of scope or an obvious injection attempt -> fixed refusal, nothing else runs
  ambiguous -> ask the cheap classifier

This is a cost and relevance filter, NOT a security boundary. Real protection comes from tool allowlists,
least-privilege IAM, and treating all text (user, history, data sources) as untrusted input.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

from navigator.config import QuotaLimits
from navigator.errors import BadRequest
from navigator.models import HistoryMessage

Decision = Literal["allow", "reject", "ambiguous"]

REFUSAL_OUT_OF_SCOPE = (
    "I can only help with finding community resources such as food assistance, baby formula, diapers, "
    "nearby providers, and what is available. Try asking, for example: \"Which food banks near 10027 are open?\""
)

_ALLOW = re.compile(
    r"\b(food|pantr(?:y|ies)|food ?banks?|soup kitchens?|meals?|groceries|grocery|formula|infant|baby|babies|diapers?|"
    r"nappies|hunger|hungry|snap|wic|resources?|nearby|near me|zip|inventory|in stock|stock|capacity|distribut\w*|"
    r"provider|organi[sz]ations?|nonprofit|non-profit|shelter|community|assistance|supplies|open (?:today|now)|hours)\b",
    re.I,
)
_REJECT = re.compile(
    r"\b(write (?:me )?(?:a |an |some )?(?:poem|essay|story|song|code|script|program|function|email|cover letter)|"
    r"(?:python|javascript|sql|java|c\+\+|html) (?:code|script|function)|homework|solve (?:this )?(?:equation|problem)|"
    r"bitcoin|crypto(?:currency)?|stock (?:tips|market|picks)|invest(?:ment|ing)? advice|lottery|"
    r"diagnos\w+|prescri\w+|dosage|legal advice|sue |lawsuit|jailbreak|dan mode|"
    r"translate (?:this|the following)|recipe for|movie|celebrity|horoscope)\b",
    re.I,
)
_INJECTION = re.compile(
    r"(ignore (?:all |any |the )?(?:previous|prior|above|earlier) (?:instructions?|prompts?|rules?)|"
    r"disregard (?:all |any |the )?(?:previous|prior|above)|forget (?:your|all|the) (?:instructions?|rules?)|"
    r"(?:reveal|show|print|repeat|output|leak) (?:me )?(?:your|the) (?:system |hidden |initial )?(?:prompt|instructions?)|"
    r"you are now |act as (?:an? )?(?:unrestricted|jailbroken|dan)|developer mode|"
    r"(?:call|invoke|run|use) (?:the )?(?:tool|function) |<\s*/?\s*(?:system|assistant|tool)\s*>)",
    re.I,
)

_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f​-‏‪-‮⁠-⁤﻿]")


def sanitize(text: str) -> str:
    """Normalizes unicode, strips control and invisible/bidi characters, collapses whitespace."""
    t = unicodedata.normalize("NFKC", text)
    t = _CONTROL.sub("", t)
    return " ".join(t.split())


def clean_message(message: str, limits: QuotaLimits) -> str:
    cleaned = sanitize(message)
    if not cleaned:
        raise BadRequest("Message must not be empty")
    if len(cleaned) > limits.max_query_chars:
        raise BadRequest(f"Message is too long. Please keep it under {limits.max_query_chars} characters.", details={"maxChars": limits.max_query_chars})
    return cleaned


def clean_history(history: list[HistoryMessage], limits: QuotaLimits) -> list[dict[str, str]]:
    """Keep only the last N turns, sanitize, and cap each. Assistant turns from the browser are untrusted too."""
    recent = history[-limits.history_messages :] if limits.history_messages > 0 else []
    out = []
    for m in recent:
        text = sanitize(m.content)[: limits.max_query_chars]
        if text:
            out.append({"role": m.role, "content": text})
    return out


@dataclass(frozen=True)
class DomainDecision:
    decision: Decision
    reason: str


def decide(message: str, history: list[dict[str, str]] | None = None) -> DomainDecision:
    if _INJECTION.search(message):
        return DomainDecision("reject", "injection_pattern")
    if _REJECT.search(message) and not _ALLOW.search(message):
        return DomainDecision("reject", "out_of_domain")
    if _ALLOW.search(message):
        return DomainDecision("allow", "domain_keywords")
    # Very short follow-ups ("and in Queens?") are only meaningful with recent on-topic context.
    if history and any(_ALLOW.search(h["content"]) for h in history if h["role"] == "user") and len(message) < 80:
        return DomainDecision("ambiguous", "followup")
    return DomainDecision("ambiguous", "no_signal")

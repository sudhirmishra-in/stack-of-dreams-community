"""Treat every string that came from a data source or a user as untrusted, and verify the model's output.

* `untrusted()` cleans source text before it is shown to a model (names, hours, notes from OpenStreetMap etc.
  can contain instructions). It cannot make injection impossible, which is why tools are allowlisted, read-only
  and least-privilege; it only removes the cheap, obvious vectors.
* `guard_response()` checks the model's final text against what the tools ACTUALLY returned: phone numbers,
  e-mail addresses, URLs and inventory quantities that are not in tool data are redacted. This is what stops
  unsupported contact or inventory claims even if the model hallucinates or is manipulated.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from navigator.gateway.validate import _INJECTION, sanitize

_PHONE = re.compile(r"(?<!\d)(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_URL = re.compile(r"https?://[^\s)>\]]+", re.I)
_QTY = re.compile(r"(?<![\w.])(\d[\d,]*)\s*(units?|cans?|lbs?|pounds?|boxes?|cases?|packs?|bottles?|tins?|diapers?|containers?|pallets?)\b", re.I)
_TAGS = re.compile(r"[<>`]")

REDACTED_CONTACT = "[not in verified data]"
REDACTED_QTY = "[quantity not in data]"


def untrusted(text: str | None, limit: int = 160) -> str | None:
    if not text:
        return None
    t = sanitize(str(text))
    t = _TAGS.sub("", t)
    t = _INJECTION.sub("[removed]", t)
    return t[:limit] or None


def _digits(s: str) -> str:
    return re.sub(r"\D", "", s)[-10:]


@dataclass
class Observed:
    """Everything tools returned during this request: the only facts the answer may rely on."""

    phones: set[str] = field(default_factory=set)
    urls: set[str] = field(default_factory=set)
    quantities: set[int] = field(default_factory=set)
    resources: dict[str, dict] = field(default_factory=dict)
    activity_used: bool = False
    tool_calls: int = 0

    def add_resource(self, view: dict) -> None:
        self.resources[view["id"]] = {
            "sourceId": view.get("sourceId", "unknown"),
            "isDemoData": bool(view.get("isDemoData")),
            "verification": "verified" if view.get("verified") else "unverified",
            "freshness": view.get("freshness", "unknown"),
            # Kept only so a limit-truncated request can still list what was found; never part of the citation.
            "name": view.get("name"),
            "address": view.get("address"),
            "distanceMiles": view.get("distanceMiles"),
        }
        if view.get("phone"):
            self.phones.add(_digits(view["phone"]))
        for key in ("website", "sourceUrl"):
            if view.get(key):
                self.urls.add(view[key].rstrip("/"))
        for q in (view.get("inventory") or {}).values():
            self.quantities.add(int(q))
        if view.get("availableQuantity") is not None:
            self.quantities.add(int(view["availableQuantity"]))
        if view.get("weeklyCapacity") is not None:
            self.quantities.add(int(view["weeklyCapacity"]))
        if view.get("distanceMiles") is not None:
            self.quantities.add(int(view["distanceMiles"]))

    def add_numbers(self, *values: int | None) -> None:
        self.quantities.update(int(v) for v in values if v is not None)


def guard_response(text: str, seen: Observed) -> tuple[str, list[str]]:
    """Returns (safe text, notes about what was removed)."""
    notes: list[str] = []

    def phone(m: re.Match[str]) -> str:
        if _digits(m.group(0)) in seen.phones:
            return m.group(0)
        notes.append("removed a phone number that was not in the retrieved data")
        return REDACTED_CONTACT

    def email(m: re.Match[str]) -> str:
        notes.append("removed an e-mail address that was not in the retrieved data")
        return REDACTED_CONTACT

    def url(m: re.Match[str]) -> str:
        if m.group(0).rstrip("/.,;") in seen.urls or m.group(0).rstrip("/") in seen.urls:
            return m.group(0)
        notes.append("removed a link that was not in the retrieved data")
        return REDACTED_CONTACT

    def qty(m: re.Match[str]) -> str:
        n = int(m.group(1).replace(",", ""))
        if n in seen.quantities:
            return m.group(0)
        notes.append("removed a quantity that was not in the retrieved data")
        return f"{REDACTED_QTY}"

    out = _URL.sub(url, text)  # URLs first so their digits are not mistaken for phone numbers
    out = _EMAIL.sub(email, out)
    out = _PHONE.sub(phone, out)
    out = _QTY.sub(qty, out)
    return out, sorted(set(notes))

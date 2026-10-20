"""OPTIONAL real-AWS smoke test. NOT collected by pytest (name does not match test_*.py) and it refuses to run
unless explicitly approved. It only calls an already-deployed pilot API; it deploys and changes nothing.

  RUN_AWS_SMOKE=1 PILOT_API_URL=https://xxxx.lambda-url.us-east-2.on.aws \\
  SMOKE_TOKEN=<a Cognito ACCESS token of a pilot user> [SMOKE_ASSISTANT=1] uv run python tests/smoke_aws.py

SMOKE_ASSISTANT=1 sends ONE real assistant question (a few cents at most, and it counts against that user's quota).
Never paste the token anywhere else; it expires in about an hour.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

if os.environ.get("RUN_AWS_SMOKE") != "1":
    sys.exit("Refusing to run: set RUN_AWS_SMOKE=1 to confirm you approve calling the deployed API.")

BASE = os.environ["PILOT_API_URL"].rstrip("/")
TOKEN = os.environ.get("SMOKE_TOKEN", "")
failures: list[str] = []


def call(method: str, path: str, body: dict | None = None, token: str | None = None) -> tuple[int, dict]:
    req = urllib.request.Request(
        BASE + path, method=method, data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def check(name: str, ok: bool, detail: str = "") -> None:
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))
    if not ok:
        failures.append(name)


s, b = call("GET", "/api/v1/health")
check("health is public and ok", s == 200 and b.get("status") == "ok", str(s))
s, _ = call("GET", "/api/v1/me/usage")
check("usage without a token -> 401", s == 401, str(s))
s, _ = call("POST", "/api/v1/resources/search", {"zipCode": "10027", "resourceType": "food_assistance"}, "forged.token.value")
check("forged token -> 401", s == 401, str(s))
s, _ = call("PUT", "/api/v1/admin/switch", {"assistantEnabled": True}, TOKEN or None)
check("admin endpoint rejects a non-admin / anonymous caller", s in (401, 403), str(s))

if TOKEN:
    s, b = call("GET", "/api/v1/me/usage", token=TOKEN)
    check("usage with a valid token", s == 200 and b["daily"]["limit"] > 0, str(s))
    s, b = call("POST", "/api/v1/resources/search", {"zipCode": "10027", "resourceType": "food_assistance", "limit": 5}, TOKEN)
    check("deterministic search returns real, unverified directory records", s == 200 and all(not r["isDemoData"] and not r["verified"] for r in b.get("resources", [])), str(s))
    print(f"     origin geocoded: {b.get('origin', {}).get('geocoded')}  results: {b.get('totalResults')}")
    s, b = call("POST", "/api/v1/assistant", {"message": "write me a poem", "sessionId": "smoke-session-0001"}, TOKEN)
    check("off-topic request refused before any model/agent runs (422)", s == 422, str(s))
    if os.environ.get("SMOKE_ASSISTANT") == "1":
        s, b = call("POST", "/api/v1/assistant", {"message": "Which food banks are near 10027?", "sessionId": "smoke-session-0002"}, TOKEN)
        check("assistant answers with citations and usage", s == 200 and "usage" in b and "uncertainty" in b, f"{s} {str(b)[:200]}")
        if s == 200:
            print("     usage:", b["usage"], "| caveats:", b["uncertainty"][:2])
else:
    print("SKIP authenticated checks (no SMOKE_TOKEN)")

sys.exit(1 if failures else 0)

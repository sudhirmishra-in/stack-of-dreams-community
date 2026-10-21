#!/usr/bin/env python3
"""Manage the emails allowed to create a NEW account by signing in with Google, using YOUR AWS credentials.

Usage (from platform/):
  uv run python scripts/allow_email.py add alice@example.com bob@example.com
  uv run python scripts/allow_email.py remove alice@example.com
  uv run python scripts/allow_email.py list

Being on this list lets a person create an account; they still start as PENDING and need approval
(scripts/approve_user.py) before they can use the pilot. Removing an email does not delete an existing account.
Environment: USAGE_TABLE (default navigator-usage-pilot), AWS_REGION (default us-east-2).
"""

from __future__ import annotations

import argparse
import sys

from navigator.config import Settings
from navigator.signup.allowlist import Allowlist, normalize


def run(argv: list[str], allowlist: Allowlist) -> list[str]:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["add", "remove", "list"])
    ap.add_argument("emails", nargs="*")
    args = ap.parse_args(argv)
    if args.action != "list":
        if not args.emails:
            raise SystemExit("Give at least one email address.")
        bad = [e for e in args.emails if normalize(e) is None]
        if bad:
            raise SystemExit(f"Not valid email addresses: {', '.join(bad)}")
        for e in args.emails:
            (allowlist.add if args.action == "add" else allowlist.remove)(e)
    return allowlist.list()


def main(argv: list[str] | None = None) -> int:
    s = Settings()
    emails = run(sys.argv[1:] if argv is None else argv, Allowlist(s.usage_table, s.region))
    print(f"{len(emails)} allowed email(s):")
    for e in emails:
        print(f"  {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

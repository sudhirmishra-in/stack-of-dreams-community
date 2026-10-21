#!/usr/bin/env python3
"""Approve (or revoke) a Google-signed-in pilot user by Cognito `sub`, using YOUR AWS credentials.

Google sign-in proves who someone is; this script is the explicit human decision that lets them use the pilot.
Find the sub with:
  aws cognito-idp list-users --region us-east-2 --user-pool-id <pool> \\
    --filter 'cognito:user_status = "EXTERNAL_PROVIDER"' --query 'Users[].[Attributes[?Name==`sub`]|[0].Value,Attributes[?Name==`email`]|[0].Value]'

Usage (from platform/):  uv run python scripts/approve_user.py <sub>            # approve
                         uv run python scripts/approve_user.py <sub> --revoke   # back to pending
Environment: USAGE_TABLE (default navigator-usage-pilot), AWS_REGION (default us-east-2).
"""

from __future__ import annotations

import argparse
import re
import sys

from navigator.config import Settings
from navigator.quota.ledger import UsageLedger

_SUB = re.compile(r"^[A-Za-z0-9_.:-]{8,128}$")


def run(sub: str, revoke: bool, ledger: UsageLedger) -> dict:
    if not _SUB.match(sub):
        raise SystemExit("That does not look like a Cognito sub (expected the user's 'sub' attribute).")
    return ledger.set_user_profile(sub, disabled=None, overrides=None, actor="cli:approve_user", approved=not revoke)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sub")
    ap.add_argument("--revoke", action="store_true", help="return the user to pending")
    args = ap.parse_args(argv)
    s = Settings()
    profile = run(args.sub, args.revoke, UsageLedger(s.usage_table, s.region))
    print(f"{'approved' if profile['approved'] else 'pending'}: {args.sub} (disabled={profile['disabled']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

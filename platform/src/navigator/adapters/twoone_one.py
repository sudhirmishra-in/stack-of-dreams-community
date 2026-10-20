"""211 adapter: DISABLED until access is authorized. Deliberately contains no network calls.

When 211 data-sharing access is granted: obtain the API credentials, store the key in SSM Parameter Store
(SecureString) or Secrets Manager, set SOURCE_211_ENABLED=true and SOURCE_211_API_KEY_PARAM, then implement
`fetch` against the contract and terms 211 provides. Nothing here assumes what that API looks like.
"""

from __future__ import annotations

from typing import Iterator

from .base import AdapterNotConfigured, Page

SOURCE_ID = "211"


class TwoOneOneAdapter:
    source_id = SOURCE_ID
    supports_deactivation = False

    def __init__(self, enabled: bool = False, api_key_param: str = ""):
        self.enabled, self.api_key_param = enabled, api_key_param

    def fetch(self, checkpoint: str | None, full: bool) -> Iterator[Page]:
        if not self.enabled:
            raise AdapterNotConfigured("211 integration is disabled (access not yet authorized)")
        if not self.api_key_param:
            raise AdapterNotConfigured("211 is enabled but SOURCE_211_API_KEY_PARAM is not set")
        raise AdapterNotConfigured("211 fetch is not implemented: waiting for the authorized API contract and terms")
        yield Page()  # pragma: no cover  (makes this a generator)

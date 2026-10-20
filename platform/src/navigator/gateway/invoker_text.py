"""Text helpers shared by the gateway and the agent runtime (no heavy imports)."""

from __future__ import annotations

import re

_THINKING = re.compile(r"<thinking>[\s\S]*?</thinking>", re.I)


def strip_thinking(text: str) -> str:
    """Removes inline <thinking>...</thinking> scratch text (and an unterminated trailing block)."""
    out = _THINKING.sub("", text)
    out = re.sub(r"<thinking>[\s\S]*$", "", out, flags=re.I)
    # Some models also wrap the final answer in <response>...</response>; keep the content, drop the tags.
    out = re.sub(r"</?response>", "", out, flags=re.I)
    return out.strip()

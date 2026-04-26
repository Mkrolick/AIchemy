"""STUB: LLM-based extraction path.

Use when adding a new vendor without writing a per-vendor regex parser:
fetch markdown via Fetch API → feed to an LLM → ask "what's the per-gram
price". Vendor-agnostic but adds Anthropic/OpenAI cost (~$0.001-0.01/page)
and depends on prompt-engineering quality.

NOT IMPLEMENTED in v1 — the per-vendor regex parsers in parsers/{vendor}.py
are deterministic and free; build this only when the parser-per-vendor
cost grows past the LLM-call cost (e.g. supporting 50+ vendors).
"""

from __future__ import annotations

from aichemy_pricing.types import PriceQuote, VendorRef


class BrowserbaseLLMLookup:
    name = "browserbase_llm"

    def __init__(self) -> None:
        raise NotImplementedError(
            "BrowserbaseLLMLookup: not implemented in v1. The per-vendor "
            "markdown parsers under aichemy_pricing.browserbase.parsers are "
            "deterministic and free; build this only when the parser-per-vendor "
            "cost grows past the LLM-call cost (e.g. supporting 50+ vendors)."
        )

    def lookup(self, ref: VendorRef) -> PriceQuote | None:
        raise NotImplementedError

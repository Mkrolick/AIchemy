"""Each L3 vendor parser is a tiny module exporting two callables:

    URL_TEMPLATE: str   # e.g. "https://www.sigmaaldrich.com/US/en/product/aldrich/{sku}"
    def parse(markdown: str, sku: str) -> PriceQuote | None: ...

The vendor name is implied by the module name in `parsers/`. We don't
runtime_checkable this Protocol because the implementations are *modules*,
not class instances, and isinstance checks don't apply.
"""

from __future__ import annotations

from typing import Protocol

from aichemy_pricing.types import PriceQuote


class MarkdownParser(Protocol):
    """Pure function: rendered markdown of a vendor product page → PriceQuote | None."""

    URL_TEMPLATE: str

    def parse(self, markdown: str, sku: str) -> PriceQuote | None: ...

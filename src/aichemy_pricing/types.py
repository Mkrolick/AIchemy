"""Pure-data types — no behavior, no I/O."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, PositiveFloat, field_validator

Currency = Literal["USD", "GBP", "EUR", "CNY", "JPY", "SEK"]


class VendorRef(BaseModel):
    """Pointer from an InChIKey to a vendor's catalog SKU."""

    model_config = ConfigDict(frozen=True)

    vendor: str
    sku: str
    canonical_url: str | None = None


class ResolverHit(VendorRef):
    """A `VendorRef` plus the source InChIKey it resolves."""

    inchikey: str = Field(min_length=27, max_length=27)


class PriceQuote(BaseModel):
    """One pack of one product at one vendor at one moment."""

    vendor: str
    sku: str
    price: PositiveFloat
    currency: Currency
    pack_size_g: PositiveFloat
    fetched_at: datetime
    raw: dict[str, Any] | None = None

    @field_validator("currency", mode="before")
    @classmethod
    def _normalize_currency(cls, v: object) -> object:
        return v.upper() if isinstance(v, str) else v

    @property
    def price_per_gram_native(self) -> float:
        return self.price / self.pack_size_g

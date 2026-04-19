# Open Item 01 — ChemPrize → Federated Price Lookup (retargeted)

**Status:** RETIRED. The original ChemPrize integration is superseded by the federated lookup in Stage 10 (ZINC bulk primary, PubChem discovery, opt-in scrapers). ChemPrize can be added later as another keyed `PriceLookup` implementation if access is granted, but it's no longer on the critical path.

**If ChemPrize becomes available:** implement `ChemPrizeClient(PriceLookup)` and add `"chemprize"` to the `prices.chain` config list. No other stage changes needed.

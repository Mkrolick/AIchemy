# Open Item 08 — Patent scrapers (`aichemy.scrapers`)

**Goal:** Scrape patent filings for fixed-cost estimates and better stoichiometric coefficients (per proposal's Todos section). Independent of the chemical price scrapers in Stage 10.

**Prerequisites:** Stages 02–12 + Open Item 07 solver running first. Patent scraping adds a second-order data layer.

## Tasks (Ralph loop: 30 iterations when activated)

- [ ] Decide patent source: Google Patents (accessible), USPTO's own API (robust but rate-limited), Lens.org (needs account)
- [ ] Build `aichemy.scrapers.patents.PatentSearcher` with a search-by-molecule API
- [ ] Extract reaction conditions (temperature, pressure, catalyst) from patent text
- [ ] Cost-estimation heuristics (based on catalyst type, temperature, pressure → estimated $/reaction-hour)
- [ ] Wire into a new `augment_patent_data` stage (post-export) that enriches reactions

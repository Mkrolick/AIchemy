# Open Item 05 — MetaNetX atom-balance failure policy

**Decision needed:** when `balance/validate.py` flags a MetaNetX reaction as unbalanced (typically missing H+ or H2O due to MetaNetX's curation conventions), what do we do?

**Options:**
1. **Flag + pass through** (`balanced=False`) — let the MILP exclude unbalanced reactions via an optional constraint
2. **Attempt proton balancing** — heuristic: if only H count differs, add/subtract H+ to balance
3. **Attempt water balancing** — if only H and O differ in a 2:1 ratio, add/subtract H2O
4. **Drop unbalanced** — exclude entirely; lose data but guarantee solver correctness

**Recommendation:** ship option 1 first (flag + pass), measure failure rate, decide if 2 or 3 is worthwhile based on volume.

## Tasks (after Stage 08 is running)

- [ ] After `balance_validate` runs on real data, measure % flagged as unbalanced among MetaNetX rows
- [ ] If >20% unbalanced, implement proton/water heuristics (Options 2/3) as optional augmenters
- [ ] Add config `balance.metanetx_unbalanced_policy: Literal["flag", "heuristic_h", "heuristic_h2o", "drop"]`
- [ ] Implement each policy as a separate function with unit tests

"""Patent + data-enrichment scrapers.

Provides:
- `PatentSearcher`: queries the USPTO PatentsView API for patent metadata
  matching a given chemical term. Used as the foundation for future
  reaction-condition NLP (fixed costs, catalyst prices, process temps).
"""

from aichemy.scrapers.patents import Patent, PatentSearcher

__all__ = ["Patent", "PatentSearcher"]

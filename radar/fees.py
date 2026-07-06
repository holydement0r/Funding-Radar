"""Per-venue taker fees (decimal, one leg, one direction).

Values from official fee pages; base tier, no VIP/volume discounts.
Maintenance task: re-verify quarterly and when adding a venue (runbook).
Verification pending marks values taken from docs knowledge that Sonnet
must confirm against the live fee page (plan Task 18).
"""
from __future__ import annotations

TAKER_FEES: dict[str, float] = {
    "hyperliquid": 0.00045,  # verification pending: https://hyperliquid.gitbook.io fees page
    "aster": 0.00035,        # verification pending: https://docs.asterdex.com fees page
    "paradex": 0.0003,       # verification pending: https://docs.paradex.trade fees page
    "lighter": 0.0,          # verification pending: lighter.xyz — zero-fee model
}

# Unknown venues get a conservative (high) fee so net_apr is understated,
# never overstated.
DEFAULT_TAKER_FEE = 0.0005

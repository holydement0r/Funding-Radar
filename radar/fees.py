"""Per-venue taker fees (decimal, one leg, one direction).

Base-tier taker fees, no VIP/volume/token discounts. Verified against
official docs 2026-07-06 (source per line). Re-verify quarterly and when
adding a venue (see docs/runbook.md).
"""
from __future__ import annotations

TAKER_FEES: dict[str, float] = {
    "hyperliquid": 0.00045,         # 0.045% - hyperliquid.gitbook.io/hyperliquid-docs/trading/fees
    "aster": 0.0004,                # 0.04% USDT perps - docs.asterdex.com/trading/perpetuals/fees-and-specs/fees
    "paradex": 0.0,                 # 0% taker on 100+ perps - docs.paradex.trade (2026)
    "lighter": 0.0,                 # 0% standard accounts - docs.lighter.xyz/perpetual-futures/fees
    "binance_via_lighter": 0.0004,  # 0.04% Binance USDT-M taker - binance.com/en/fee/futureFee
    "dydx": 0.0005,                 # 0.05% base tier - docs.dydx.exchange
    "extended": 0.00025,            # 0.025% flat - docs.extended.exchange (llms-full.txt)
    "pacifica": 0.0004,             # 0.04% base - docs.pacifica.fi / rankfi.com/dex/pacifica
}

# Unknown venues get a conservative (high) fee so net_apr is understated,
# never overstated.
DEFAULT_TAKER_FEE = 0.0005

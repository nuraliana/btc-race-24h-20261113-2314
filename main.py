"""Dip-sniper: a long-only mean-reversion bot for the make.fun BTC race.

Idea
----
The replay's price is a thin on-chain pool quote: minute returns are tiny
(1-minute sd ~8 bps) and strongly mean-reverting -- after a sharp rise the
price falls back, and after a sharp drop it bounces. A full-size round trip
costs ~26 bps, so the bot only trades when the move it is fading is much
bigger than that cost.

Rules (all integer arithmetic, no clock, no environment, no randomness):
  * Flat and the last 15 closes fell by >= 100 bps: buy with all cash
    (one position, 100% of equity). The drop is measured on closes, with
    exact cross-multiplication, so the decision is identical every run.
    100 bps was picked over 80/90/105/110/120 on the dev window: 80 bps
    churns into the decline (+1.08 USDC), 105+ misses the bounce trades
    (-9.20 USDC), 95-100 bps give the same four trades (+4.60 USDC).
  * Holding: sell the whole position when its value is >= +150 bps over
    its cost (fees included), <= -300 bps under its cost, or after 60
    bars held -- whichever comes first.
  * Never enter in the last 60 bars of the scored window: a fresh position
    there would pay a round trip for no time to earn it back.
  * max_slippage_bps 100 on every order: far above the largest 1-minute
    move in the dev window (~35 bps up), so fills are not rejected for
    ordinary moves, but a violent gap cannot fill at a disastrous price.

The bot keeps its own close history (the SDK state only remembers the
latest bar) and tracks the entry batch from when the position first
appears in the account, so the hold limit counts from the fill.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))

import makefun_bars

SYMBOL = "CBBTC"
DROP_WINDOW = 15          # bars over which the entry drop is measured
DROP_BPS = 100            # enter when the close fell >= 100 bps in the window
TP_BPS = 150              # take profit: value >= cost + 150 bps
SL_BPS = 300              # stop loss: value <= cost - 300 bps
MAX_HOLD_BARS = 60        # time exit: sell after 60 bars held
MAX_SLIPPAGE_BPS = 100    # bound on the move from the latest close
NO_ENTRY_AFTER = 1380     # scored-window bars after which no new entry
MIN_NOTIONAL = 1_000_000  # 1 USDC, in quote units

_closes = []              # closes seen so far, oldest first (ints)
_entry_seq = None         # seq of the batch where the position first appeared


def on_batch(state, batch):
    global _entry_seq
    bar = state.latest.get(SYMBOL)
    if bar is not None:
        _closes.append(int(bar["c"]))
    if state.warming_up:
        return []

    held = state.positions.get(SYMBOL)
    if held is not None:
        if _entry_seq is None:
            _entry_seq = state.seq
        value = state.value(SYMBOL, held.qty)
        cost = held.cost
        if value * 10_000 >= cost * (10_000 + TP_BPS):
            _entry_seq = None
            return [{"side": "sell", "symbol": SYMBOL, "qty": held.qty,
                     "max_slippage_bps": MAX_SLIPPAGE_BPS}]
        if value * 10_000 <= cost * (10_000 - SL_BPS):
            _entry_seq = None
            return [{"side": "sell", "symbol": SYMBOL, "qty": held.qty,
                     "max_slippage_bps": MAX_SLIPPAGE_BPS}]
        if state.seq - _entry_seq >= MAX_HOLD_BARS:
            _entry_seq = None
            return [{"side": "sell", "symbol": SYMBOL, "qty": held.qty,
                     "max_slippage_bps": MAX_SLIPPAGE_BPS}]
        return []

    _entry_seq = None
    if state.seq - state.warmup_bars > NO_ENTRY_AFTER:
        return []
    if len(_closes) >= DROP_WINDOW + 1:
        now = _closes[-1]
        then = _closes[-1 - DROP_WINDOW]
        if now * 10_000 <= then * (10_000 - DROP_BPS):
            cash = state.cash
            if cash >= MIN_NOTIONAL:
                return [{"side": "buy", "symbol": SYMBOL,
                         "notional_quote_units": cash,
                         "max_slippage_bps": MAX_SLIPPAGE_BPS}]
    return []


makefun_bars.run(on_batch)

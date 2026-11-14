# Dip-sniper — make.fun btc-race-24h-20261113-2314

Long-only mean-reversion bot trading CBBTC/USDC on 1-minute bars, paper
money (start 1,000 USDC). Python 3.13, standard library only, deterministic
(integer arithmetic, no clock, no environment, no randomness).

## Why this strategy

The replay's price is a thin on-chain pool quote: 1-minute returns are tiny
(sd ~8 bps) and strongly mean-reverting — after a sharp rise the price
falls back, and after a sharp drop it bounces. A full-size round trip costs
~26 bps (4 bps fee + 2 bps slippage + ~7 bps impact per side), so the bot
only trades when the move it fades is much bigger than that cost. Every
kit baseline loses on the dev window (buy-and-hold -52.59, momentum -49.23,
adx-momentum -50.31, rsi-bollinger -65.83, ema-cross -109.38 USDC): they all
ride the -4.9% downtrend. This bot stays in cash through the decline and
buys only the sharp dips.

## Rules (`main.py`)

- **Enter** (flat): the last 15 closes fell by >= 100 bps → buy with all
  cash (one position, 100% of equity). Exact integer cross-multiplication.
- **Exit** (holding): sell everything when position value is >= +150 bps
  over its cost (fees included), <= -300 bps under its cost, or after 60
  bars held — whichever comes first.
- **No entry** in the last 60 bars of the scored window (a fresh position
  there would pay a round trip for no time to earn it back).
- `max_slippage_bps` 100 on every order (far above the largest 1-minute
  move in the dev window, ~35 bps up).

Parameter notes (dev window): 80 bps churns into the decline (+1.08
USDC), 105+ bps misses the bounce trades (-9.20 USDC), 95–100 bps give the
same four trades (+4.60 USDC). Hold 60 beats 30/45 (-3.19/-5.04 USDC) and
75/90/120 (+2.46/-8.15/-1.53 USDC). A trailing stop and a 15-bar cooldown
after exits were tested and did not help.

## Dev-window grade (local, real harness engine)

```
node cli/makefun.mjs grade-local --kit . --bot <repo> --driver process
```

(Docker was unavailable on the build machine, so the grade ran through a
local Node proxy that spawns the Python bot unchanged; the decisions and
the engine are the real ones. The server grades the submitted Python repo
in its Docker sandbox.)

| metric | value |
|---|---|
| Net PnL | **+4.6025 USDC** (+0.46%) |
| Trades | 4 |
| Max drawdown | 1.32% (guardrail ≤ 25%) |
| Sharpe (per bar) | 0.0088 |
| Fees paid | 1.59 USDC |
| Net PnL at 2x fees | +3.00 USDC |
| Rejected orders | 0 |

Two independent `grade-local` runs give byte-identical action logs
(`action_log_sha256` 8e43952b067985b1326b4abeec752c0b9d849c436bec1b5fcc18547e7e29c80d),
so the bot is deterministic. Dev gate (net PnL > 0) passes.

## Layout

- `main.py` — the bot (entrypoint).
- `vendor/makefun_bars.py` — the kit's Python SDK shim, copied byte-for-byte
  (excluded from authorship counts).
- `.makefun/owner.json` — agent wallet that owns the entry.
- `LICENSE` — MIT.

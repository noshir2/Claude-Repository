# Wheel Planner

Answers one question before you click Sell: **is this put or call worth the cash it ties up, and what
are my own rules saying about it?** (Wheel Tracker tells you how it went; this tells you what you are
about to do.)

You type the numbers Webull shows on the option chain. The tool prints the return on the cash it ties up,
the cushion, the break-even, a rough chance of assignment, and fires your own written rules back at you
as plain sentences. It never logs in anywhere and never uploads anything.

## How to use it

On Windows type `python` (or `py`) where these examples say `python`; on a Mac type `python3`.
Run everything from the repo folder (the one that holds `wheel_planner` and `wheel_tracker`).

1. **The fast way**, one line per candidate, numbers copied from the chain:
   `python -m wheel_planner compare --candidate AAA,P,45,2026-11-20,1.00,50,60`
   The order is `ticker,type(P/C),strike,expiry,premium,price[,iv%[,cost_basis]]`. Repeat `--candidate`
   to compare several.
2. **The side-by-side way**: copy `samples/wheel_planner_candidates.csv` to `data/candidates.csv` (create the
   `data/` folder next to `wheel_planner` if it is not there yet), edit it in Excel (header: `ticker,type,strike,expiry,premium,price,iv,cost_basis,note`, optional 10th column
   `earnings`), then `python -m wheel_planner compare data/candidates.csv`. Dates are `YYYY-MM-DD`; if
   Excel saves the expiry back as `11/20/2026` that is read too, and the echo prints it as `2026-11-20`.
3. Open `wheel_planner_report.html` for the picture version, or open
   `wheel_planner/wheel_calculator.html` on your phone next to the chain (see "Opening it on a phone").
4. **Thinking about a roll**:
   `python -m wheel_planner roll --old 45,2026-10-16,1.00,2.50 --new 43,2026-11-13,3.20 --price 44.10 --iv 60`
   (`--old` = strike,expiry,premium you received,buyback price; `--new` = strike,expiry,credit).
5. **Expiry week**: `python -m wheel_planner expiry data/your_webull_export.csv --price AAA=44.10 --cash 2000`
   uses the same Webull order-history CSV that Wheel Tracker reads.

Try it first on the made-up samples (the `--today` flag pins the date so the sample numbers never drift;
leave it out for real use):

```
python -m wheel_planner compare samples/wheel_planner_candidates.csv --flags samples/wheel_planner_flags.txt --today 2026-10-21 --buying-power 6000 --account 20000 --monthly-goal 500
python -m wheel_planner compare --candidate AAA,P,45,2026-11-20,1.00,50,60 --today 2026-10-21 --html ""
python -m wheel_planner roll --old 45,2026-10-16,1.00,2.50 --new 43,2026-11-13,3.20 --price 44.10 --iv 60 --today 2026-10-14
python -m wheel_planner expiry samples/wheel_planner_orders.csv --price AAA=44.10 --cash 2000 --today 2027-11-10
```

Your real files go in `data/` (ignored by git): `data/candidates.csv`, `data/flags.txt` (your per-ticker
notes, `TICKER: note`), and your Webull export. `wheel_planner_report.html` is ignored by git too.

No installs needed (Python 3.11+, standard library only). To run the checks:
`pip install pytest` then `python -m pytest tests/test_wheel_planner.py -q`.

## What the numbers mean

- **Inputs you typed** come first in every report. One wrong IV or price silently changes every number
  below it, and the echo is the only defence.
- **Collateral** is the cash Webull holds. For a cash-secured put it is strike x 100 per contract; Webull
  reserves the full strike and the premium does not reduce the hold. For a covered call it is your cost
  basis x 100 when you typed one, else today's price x 100 with a note saying so.
- **Premium** = premium per share x 100: what lands in cash when the order fills.
- **Return** = premium / collateral. This is "return on collateral", the number most retail calculators
  show and the one Wheel Tracker uses for finished trades, so planned and realized returns compare.
  (A variant, "return on net cash" = premium / (collateral - premium), looks slightly higher; it only fits a
  broker that nets the premium against the hold, which Webull does not.)
- **Annualized** = return x 365 / days to expiry. It says what the rate would be if you could repeat this
  trade all year; it is not a promise. Days are calendar days (never less than 1) because the cash is
  tied up on weekends too.
- **DTE** = calendar days from today to expiry. **$/day** = premium / DTE.
- **Cushion** for a put = (price - strike) / price: how far the stock can fall before the strike is hit.
  The drop that reaches your break-even is a little bigger (cushion plus premium / price). For a call the
  same column shows the **upside to the strike** = (strike - price) / price, marked with ^ in the text table.
- **Break-even**: put = strike - premium (your effective purchase price if assigned); call = cost basis -
  premium. Same meaning as the break-even in Wheel Tracker.
- **1-sigma move** = price x IV x sqrt(DTE / 365): the move inside which the stock finishes about 68% of
  the time if IV is right. Two of them cover about 95%.
- **Rough odds ITM** = the chance the option finishes in the money at expiry: N(-d2) for a put, N(d2) for
  a call, from the Black-Scholes formula with the risk-free rate (`--rate`, default 4%, roughly the 4-week
  T-bill) and no dividends. It is "rough" because it assumes a lognormal stock with no earnings jumps, no
  skew and no early assignment; it is the risk-neutral figure, and real-world odds for puts tend to run a
  bit lower. It is **not** the chance of touching the strike before expiry, which is roughly double.
  With no IV typed the column says `n/a (no IV typed)`. If you add a `delta` column instead, |delta| is
  used and labelled, which overstates the odds a little for out-of-the-money options.
- **Net credit** on a roll = credit for the new contract - buyback of the old one (per share; x100 per
  contract). **Total premium collected** = everything received minus everything paid on the position.
  **New break-even** = new strike - total collected. **Added days** = new expiry - old expiry.
  **Annualized on the extension** = net credit / new strike x 365 / added days: what the extra time pays.
- **The roll sentence** states one of your rules: "This roll pays you for the extra time" when the net is a
  credit and the break-even did not get worse; "You are paying to delay, not to improve" on a net debit;
  "Net credit but break-even got worse: only if you want to keep the shares" when you rolled up for a credit.
- **If called away** (what-if tab) = (call strike - cost basis + call premium) x shares: the total gain or
  loss on the shares if that first covered call is assigned. When the call strike is below your basis the
  flag says the loss you would lock in, or the gain if the premium more than covers the gap.
- **Assignment cash** = strike x 100 for every open short put in your export (contracts past expiry are
  dropped; buybacks are netted). The shortfall line compares it with the cash you typed.
- **The income-goal sentence** = monthly goal x 12 / best annualized rate in the table: the collateral that
  would have to be working all month at that rate. Rates that high rarely repeat all year; it is a scale
  check, not a plan.

## Your rules (the flags)

Flags are sentences that quote the rule and the threshold that fired. The tool applies rules you wrote; it
does not give advice and never prints a verdict.

| Rule | Default | Change it with |
|---|---|---|
| Ticker is on the leveraged-ETF list | `wheel_planner/leveraged_etfs.txt` (ProShares/Direxion daily 2x/3x funds and a few single-stock 2x funds) | edit the file; `--leveraged other.txt` |
| Expiry too far out | 45 days | `--max-dte 30` |
| Covered-call strike below your cost basis | always on when a cost basis is typed; says the loss you would lock in (or the gain, if the premium covers the gap) | type the right cost basis |
| Collateral above your buying power | off; puts only, because a covered call is written against shares you already own and uses no buying power | `--buying-power 5000` |
| Collateral above N% of your account | 25% | `--account 20000 --max-pct 10` |
| Rough odds of finishing in the money above N% | 35% | `--max-odds 30` |
| Expiry crosses the earnings date you typed | on when the `earnings` column is filled; one line lists tickers with a blank | fill the column |
| Your own note for a ticker | `data/flags.txt`, one line per ticker `TICKER: note` | `--flags samples/wheel_planner_flags.txt` |

`--sort annualized|cushion|odds` changes the order (default annualized). `--html ""` skips the HTML report.

The leveraged-ETF list is public knowledge, editable, and will go stale as funds launch and close; after
editing it run `python -m wheel_planner.embed_lists` so the calculator page carries the same list.

## Three worked examples

These exact inputs and outputs are pinned by `tests/test_wheel_planner.py` and recomputed by the
calculator page's self-check panel, so the Python and the page cannot drift apart unnoticed.

**A. A plain put.** Price 50, strike 45, premium 1.00, 30 days to expiry, IV 60%, rate 4%.
Collateral $4,500; premium $100; return 100 / 4500 = 2.22%; annualized 2.22% x 365 / 30 = 27.0%;
$3.33 per day; cushion (50 - 45) / 50 = 10.0%; break-even 44.00; 1-sigma move 50 x 0.60 x sqrt(30/365) =
$8.60; rough odds ITM: d2 = [ln(50/45) + (0.04 - 0.18) x 30/365] / (0.60 x sqrt(30/365)) = 0.5456, so
N(-0.5456) = 29.3%. (With a 0% rate instead of 4% the odds would read 29.9%: the rate matters little.)

**B. A roll.** Old 45 put expiring 2026-10-16, received 1.00, buy it back for 2.50; new 43 put expiring
2026-11-13 for 3.20; today 2026-10-14; price 44.10; IV 60%.
Net credit 3.20 - 2.50 = +0.70 per share (+$70); 28 days added; total collected 1.00 + 3.20 - 2.50 = 1.70;
break-even 44.00 -> 43 - 1.70 = 41.30; annualized on the extension 0.70 / 43 x 365 / 28 = 21.2%; rough
odds for the new put 46.8%. Sentence: "This roll pays you for the extra time (net credit > 0 and break-even
not worse)."

**C. A covered call below cost basis.** Price 50, cost basis 52, strike 51, premium 0.80, 10 days, IV 25%.
Collateral $5,200 (your basis, not the price); premium $80; return 1.54%; annualized 56.2%; break-even
52 - 0.80 = 51.20; upside to strike 2.0%; rough odds of finishing ITM 31.8%. Flag: "if called you lock in a
loss of $20.00 after keeping the $80.00 premium" (basis 52 - strike 51 = $100 on the shares, minus $80).

Two more checks live in the same self-check block: the Black-Scholes reference case (price 40, strike 37.5,
IV 60%, 30 days, rate 4% -> put odds 37.9%, put delta -0.316, 1-sigma move $6.88) and an assignment
what-if (45 put with 1.00 kept -> 100 shares at a $44.00 basis; a first 46 call for 0.90 pays $90 = 2.05%
of the basis and +$290 if called away).

## The calculator page

`wheel_planner/wheel_calculator.html` is one file with no internet connection needed: double-click it.
Three tabs: **Compare** (up to 4 candidates, same columns and the six threshold flags; the `flags.txt` notes
and the earnings check are CLI-only, so on expiry Friday your biotech note shows in the terminal, not here),
**Roll**, and **Assignment what-if** (shares you would own, cost basis, and what a first covered call would
return). Your last inputs are remembered in that browser only (localStorage keys starting with
`wheel_planner.`); the Reset button on each tab clears them. The self-check panel at the bottom shows green
"matches" for each worked example when the page's math agrees with the tested Python.

### Opening it on a phone

- **Android**: Chrome opens the saved .html file directly (Files app > tap it, or type the `file://` path).
- **iPhone**: the Files preview does not run JavaScript, so the page looks dead. Use Share > Open in Safari,
  AirDrop it from a Mac and open it in Safari, or host the file somewhere (GitHub Pages works: this public
  file holds no personal data).

## Limits

- No live prices. You type everything, and the report echoes it so typos show.
- The odds are a rough model: lognormal, no dividends, no earnings jumps, no skew, no early assignment.
  Early assignment is not modelled anywhere (short calls near an ex-dividend date are the usual case).
- Covered calls use the cost basis you type; the tool cannot know your adjusted basis from past premiums
  (Wheel Tracker's break-even gives you that number).
- The roll command is for short puts. For a covered-call roll the net credit and days are the same math,
  but the break-even depends on your cost basis.
- The expiry command counts a contract as open when sells minus buys is positive and the expiry has not
  passed. It cannot see assignments that already happened (Webull's export does not list them).
- Not tax or fee aware. Not investment advice: the flags are your thresholds, written when calm.
- Webull's help index suggests cash-secured puts need a margin-type account; check your account type.

## Where the rules/figures come from

Verify against Webull's current help pages and your own account before relying on any of this.

- Collateral held in full (strike x 100, premium credited separately): Webull help FAQ "What happens when
  you get assigned" (EU FAQ 1089) and Webull Learn's cash-secured put lesson.
- Return on collateral = premium / strike and annualized = x 365 / DTE: the convention used by TradesViz,
  QuantWheel and Benzinga calculators, and tastylive's return on capital (credit / buying power reduction).
  Wheel Tracker's `analyze.py` uses the same convention.
- Calendar-day DTE with T = DTE / 365: Macroption's Black-Scholes time-input note; tastylive on calendar vs
  trading days.
- Black-Scholes d1, d2, N(d2) as the risk-neutral probability of finishing in the money, delta as a cruder
  proxy: Wikipedia "Black-Scholes model"; tastylive and Cboe on delta as a probability gauge. N(x) is the
  `erf` example from the Python `math` module docs.
- 1-sigma expected move = price x IV x sqrt(DTE / 365): tastylive "What determines a stock's expected move".
- Risk-free rate default 4%: US Treasury daily bill rates, 4-week coupon-equivalent yield on 2026-10-20
  (4.00%; 13-week 4.18%). It changes daily; `--rate` overrides it.
- Roll math (net = new credit - buyback; new break-even = new strike - total credits) and "roll for a
  credit": tastytrade short-put page, QuantWheel "Rolling options for a credit", tastylive "Rolling Options".
- Covered-call break-even = cost basis - premium and the "strike below basis locks in a loss" rule:
  Webull Learn "Covered Call"; SpotGamma "Covered calls below cost basis".
- Leveraged ETF flag: ProShares UltraPro QQQ summary prospectus (SEC 497K) and Direxion's "Understanding
  Leveraged & Inverse ETFs" brochure (a flat index with a 3x fund down 4.5% over six days).
- Earnings flag: Option Alpha on IV crush; tastylive on event moves. Earnings dates must be checked on the
  company's investor page or your broker's calendar.
- Position-size cap: no authoritative number exists; tastylive studies tested 1-10% per trade. The 25%
  default is a placeholder for your own number.
- Auto-exercise at $0.01 in the money and the 4:30 PM ET do-not-exercise cutoff: OIC "Options Exercise"
  FAQ; Webull help FAQ 659 and 10614.

Estimates from numbers you typed; no live data; the odds are a rough model; this is not investment advice.

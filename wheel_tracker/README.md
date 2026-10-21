# Wheel Tracker

Answers one question: **are my cash-secured puts and covered calls actually making money?**

It reads the order-history file exported from Webull and reports cash actually made, split into
puts, calls, and stock gains/losses, by ticker and by month. Everything runs on your computer. It never
logs in anywhere and never uploads anything.

## How to use it

1. Export your order history from Webull as a CSV and save it in the `data/` folder
   (this folder is ignored by git, so your trades are never uploaded).
   Webull's menu names change; look for Orders > History > export/download.
2. Run: `python3 -m wheel_tracker data/your_file.csv`
3. Open `wheel_report.html` in your browser for the picture-friendly version.

Try it first on the made-up sample: `python3 -m wheel_tracker samples/sample_webull_orders.csv`

No installs needed (Python 3.11+, standard library only). To run the checks: `pip install pytest && pytest`.

## What the numbers mean

- **Made** = money from contracts that are finished (bought back, expired, or assigned), minus the cost
  of buying contracts back. Rolling a position just shows up as a buyback cost plus new premium.
- **Premium on open contracts** is shown separately. It is not yours until the contract ends.
- When a put is **assigned** you buy shares. No profit or loss exists on them until you sell them, so the
  report shows them under "Shares you still hold" with a **break-even price**: the share price where
  everything on that ticker nets to zero. Add `--price TICKER=PRICE` to see the current gain/loss on them.
- Fees and tax effects are **not** included. This is a cash view, not a tax report.

## Two things Webull's export may not tell the tool

- **Assignments.** If the export has no matching share purchase/sale, an option that ran past its
  expiry is counted as expired worthless. If you were actually assigned, put the contract symbol
  (e.g. `AAPL250117P00180000`) on its own line in `data/assigned.txt` and re-run. The report lists which
  contracts it assumed.
- **Shares bought before your export starts.** List them in `data/opening_shares.csv`
  (header: `ticker,shares,cost_per_share`) or the tool will warn that it can't value their sale.

## Limits

- Expects the usual Webull columns (Symbol, Side, Filled, Avg Price, Filled Time). If your file doesn't
  match, the tool prints the columns it found so the reader can be adjusted.
- Early assignment (before expiry) and short stock aren't handled.
- Long options you bought are tracked separately and don't count as wheel trades.

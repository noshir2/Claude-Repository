# Wheel Tracker

Answers one question: **are my cash-secured puts and covered calls actually making money?**

It reads the order-history file you export from Webull and reports the cash actually made, split
into puts, calls and share gains or losses, by ticker and by month. Everything runs on your own
device. It never logs in anywhere and never uploads anything.

## The easy way

The tracker lives on the options page, `wheel_planner/wheel.html` (one page holds the tracker and
the planner). Open it from the Start here page (`index.html`) or double-click the file.

1. Press the big **Try it with example data** button in section **1. How did my trades do?** (it is
   the first button on the page; the sections below it have their own, for the planner). The page
   loads a made-up Webull export and shows a finished report at once: a one-sentence verdict, then
   the totals.
2. Get your own file from Webull. How: in the Webull app or website open Orders, then History,
   and look for an export or download button; save the file (its name ends in .csv, a spreadsheet
   file). Menus move between versions, so the words may differ a little.
3. Choose that file in the box **Your Webull order history file (.csv)** in section 1, and read the
   verdict. (Section 5, Expiry week, has a box with the same label, but that one only checks whether
   you can afford assignment.) Every number on the page has a one-line meaning next to it; the fuller
   meanings are below.

## What the numbers mean

- **Made** = money from contracts that are finished (bought back, expired, or assigned), minus the
  cost of buying contracts back. Rolling a position (buying the old contract back and selling a new
  one) shows up as a buyback cost plus new premium.
- **Premium** is the cash you are paid for selling a put or call. **Premium on open contracts** is
  shown separately: it is not yours until the contract ends.
- When a put is **assigned** you buy the shares at the strike price. No profit or loss exists on
  them until you sell them, so the report shows them under "Shares you still hold" with a
  **break-even price**: the share price where everything on that ticker nets to zero. In the
  command-line version, add `--price TICKER=PRICE` to see the current gain or loss on them; on the
  page, type today's price where it asks.
- Fees and tax effects are **not** included. This is a cash view, not a tax report.

## Two things Webull's export may not tell the tool

- **Assignments.** If the export has no matching share purchase or sale, an option that ran past
  its expiry is counted as expired worthless. The report lists which contracts it assumed under
  "Please check". If one of them was actually assigned, tell the tool. On the page: paste the
  contract symbol (for example `AAPL250117P00180000`, the code Webull uses for one option contract)
  into the box **Contracts that were assigned**, one per line, and read the results again. In the
  command-line version: put the same symbols, one per line, in a text file named assigned.txt
  inside your data folder and run it again.
- **Shares bought before your export starts.** On the page, add a row under **Shares I owned before
  this export** (ticker, how many shares, what you paid per share). In the command-line version,
  list them in a spreadsheet file named opening_shares.csv in your data folder (first line:
  `ticker,shares,cost_per_share`). Without them the tool warns that it cannot value their sale.

## Limits

- Expects the usual Webull columns (Symbol, Side, Filled, Avg Price, Filled Time). If your file
  does not match, the tool prints the columns it found so the reader can be adjusted.
- Early assignment (before expiry) and short stock are not handled.
- Long options you bought are tracked separately and do not count as wheel trades.

## Advanced: the command-line version

The same math runs as a Python program (Python 3.11 or newer, standard library only, nothing to
install). Open a terminal (the text window where you type commands: on Windows search the Start menu for Command Prompt or PowerShell; on a Mac open Terminal) in the project folder (the one that holds this `wheel_tracker` folder);
on Windows type `python` or `py` where these lines say `python3`.

1. Export your order history from Webull as a CSV and save it in the `data/` folder (this folder is
   ignored by git, the program that copies files to GitHub, so your trades are never uploaded).
   Webull's menu names change; look for Orders > History > export/download.
2. Run: `python3 -m wheel_tracker data/your_file.csv`
3. Open `wheel_report.html` in your browser for the picture-friendly version.

Try it first on the made-up sample: `python3 -m wheel_tracker samples/sample_webull_orders.csv`

Options: `--assigned data/assigned.txt`, `--opening-shares data/opening_shares.csv`,
`--price TICKER=PRICE`, `--html FILE` (where to write the report), `--today YYYY-MM-DD`.

To run the checks: `pip install pytest` once, then `python3 -m pytest tests/test_wheel.py -q`.

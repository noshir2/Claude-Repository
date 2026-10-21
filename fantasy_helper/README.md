# Fantasy Lineup and Trade Helper

Answers three questions each week: **who do I start, is this trade good for my starting lineup, and
which pickup adds the most?** It uses the FantasyPros projection files you already download and your
league's own scoring. Everything runs on your own device; it never logs in anywhere and never uploads
anything.

## The easy way

Open `fantasy_helper/fantasy.html` from the Start here page (`index.html`) or double-click the file.

1. Press the big **Try it with example data** button. The page loads a made-up roster and made-up
   projection files and shows the best lineup at once, with the bench and the close calls under it.
2. Get your own files. How: on the FantasyPros website open Projections for the week, pick each
   position in turn (QB, RB, WR, TE, K, DST), and press the download or export button on each; six
   spreadsheet files (names ending in .csv) land in your Downloads folder. Menus move, so the button
   may be called "Export" or "Download CSV". Then, on the page, choose those six files under
   **1. Your projection files**, type your roster under **2. Your team** in the box **Your players,
   one per line** (write the position after a comma, as in "Passer Baker, QB"), and check
   **3. Your league's scoring and starting spots** against your league's settings page.
3. Press **Show my best lineup** and read the verdict sentence and the lineup. For a trade, open
   the **Is this trade good?** tab, tick the players you give, type the **Players you get**, and
   press **Check this trade**. For a pickup, open **Which pickup helps most?**, type the player
   under **One player you are thinking of adding** (or several under **Or compare several free
   agents**), and press **Rank the pickups**. Each builds its sentence from the numbers only.

## What the numbers mean

Words used below: a **projection** is FantasyPros' guess at a player's points this week; your
**roster** is everyone on your team; the **bench** is the roster players not in the starting
lineup; a **waiver pickup** is a free player you add.

- **Proj** (projected points) is recomputed by this tool from the stat columns in the file (yards,
  touchdowns, receptions, ...) using the points in YOUR scoring settings (`league.txt` in the
  command-line version; the scoring box on the page). It is not the FPTS column.
- **FantasyPros FPTS** is FantasyPros' own total, shown next to the bench for comparison only. It
  reflects whichever scoring tab (Standard / Half PPR / PPR; PPR means points per reception, a
  point for every catch) was selected when you downloaded. If it
  differs from Proj by more than 0.5 for any player, a "Please check" line names the player and
  both numbers, which usually means your scoring does not match the tab you downloaded with.
- **Floor** is the "low" row FantasyPros ships under each player, scored with your points. If a
  file has no low rows, floor equals projection and the report says so.
- **Ceil** (ceiling) is the "high" row when the file has one. When it does not, ceiling is
  estimated as projection + (projection - floor), and the report says for how many players that
  estimate was used. If a low row scores above the projection (or a high row below it), the floor
  (or ceiling) is set equal to the projection; this happens in some FantasyPros defense rows,
  whose high/low rows do not always agree with the main row, so lean less on defense floors and
  ceilings.
- **Best lineup** fills every starting slot in your settings to get the highest total Proj. It is
  an exact search over every legal combination, not a shortcut, so the FLEX really is the best
  leftover WR/RB/TE. Ties go to the higher floor. (Players who cannot possibly start, such as the
  sixth-best RB when only five slots can take a RB, are skipped before the search; that does not
  change the answer, it only keeps big dynasty rosters with extra flex slots instant.)
- **Floor lineup** is the same search run on Floor instead of Proj: the safest lineup. It is
  printed beside the best lineup, "same" where the player is the same, and the differences are
  listed in one line.
- **Close calls** are a starter and a bench player (eligible for that slot) whose Proj are within
  1.5 points of each other (the command-line option `--close` changes the gap). Those are the
  decisions worth a second look at the floors.
- **Bench** is everyone else who has a projection, sorted by Proj.
- **Not projected this week (bye or out?)** lists roster players who are not in any projection
  file. They are left out of the lineup and never scored as zero. Check for a typo, a bye week, or
  an injury.
- **Trade** compares your best lineup before and after the swap, this week and (with rest-of-season
  files, the command-line option `--ros`) rest of season. The change is the change in your
  starting lineup's total, not a sum of player values: a player who would sit on your bench adds
  0.0. "Starters out / in" names who leaves and enters the lineup, "starter points by position"
  shows where the points moved, and the **verdict sentence** is built only from those numbers. It
  does not say accept or reject; that is your call. If a player you get is not in the
  rest-of-season files, the rest-of-season number is not computed (it would describe a one-sided
  trade) and the report says so; a player you give who is absent there counts as 0.0 rest of
  season, with a note.
- **Waiver gain** is best lineup after the add (and drop) minus best lineup before. Candidates are
  ranked by that gain, so a 15-point receiver who would sit behind your starters ranks below a
  10-point kicker who would start. With no drop named, the lowest-projected bench player is assumed
  dropped.
- **Opponent line** (command-line option `--opponent-total`): if your best lineup projects above the
  opponent's number you are favoured and the line suggests leaning on the floor lineup; below it,
  leaning on the ceiling lineup.
- **Defense points allowed** with a fraction (a projected 17.2) uses the whole number (17) to pick
  the tier, the same way FantasyPros' own FPTS does on the one weekly row we could check.
- **Weekly or season file?** The two exports have identical columns, so the tool judges by size (a
  QB with more than 100 pass attempts is a season total) and prints what it assumed. When there is
  no QB file it falls back to RB rush attempts over 60, WR/TE receptions over 30, K field-goal
  attempts over 10 or defense sacks over 12; those cutoffs are this tool's own rule of thumb, not
  FantasyPros'. For season-style files the defense points-allowed tier is skipped, because PA there
  is a season total, not one game's.
- **Kickers**: the file has no field-goal distances, so every field goal is worth the `fg` value in
  your scoring. The sample uses 3.3 as an average of Yahoo's 3/4/5 tiers; FantasyPros' own FPTS
  uses a flat 3, so kickers show a small, expected mismatch note. Projected misses (FGA minus FG)
  use `fg_missed`.

## The matched-names list

The tool must connect your roster names to the names in the projection files. Names are compared
ignoring case, punctuation and suffixes (Jr., Sr., II, III, IV), so "AJ Sample" finds "A.J. Sample Jr.".
A defense can be written as the full team name, the city, the nickname, "City D/ST", or the team
abbreviation (CHI). Anything that is not an exact match is printed as **I matched X to Y** so you can see
what it decided; a close-spelling match needs 85% similarity. Anything it cannot connect is printed as
**COULD NOT FIND** and listed under "not projected", never silently scored as zero. Fix the spelling in
your roster (copy it from the FantasyPros file) and run again. If the name is in a projection file but
under a different position than your roster says (a tight end listed as WR, say), the COULD NOT FIND
line says which file he is in; fix the position or leave it blank. A **Names I could not use** list covers
the rest: a duplicate row in your roster, a waiver candidate who is already on your roster, a name
given twice (counted once), or a player you get, or a candidate, who is in no projection file. For
the player you give or drop either spelling works, the one in your roster or the one in the
projection file; a roster player who is not projected this week (bye or out) can still be given or
dropped and counts as 0.0 for this week's comparison.

## Two leagues

Everything is per league. On the page, change the roster and scoring boxes for the other league.
In the command-line version everything is per `--league` folder: make `data/league2/` with its own
`roster.csv` and `league.txt`; copy the sample `league.txt` and change the scoring and slot lines.
The samples ship two leagues with different rules (`fantasy_helper/samples/league1` half-PPR Yahoo
defaults, half a point per catch; `fantasy_helper/samples/league2` full PPR, a point per catch,
6-point passing TDs, three WR) to show that the same files produce
different lineups. Slots are editable too: any `NAMEFLEX = 1` line with a `NAMEFLEX_FROM = QB,WR,RB,TE`
line adds another flex type (a superflex, for example).

## Limits

- Projections are FantasyPros' opinion; the tool ranks them under your scoring, it does not predict.
- The file layout was built from FantasyPros' pages and public exports from 2019-2026, not from your own
  files. The first real file may need a one-line fix in `fantasy_helper/parse.py`; when a file does not
  match, the tool prints the header it found and the header it expected and stops.
- Scoring it cannot compute from the file is ignored: 2-point conversions, return touchdowns, blocked kicks,
  field-goal distance tiers, kicker misses by distance, defensive yards allowed. Expect small differences
  from your league's final numbers.
- Only slots defined in your scoring settings; the default is Yahoo's QB, RB x2, WR x2, TE, W/R/T flex,
  K, DEF. Yahoo's 2026 optional "Offense" roster spot has no FantasyPros projection and is not supported.
- No opponent, bye or injury information is in the projection export; a player on bye is simply absent.
  Bye-week coverage after a trade is therefore not computed.
- Football only; fantasy basketball files are a different shape. Dormant January to August.

## Where the rules and figures come from

- FantasyPros CSV column order per position, the `high`/`low` rows, the blank second row, thousands
  commas, and the empty Team cell on defense rows: the FantasyPros projection pages
  (fantasypros.com/nfl/projections/qb.php and the other positions) and more than twenty public exports of
  those files on GitHub, 2019-2026. Weekly and season exports share the same header.
- What the FPTS column is made of: FantasyPros' scoring page (fantasypros.com/scoring-settings/), checked
  by arithmetic on exported rows (passing 1 per 25 yards, 4 per TD, -1 INT; 1 per 10 rushing/receiving
  yards, 6 per TD; 0 / 0.5 / 1 per reception by tab; -2 fumble lost; K flat 3 per FG and 1 per XP; DST 1
  sack, 2 INT, 2 FR, 6 TD, 2 safety plus the points-allowed tier on weekly rows).
- Default starting slots and scoring in the sample `league.txt`: Yahoo's "Default league settings in
  Fantasy Football" help page (help.yahoo.com/kb/SLN6489.html) and the W/R/T flex definition
  (help.yahoo.com/kb/SLN6500.html). That page is undated and about three years old, and any commissioner
  can change the settings, so verify every line against your league's settings page for the 2026 season.
- The NFL team abbreviation table used only for "CHI"-style defense names is general knowledge, not from a
  verified source: if one looks wrong, write the city or nickname in your roster instead.
- FantasyPros' Terms of Use allow a single personal copy of their data. Download the files yourself, keep
  them in `data/` (ignored by git, the program that copies files to GitHub, so they are never
  uploaded), and do not publish them. The sample files here are invented players.

Projections are FantasyPros' estimates as of your download; this tool only ranks them under your scoring.

## Advanced: the command-line version

The same math runs as a Python program (Python 3.11 or newer, standard library only, nothing to
install). Open a terminal (the text window where you type commands: on Windows search the Start menu for Command Prompt or PowerShell; on a Mac open Terminal) in the project folder (the one that contains `fantasy_helper`) and run it from there. On Windows
type `python` or `py` instead of `python3`; on a Mac, `python3`.

1. On FantasyPros, open the projections for the week, pick each position (QB, RB, WR, TE, K, DST), click
   the download/export button, and save all six files into one folder, for example `data/week8/` (the
   folder name is yours). The tool finds each file by the position word in its name
   (`FantasyPros_Fantasy_Football_Projections_QB.csv` and so on). The `data/` folder is ignored by git
   (the program that copies files to GitHub), so your files are never uploaded.
2. List your roster once in `data/league1/roster.csv` (header `player,position`, one player per line,
   position QB/RB/WR/TE/K/DEF next to it; blank is allowed) and copy
   `fantasy_helper/samples/league1/league.txt` to `data/league1/league.txt`. Check every line of it against
   your league's settings page: starting slots at the top, points per stat below.
3. Run one of these.

   Best lineup:
   `python -m fantasy_helper lineup --league data/league1 --proj data/week8`

   Trade check (repeat `--give` / `--get` for multi-player trades; add `--ros data/ros` with a folder of
   rest-of-season projections to see the rest-of-season effect too):
   `python -m fantasy_helper trade --league data/league1 --proj data/week8 --give "Player A" --get "Player B"`

   Waiver pickup (drop someone by name, or the tool assumes your weakest bench player goes):
   `python -m fantasy_helper waiver --league data/league1 --proj data/week8 --add "Player X" --drop "Player Y"`

   Rank several pickups from a text file with one name per line:
   `python -m fantasy_helper waiver --league data/league1 --proj data/week8 --candidates data/free_agents.txt`

   Each run prints the answer and writes `fantasy_report.html` (open it in your browser). Add `--html ""` to
   skip the file, `--close 2` to widen what counts as a close call, and on `lineup`,
   `--opponent-total 115` for a one-line floor-or-ceiling lean.

Try it first on the made-up sample:

```
python3 -m fantasy_helper lineup --league fantasy_helper/samples/league1 --proj fantasy_helper/samples/week8
python3 -m fantasy_helper trade --league fantasy_helper/samples/league1 --proj fantasy_helper/samples/week8 --ros fantasy_helper/samples/ros --give "Runner Charlie" --get "Catcher Charlie"
python3 -m fantasy_helper waiver --league fantasy_helper/samples/league1 --proj fantasy_helper/samples/week8 --add "Catcher Baker" --candidates fantasy_helper/samples/free_agents.txt
python3 -m fantasy_helper lineup --league fantasy_helper/samples/league2 --proj fantasy_helper/samples/week8
```

**Opening fantasy_report.html on a phone.** Email or message the file to yourself. Android Chrome
opens it directly. On an iPhone, the Files app preview does not run page styling well; use Share >
Open in Safari, or just read the text output. The page has a small "Lineup card" at the bottom
sized to screenshot into a group chat (no league name on it).

To run the checks: `pip install pytest` then `python3 -m pytest tests/test_fantasy_helper.py -q`.

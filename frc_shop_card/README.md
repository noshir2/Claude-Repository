# FRC Electrical Shop Card

One page for the shop wall, your binder, and students' phones. It answers the questions a new
electrical mentor gets asked most: what gauge, what breaker, why did the robot brown out, how do I
crimp this, what is safe. Everything runs in the browser from one file. It never connects to anything.

## How to use it

1. Double-click `frc_shop_card.html`. It opens in any browser (Chrome, Safari, Edge, Firefox).
   No install, no Wi-Fi, no account.
2. Pick a tab: **Safety**, **Rules** (breaker to gauge), **Reference**, **Calculators**,
   **Flashcards**, **Print**.
3. To print the one-page cheat sheet or this week's warm-up, open the **Print** tab, choose what to
   print, and press Print (it opens the browser's normal print dialog).

**Opening it on a phone.** Android Chrome opens the file directly (copy it to the phone, then open
it from Files or Downloads). On an iPhone the Files app preview shows the page but does not run its
JavaScript, so the tabs and calculators stay dead: open it in Safari instead (Share > Open in
Safari, or AirDrop it and choose Safari), or host the file somewhere and open that link. The file
holds no personal data, so hosting a copy is fine.

**The calculators from the command line (optional).** Open a terminal in the repository folder
(the folder that contains `frc_shop_card` and `tests`). On Windows type `python` or `py` instead
of `python3`; on a Mac, `python3`. No installs needed (Python 3.11 or newer).

```
python3 -m frc_shop_card check
python3 -m frc_shop_card vdrop --awg 6 --amps 120 --feet 10
python3 -m frc_shop_card brownout --battery-mohm 15 --path-mohm 8 --amps 300 --threshold 6.8
python3 -m frc_shop_card battery-r --open 12.6 --loaded 11.9 --amps 50
python3 -m frc_shop_card short --battery-mohm 12 --path-mohm 3
python3 -m frc_shop_card gauge --breaker 40
python3 -m frc_shop_card gauge --fuse 10
python3 -m frc_shop_card ohm --volts 12 --ohms 4
python3 -m frc_shop_card i2t --amps 60 --seconds 2
python3 -m frc_shop_card awg-table
python3 -m frc_shop_card warmup --week 2 --seed 7
```

Each command prints the same sentence the page shows for the same inputs.
To run the checks: `pip install pytest` once, then `python3 -m pytest tests/test_frc_shop_card.py -q`.

## What is on the card

- **Safety.** The seven things to say on day one: a shorted battery is a burn and fire hazard, no
  rings or lanyards, measure voltage not current, two hands and a capped SB50, charger lights,
  ESD, and "warm means wrong". The tab says plainly that it is not a substitute for your team's
  safety training.
- **Rules.** The breaker-or-fuse-rating to minimum-wire-gauge table from the Game Manual, each
  row tagged with the season it came from and "verify", plus a short note on why this table is
  not the house-wiring table.
- **Reference.** Copper resistance per foot for AWG 6 to 24 (computed, not typed), an EXAMPLE
  team-standards table, the rest of the power rules (battery, charger, roboRIO and radio supply,
  legal breakers and fuses, wire colours), connector ratings (Molex SL, Anderson SB50/SB120, CAN
  termination), REV PDH and Mini Power Module ratings, brown-out thresholds, ferrule colour codes,
  and battery numbers. There is no torque table and no motor stall-current table: see Limits.
- **Calculators.** Voltage drop, brown-out (both directions), battery internal resistance, short
  circuit, Ohm's law, I^2t, and a breaker-to-gauge lookup that reads the rule table above it.
  A self-check line confirms the page's math agrees with the golden examples in the data block.
- **Flashcards.** 50 to 70 cards tagged by preseason week 0 to 10. Number cards are generated from
  the table rows, so a corrected number fixes the card too.
- **Print.** A one-page cheat sheet, or a weekly warm-up (five questions), its answer key on a
  separate page, and an exit-ticket template.

## What the numbers mean

- **Voltage drop.** Current leaves on the positive wire and returns on the negative one, so a
  10 ft one-way run is 20 ft of wire. Volts lost = amps x round-trip ohms. The percentage is of
  the 12 V nominal bus. Watts = amps^2 x ohms is heat in the wire. Example: 120 A through 10 ft of
  6 AWG (20 ft round trip, 7.9 mohm) loses 0.95 V, about 7.9% of 12 V, and the wire dissipates
  114 W.
- **Brown-out.** A battery is a 12.6 V source in series with its own internal resistance; the
  SB50, lugs and cable add a few more milliohms. Bus voltage = open-circuit volts - amps x total
  ohms. The inverse answers "what current pulls the bus down to the threshold": (open-circuit
  volts - threshold) / total ohms. With a 15 mohm battery and 8 mohm of path, 300 A gives 5.7 V,
  and 6.8 V is reached at 252 A. The roboRIO 2 disables outputs at 6.75 V by default (6.8 V is
  where its 6 V rail starts to droop); SystemCore's number is provisional.
- **Battery internal resistance.** (open-circuit volts - loaded volts) / load amps. 12.6 V
  resting, 11.9 V at 50 A = 14 mohm. The reading includes whatever leads and connectors sit between
  the meter and the battery plates, which is why a handheld tester reads 15-23 mohm on a battery
  whose datasheet says about 12.
- **Short circuit.** Bolted-fault amps = open-circuit volts / (battery + path ohms). 12.6 V across
  12 + 3 mohm is 840 A. The battery alone heats at amps^2 x its own resistance (8.5 kW); the whole
  loop at volts x amps (10.6 kW). That is why a wrench across the terminals glows and why 12 V can
  still burn you: not shock, not arc flash, but current and heat.
- **I^2t.** amps^2 x seconds, the quantity breaker let-through curves are drawn in. The card
  prints no trip times or curves, only the number you type, because trip behaviour depends on the
  breaker family, temperature and history; read the manufacturer's curve.
- **Gauge lookup.** Finds the tightest "up to X amps" row of the rule table for a breaker or a
  fuse; a 120 A breaker reads the main-path row (battery, main breaker, PD input: 6 AWG). A
  rating the table does not cover prints "not in the table, see the manual" rather than guessing.
- **AWG table.** Diameter from the defining formula d = 0.127 mm x 92^((36 - n)/39), area from
  that, resistance from copper resistivity 1.724e-8 ohm-m at 20 C, solid wire. Stranded wire reads
  2-5% higher; NEC Chapter 9 Table 8 is at 75 C and reads about 22% higher again. The ampacity
  columns are rules of thumb from a public wire table; the rule table decides what you may fit.
- **Why the FRC table is not the house-wiring table.** Short runs in free air, intermittent loads,
  fast snap-action breakers, and 12 V: at 12 V the practical limit is voltage drop, not insulation
  heating.

## Where every number comes from

Every row carries a `source` and a `tag`:

- **physics**: generated from a formula (AWG, resistance, voltage drop). The checker recomputes
  the AWG table and fails if the block drifts more than 2% from the formula.
- **rule**: the 2026 FRC Game Manual (REBUILT), Version TU22, section 8.6 (R601-R626), with the
  rule number in the source and a `season` tag. The manual is re-issued every January; verify
  against the current season's manual before teaching or wiring.
- **vendor**: a named public datasheet or page (Anderson SB50/SB120 datasheets, Molex SL housing
  and terminal datasheets, REV PDH and MPM specification pages, MK ES17-12 datasheet, WPILib docs
  for brown-out and wiring practice, AndyMark's CBA page, Battery University, DIN 46228-4 as
  tabulated by RS and TE, Limelight's SystemCore alpha specification). Vendor numbers change;
  re-check them when a part changes.
- **example-team-standard**: invented, generic examples that satisfy the rule table. They are not
  attributed to any team. Edit them to match your team's own document, which should stay out of
  this public repository (keep it in `data/`, which git ignores, or anywhere else).

Where a commonly quoted number could not be tied to a document, it was left out rather than
guessed: the torque table is empty (it tells you to use the vendor datasheet), the motor table is
empty (type a datasheet stall current into the brown-out calculator instead), and the Molex SL
crimp row says "see the Molex crimp specification for your terminal part number" without numbers.
The Battery Beak readings and the 7.5 A / 10.5 V test profile are labelled community practice; the
"12.5 Ah or less is not for competition" row is labelled EXAMPLE team policy.

## Changing a number

Open `frc_shop_card.html` in Notepad (or any text editor). The block at the top, between
`<script id="card-data" type="application/json">` and `</script>`, holds every table and card,
one row per line. Change the number, keep the quotes and commas, save, and reload the page. Then
run `python -m frc_shop_card check` (Windows: `python` or `py`; Mac: `python3`). It prints
`card data OK: ...` or lists exactly which row lost its source, which rule row lost its season,
which card lost its week, which id or card is duplicated, or which calculator disagrees with a
golden example. A row with no source does not render on the page, on the printed cheat sheet, or
as a generated flashcard. A battery row may carry an optional `print_item`, a short name used
on the printed cheat sheet (otherwise the sheet prints the item text up to the first `;` or `(`).

If the page shows a red box saying the block is not valid JSON, a comma or quote went missing;
the checker points at it.

Sections of the block: `safety`, `rule_table`, `reference_tables`, `team_standards_example`,
`motors`, `battery`, `awg_table`, `cards`, `golden`. `python -m frc_shop_card regen-awg` rewrites
the `awg_table` rows from the formula if you ever change them by hand.

## Flashcards and warm-ups

- Three Leitner boxes. **Again** sends a card to box 1 (it comes back first), **Hard** to box 2,
  **Got it** to box 3. Cards you mark Again twice or more appear under "What I keep missing".
- Filter by week or box, Shuffle, keyboard: space to flip, 1/2/3 to rate, arrow keys to move.
- Progress is stored only in that browser (`localStorage`, keys starting `frc_shop_card.`), as
  box numbers only. No names, no accounts, nothing leaves the device. On a shared shop computer
  use **Reset progress**; to carry your boxes to another device use **Export / import**.
- The weekly warm-up picks 3 questions from the chosen week and 2 from earlier weeks (week 0 takes
  all 5 from week 0). The same week and seed always give the same questions, on the page and from
  `python -m frc_shop_card warmup --week N --seed S`, so the paper quiz and the answer key match.
- The exit ticket is the three-line template: one safety rule, the SL current limit and gauge, one
  thing that is still fuzzy.
- No card is about a team-internal procedure; the deck is safe to share.

## Limits

- It is not a rulebook. The Game Manual is re-issued every January and rule numbers move; the
  roboRIO is being replaced by SystemCore (scheduled for the 2027 season), whose brown-out numbers
  are from an alpha specification. Verify against the current manual.
- Vendor numbers are as published on the dates the card was built and will drift.
- The team-standards table is an example. Ferrule colours vary by supplier and two incompatible
  colour codes exist; the card says which code each colour belongs to.
- No torque values, no motor stall currents, no SL crimp dimensions, no breaker trip curves, no
  arc-flash numbers (there is no arc-flash hazard at 12 V; the hazard is bolted-fault current).
- The AWG table is for solid copper at 20 C; stranded, warm wire reads a few percent higher.
- Flashcard progress never leaves the browser it was made in, which also means it is lost if the
  browser's site data is cleared; export it first if that matters.
- The page needs JavaScript; an iPhone's Files preview does not run it (see above).

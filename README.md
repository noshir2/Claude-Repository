# Toolbox

Small, plain-English tools built for one person's actual week: options income on Webull, mentoring
an FRC robotics electrical subteam, fantasy football, kids' music practice, and keeping a PE license
current. Each tool lives in its own folder with its own README, made-up sample data, and tests.

Everything runs on your own computer. Nothing logs in anywhere, nothing is uploaded, and your real
files stay in the `data/` folder, which git ignores.

| Tool | The question it answers | Try it |
|---|---|---|
| [Wheel Tracker](wheel_tracker/README.md) | Are my cash-secured puts and covered calls actually making money? | `python -m wheel_tracker samples/sample_webull_orders.csv` |
| [Wheel Planner](wheel_planner/README.md) | Is this put or call worth the cash it ties up, is this roll worth it, and what do my own rules say? | `python -m wheel_planner compare --candidate AAA,P,45,2026-11-20,1.00,50,60` or open `wheel_planner/wheel_calculator.html` |
| [FRC Electrical Shop Card](frc_shop_card/README.md) | What are the wiring rules, reference numbers, and calculators an FRC electrical mentor needs on a Wednesday night, plus flashcards and printable quizzes for students? | open `frc_shop_card/frc_shop_card.html`; `python -m frc_shop_card vdrop --awg 6 --amps 120 --feet 10` |
| [Fantasy Lineup and Trade Helper](fantasy_helper/README.md) | Who do I start, is this trade good for my starters, and which pickup helps most? | `python -m fantasy_helper lineup --league fantasy_helper/samples/league1 --proj fantasy_helper/samples/week8` |
| [Taal Trainer](taal_trainer/README.md) | A metronome that counts like a tabla player, for practising Hindustani taals and reciting thekas from memory. | open `taal_trainer/taal_trainer.html` |
| [PDH Log](pdh_log/README.md) | Do I have the continuing-education hours my Illinois PE renewal needs, and what is still missing? | `python -m pdh_log status --log samples/pdh_log_sample.csv` |
| [Photo Sheet](photo_sheet/README.md) | Crop a photo to a passport or form size and save it under a file-size cap, without uploading it anywhere. | open `photo_sheet/photo_sheet.html` |

## Running things

- Open a terminal in this folder (the one that holds this README) and run the commands from here.
- Python 3.11 or newer, standard library only; nothing to install. On Windows type `python` or `py`
  where a README says `python3`.
- The HTML tools are single files: double-click them. They work offline and remember settings only in
  that browser. See each README's "Opening it on a phone" note (Android opens them directly; an
  iPhone needs Safari rather than the Files preview).
- To run every check: `pip install pytest` once, then `python -m pytest -q`.

## Where your real data goes

Put exports, rosters, logs and candidate lists in `data/` (create it next to this README). It is
listed in `.gitignore`, so nothing in it can be committed by accident. The samples in `samples/` and
in each tool's `samples/` folder are invented.

## Accuracy

Every tool's README has a "What the numbers mean" section and a "Where the rules/figures come from"
section with sources. Rule tables (FRC game manual, Illinois PE rules, league scoring) change; each
tool says so and tells you what to verify. None of this is investment, legal or safety advice.

# Taal Trainer

A metronome that counts the way a tabla player counts: it shows the theka bols matra by matra, marks
sam, taali and khali with different sounds and a big moving highlight, and lets you hide the bols so
you can recite them from memory (padhant). For keeping taal while singing and for practising the hand
claps and waves before a practical exam. One file, works offline, nothing leaves the device: it remembers your
last taal, tempo, practice minutes per date and the game's best score in the browser, and that is all.

Words used in this guide: a **taal** is a rhythm cycle; a **matra** is one beat of it; the
**theka** is the spoken pattern of the cycle and each spoken syllable is a **bol**; the **sam** is
the first beat (a clap), a **taali** is another clapped beat, and the **khali** is the waved,
"empty" beat; a **vibhag** is a section of the cycle; **laya** is the tempo.

## The easy way

Open `taal_trainer/taal_trainer.html` from the Start here page (`index.html`) or double-click the
file. It opens in your browser (Chrome, Edge, Safari, Firefox). No install, no Wi-Fi, no account.

1. Press the big green **Start** button. It sits below the list of taals and the beat grid, so on
   a phone scroll down past the grid to find it. There is no "Try it with example data" button on
   this page because it needs nothing from you: Teentaal (16 beats) and a medium tempo are already
   chosen, so the beat starts, the highlight moves across the grid and you hear the three sounds
   at once. (Sound starts on your first tap; that is how browsers work.)
2. Pick your own taal from the list and set the tempo (slider, `-`/`+`, or hit **Tap tempo** in
   time). On a phone, if you hear nothing, check the silent switch and the volume. The beat keeps
   moving on screen even with no sound, so it still works as a silent drill.
3. Tap **Stop** (the same button; or press Space on a keyboard) to stop. To practise reciting,
   tick **Hide bols** (see "Practising for the exam" below).

### Opening it on a phone

- **Android (Chrome):** use the online link you were given, or copy the file to the phone (email
  it to yourself, or use a USB cable or Google Drive) and open it; Chrome runs it from the Files app.
- **iPhone:** the easiest route is the online link you were given, opened in Safari. The Files app only previews a page: the buttons, sound and moving parts do nothing there. If you have the file on the phone, try Share > **Open in Safari**; if that is not offered, use the online link. Add it to the home screen afterwards and it behaves like an app.
- iPhones do not play web audio while the silent switch is on. Flip it, or just use the visual beat.

## What you see and hear

- **The big readout**: the sign, the bol, "matra 5 of 16", and the cycle number. Big enough to read
  from across the room. During a count-in it says "count-in".
- **The grid**: the matras grouped by vibhag with a bar between vibhags, in the usual notation:
  - **X** = sam, the first matra of the cycle (clap). Red.
  - **2, 3, 4** = taali, the other claps, numbered in the order they occur. Green.
  - **0** = khali, the wave (empty beat). Amber.
  - The number under the sign is the matra; the word under it is the bol.
- **Rupak is the odd one**: its matra 1 is the sam *and* a wave, so it shows **0** and plays the khali
  sound. Some books print X there; your teacher decides how you show it with your hands.
- **Three sounds plus a tick**: sam is a low, accented, longer thump; taali is a short clap-like burst;
  khali is a softer, higher tone; every other matra is a plain tick. They are simple synthesized tones,
  not a tabla recording.
- **Tempo** is in **matras per minute** (30 to 300). The label next to it is the laya:
  vilambit (slow) about 30-60, madhya (medium) about 60-120, drut (fast) about 120-200 and above (the
  slider goes to 300; very fast is sometimes called ati-drut). These ranges are approximate and overlap
  in real music; your teacher's tempo overrides them.
- **Cycle counter**: which cycle (avartan) you are in since Start, not counting the count-in; it says
  "cycle 1" during the first cycle. With "Loop N cycles" set, it reads "cycle 3 of 8" and the trainer
  stops by itself exactly where the next sam would fall.
- **Today: N min**: whole minutes the trainer has been running today on this device, with a strip for
  the last 7 days. It counts only while the beat is running and the page is on screen; time with the
  phone locked or another app in front is not counted. **Reset minutes** wipes the strip.
- **Find the sam** (game): after the count-in the sound goes off; keep the cycle in your head and tap
  the big button on the sam. The result is how many milliseconds (thousandths of a second) early or
  late you were, measured against the nearest sam; "On the sam!" means within 60 ms. The best (lowest)
  number is kept on the device. Count-in is locked on while the game is ticked: that one audible
  cycle is your reference.

## Practising for the exam

- Start with **Count-in** on: one full cycle plays first so you know the tempo before you begin.
- **Hide bols** hides the words but keeps the signs, so you recite the theka from memory while the
  highlight moves. **Hide after N cycles** gives you N cycles with the words, then hides them (if "Hide bols" is also
  ticked, "Hide after N" wins: you still get the N cycles with the words). Leave it at 0 to hide straight away.
  **Hide markers too** also hides X / 2 / 0 (and the bols with them): the hardest level, only the
  moving highlight is left. With "Hide after N cycles" it waits for those N cycles as well.
- **Mute random matras** silences about one matra in three at random, so you have to keep the cycle
  going inside your head and land on the sam yourself.
- Use **Loop N cycles** so you can recite a fixed number of cycles and check you end on the sam.
- Keyboard (laptop): Space start/stop, Up/Down tempo by 1, Left/Right by 5, T tap tempo.

## Changing or adding a taal

The whole taal table is one clearly marked block at the top of `taal_trainer.html`
(`<script id="taal-data" type="application/json">`). Each taal looks like this:

```
{"name": "Teentaal", "status": "standard", "matras": 16, "vibhags": [4, 4, 4, 4],
 "sam": 1, "taali": [1, 5, 13], "khali": [9],
 "bols": ["Dha", "Dhin", "Dhin", "Dha", "Dha", "Dhin", "Dhin", "Dha", "Dha", "Tin", "Tin", "Ta", "Ta", "Dhin", "Dhin", "Dha"],
 "note": "...", "source": "..."}
```

- `vibhags` are the sizes of the sections and must add up to `matras`; `bols` needs exactly one word
  per matra (`-` for a rest). `taali` and `khali` are matra numbers and must each be the first matra
  of a vibhag. A matra in `khali` shows 0 and plays the khali sound even if it is the sam (Rupak).
- `status` is `standard` or `standard-but-confirm` (shown as a "confirm with teacher" badge).
- `vibhags`, `taali`, `khali` and `bols` are lists in square brackets; sizes and positions are plain
  whole numbers (write `[4, 4, 4, 4]`, not `"4,4,4,4"`).
- Edit it in any text editor (Notepad is fine; "UTF-8" or "UTF-8 with BOM" both work), save, and
  check the counts add up with the checker command in the Advanced section. If a comma or quote goes
  missing, the page itself opens with "The taal table at the top of this file has a mistake" and a
  greyed-out Start button until you fix it.

The same table is also kept as `taal_trainer/taals.json`. If you prefer to edit that file, copy it
into the HTML afterwards with the embed command in the Advanced section; it refuses to touch the
page while the JSON (the bracketed text format of that file) has a problem.

Thekas vary by teacher and gharana; confirm with your teacher before relying on any row.

## Limits

- Sounds are synthesized tones, not a tabla. Use a lehra or tabla recording for raga practice; this
  is for cycle discipline, padhant and clapping.
- The thekas are common textbook forms. Ektaal, Chautaal, Deepchandi, Tilwada and Jhoomra are
  marked "confirm with teacher" because bols and even the vibhag division differ between schools
  (Chautaal, for example, is also taught as 4+4+2+2 with claps only; see its note in the table).
- Every matra gets one beat. Thekas with half-matra bols (Jhoomra's "-Dha", Deepchandi's rests) are
  shown as written but the click lands on the matra, not on the half.
- Everything the page remembers stays in this browser: the last taal, the tempo, minutes per date and
  the game's best score. Nothing syncs between devices; clearing the browser's site data clears it.
  No names, no log of what was practised.
- No syllabus or exam checklist is included on purpose: lists change and a wrong one before an
  exam is worse than none. Use the current sheet from the exam body or your teacher.
- iPhone preview in the Files app does not run the page; see "Opening it on a phone".
- Keep the page in the foreground. If the phone locks or you switch apps, the browser pauses the
  page; when you come back the trainer carries on from the next matra (the missed beats are not
  replayed), so the cycle count may be behind real time by however long you were away.
- The timing is as good as the browser's audio clock (normally within a few milliseconds and it does
  not drift over long sessions). If the browser blocks audio, the page falls back to a plain timer for
  the visual beat and says so.
- A Sa drone was considered and left out: it needs tuning by ear to be pleasant, which could not be
  checked here. Play a tanpura app alongside if you need one.

## Where the rules/figures come from

- Taal structures (matras, vibhags, taali/khali positions) and the thekas: Wikipedia's pages for
  each taal (Teental, Ektal, Jhaptal, Rupak tala, Dadra, Keherwa, Tilwada, Jhoomra, Vibhag),
  chandrakantha.com's "Index of Tals" pages, the University of Washington (Gangolli) theka list,
  ancient-future.com's theka page and Sahapedia's note on tala in semi-classical music. Each row in the
  table carries its own `source` line and a `note` listing the common variants.
- Rupak's sam being a wave (written 0): chandrakantha.com, the UW theka list and Wikipedia all agree;
  Wikipedia notes some books print X instead.
- Chautaal's two schools (2+2+2+2+2+2 with waves at 3 and 7, or 4+4+2+2 with claps only at
  1, 5, 9, 11): chandrakantha.com and the UW theka list; the claps are the same in both.
- Notation signs (X sam, 2/3/4 taali, 0 khali, | vibhag, - rest): the Bhatkhande convention as
  described on chandrakantha.com and Wikipedia (Vibhag).
- Laya ranges: chandrakantha.com gives roughly 40 / 80 / 160 beats per minute for vilambit / madhya /
  drut and calls it "the roughest of an approximation"; raag-hindustani.com gives vocal vilambit
  around 30, madhya 60-120, drut 150+; Clayton (Time in Indian Music, 2000) measured overlapping ranges.
  The labels here (30-60 / 60-120 / 120-200) are a teaching simplification of those, not a rule.
- "Within 60 ms" for the sam game and the one-in-three random mute are this tool's own settings, not
  musical rules.

Check anything that matters for an exam against your teacher and the exam body's current syllabus.

## Advanced: the command-line version

Nothing to run for normal use. The only command is the checker for people who edit the taal table.
It needs Python 3.11 or newer (nothing to install). Open a terminal (the text window where you type commands: on Windows search the Start menu for Command Prompt or PowerShell; on a Mac open Terminal) in the project folder (the folder that contains
`taal_trainer`) and run it from there; on Windows type `python` or `py` where these lines say
`python3`.

```
python3 -m taal_trainer.check
```

It prints `taal data OK: 10 taals` or `Problem: ...` saying exactly what is wrong.

To copy `taal_trainer/taals.json` into the page: `python3 -m taal_trainer.check --embed`.
The tests (`python3 -m pytest tests/test_taal_trainer.py -q`) check that the two stay identical.

# Start here

Version: 2026-10-22 (year-month-day). The same line sits at the top of the Start here page
(`index.html`) and in `OPEN-ME-FIRST.txt`. To see whether a newer copy exists, open the project page
on GitHub (the address is in "Getting your own copy" below), scroll below the list of files to where
GitHub shows this README, and compare the date there with this one. A later date there means there
is a newer copy; the same date means you already have the newest.

This folder holds a few small tools built for one person's week: options income on Webull,
mentoring a robotics electrical team, fantasy football, kids' music practice, keeping an engineering
license current, and making a passport photo: six pages covering seven tools (the Webull results
checker lives inside the Options page). Each tool is a page you open in your web browser
(Chrome, Edge, Safari or Firefox), on a PC or on a phone. You type or choose a file, press a button,
and read the answer in plain words. There is nothing to install and no account to make.

## The easiest way

Double-click the file `index.html` in this folder, or open the online link if you were given one. That is the
"Start here" page: it lists every tool with one sentence each and a button that opens it. Every tool
page that works from your own numbers or files has a big button near the top that fills the page
with made-up data, so you can see what a result looks like before you use your own. On the Options,
Fantasy football and PE continuing education pages it reads **Try it with example data**; on the
Robotics electrical card it reads **Show me an example**; on the Passport photo page it reads
**Try it with a drawn face**. The Taal trainer needs nothing from you: tap the big green **Start**
button (it sits below the list of taals and the beat grid, so on a phone scroll down to it). The
online copy cannot save files or print; every result is still shown on the page, so
copy it, or press and hold (phone) or right-click (PC) a picture and choose Save. To save and
print, use your own copy of the files (next section).

If you have the folder on your computer, the file `OPEN-ME-FIRST.txt` says the same thing in ten
lines.

On a phone, an online link (if you were given one) is the easiest route. The same pages also work
in Chrome on Android if you copy the files over; on an iPhone the Files app only previews a page
(the buttons do nothing there), so on an iPhone use an online link.

## Getting your own copy

GitHub is a website that stores the files of this project. Downloading them needs no sign-in and
no install. The project's address is public: https://github.com/noshir2/Claude-Repository

1. Open the project page in your browser: type that address into the address bar at the top of the
   browser, or tap the link if someone sent it to you. The page is public, so you arrive without an
   account.
2. Near the top left of the project page, just under the project name, is a button that shows a
   name beginning with claude/. If it already says
   **claude/lucid-dijkstra-gic3gd**, go to the next step. If it shows a different name, press it,
   type **lucid** in the box that appears, and choose **claude/lucid-dijkstra-gic3gd** from the
   short list. GitHub calls these names branches; a branch is one saved version of the files, and
   that one is the version these instructions describe. If this step is a struggle, skip it: the
   download in the next step works from whichever branch is shown, and the Version line at the top
   of the README in the copy you get tells you which one you have.
3. Click the green **Code** button (top right of the file list).
4. Click **Download ZIP**. A file ending in `.zip` lands in your Downloads folder. A ZIP is one file
   that holds a whole folder, squeezed smaller.
5. On Windows, right-click the ZIP file and choose **Extract All...**, then **Extract**. You get an
   ordinary folder with the same name. (On a Mac, double-click the ZIP; the folder appears next to it.)
6. Open that folder. Inside it is one more folder, whose name starts with `Claude-Repository`.
   Open that one too; this is where the files are.
7. Double-click `index.html` there. If your computer asks which program to use, choose your web
   browser.

To get an updated copy later, do the same steps again and use the new folder. Updates go on the
same branch, **claude/lucid-dijkstra-gic3gd**, so the steps above do not change. If that name is
ever missing from the list in step 2, pick each name that starts with claude/ in turn and read the
Version line just under the heading Start here in the README shown below the file list; the latest
date is the newest copy.
Before you download, compare that date with the Version line at the top of this file: a later date
means there is something new, the same date means you already have it. Nothing you typed is stored
in the old folder (the pages remember a few settings inside the browser itself, not in the files),
so the old folder can go in the bin.

## The tools, one at a time

Six pages covering seven tools: the Webull results checker (the `wheel_tracker` folder, which has
no page of its own) lives inside the Options page.

**Options: Wheel Planner and Wheel Tracker.** One page, `wheel_planner/wheel.html`, for selling
cash-secured puts and covered calls on Webull. The *tracker* part reads the order-history file you
export from Webull and tells you how much money the finished trades actually made, by stock and by
month, and what you would need to sell shares for to break even. The *planner* part is for before you
click Sell: you type the numbers Webull shows for a put or call and it tells you the return on the
cash tied up, how far the stock can fall before you are in trouble, a rough chance of being assigned
the shares, whether a roll is worth it, and which of your own written rules the trade breaks. You
need: the Webull export (a spreadsheet file ending in .csv) for the tracker; for the planner, only
the numbers on your screen. How to get the export: in the Webull app or website open Orders, then
History, and look for an export or download button; the words move between versions. Details:
[wheel_tracker/README.md](wheel_tracker/README.md) and
[wheel_planner/README.md](wheel_planner/README.md).

**FRC Electrical Shop Card.** The page `frc_shop_card/frc_shop_card.html` is a one-page reference
for a robotics electrical mentor: safety reminders, the rule table that says which wire size goes
with which breaker, reference numbers for connectors and batteries, calculators (voltage drop,
brown-out, battery health, short circuit), flashcards for students, and a printable one-page cheat
sheet and weekly quiz. You need nothing but the page. Details:
[frc_shop_card/README.md](frc_shop_card/README.md).

**Fantasy Lineup and Trade Helper.** The page `fantasy_helper/fantasy.html` answers who to start
this week, whether a trade helps your starting lineup, and which free-agent pickup adds the most. You
need the six weekly projection files you download from FantasyPros (one per position), your roster
typed into a box, and your league's scoring (a sample is filled in; check it against your league
settings page). Details: [fantasy_helper/README.md](fantasy_helper/README.md).

**Taal Trainer.** The page `taal_trainer/taal_trainer.html` is a metronome for Hindustani
classical music that counts like a tabla player: it shows the beats of a taal cycle, sounds the
clap and wave beats differently, and can hide the words so you recite them from memory. You need
nothing but the page and, for sound, the first tap on the Start button, which sits below the beat
grid (scroll down to it on a phone). Details:
[taal_trainer/README.md](taal_trainer/README.md).

**PDH Log.** The page `pdh_log/pdh.html` keeps track of the continuing-education hours an Illinois
Professional Engineer needs to renew the license: which renewal period each course falls in, the
three required core hours, the carry-over and daily-cap rules, and which courses still have no
certificate on file. You need your list of courses (type them on the page or choose a spreadsheet
file ending in .csv). Details: [pdh_log/README.md](pdh_log/README.md).

**Photo Sheet.** The page `photo_sheet/photo_sheet.html` crops a photo to passport or form size,
saves it under the file-size limit an online form states, and makes a 4 x 6 inch print sheet with
six copies. You need a photo on your computer or phone. The photo never leaves your device.
Details: [photo_sheet/README.md](photo_sheet/README.md).

## Words you will see

The same short list is on the Start here page.

- **.csv file**: a spreadsheet saved as plain text; Excel opens it, and it is the kind of file
  Webull and FantasyPros give you when you download your data.
- **Export, download**: two words for the same thing: asking an app to give you a file of your own
  data so you can use it elsewhere.
- **Option**: a contract about buying or selling 100 shares at a set price before a set date;
  selling one is how the puts and covered calls here earn money.
- **Put**: a contract you sell that promises to buy 100 shares at the strike price if the buyer
  wants you to, in return for the premium.
- **Covered call**: a contract you sell on shares you already own that promises to hand them over
  at the strike price if the buyer wants them.
- **Premium**: the money you receive when you sell an option; it is yours to keep whatever happens
  next.
- **Strike and expiry**: the strike is the share price the contract is tied to, and the expiry is
  the date the contract ends.
- **Assigned**: what happens when the buyer uses the contract: a put makes you buy the shares, a
  covered call makes you sell them.
- **Roll**: buying back a contract you sold and selling a new one with a later date or a different
  strike, usually to avoid being assigned.
- **Projection**: someone's estimate of how many fantasy points a player will score this week;
  FantasyPros publishes them as files.
- **Roster**: the list of players on your fantasy team, starters and bench together.
- **PDH**: professional development hour: one hour of approved continuing education, the unit your
  PE renewal counts.
- **Browser tab**: one open page in Chrome or Safari. The tools open in the same tab as the Start
  here page; use the Back to the toolbox link at the top of a tool, or the browser's Back arrow, to
  return there.
- **Pop-up, blocked download**: a message from the browser saying it stopped a page from opening a
  window or saving a file; the online copy of these tools is not allowed to save files, so this is
  expected there.

Words about getting the files (GitHub, ZIP, branch) are explained where they come up in "Getting
your own copy" above.

## Nothing is uploaded

Everything happens inside your browser, on your own device. Nothing you type or choose leaves it,
no page logs in anywhere, and no file is sent to any website. Close the page and your data is
gone, except the few settings each page says it remembers in the browser. The made-up sample files
are the only data in the project.

## For the technically minded: the command-line versions

Every tool also runs as Python 3.11+ (standard library only) from a terminal (the text window where
you type commands) opened in this project folder: `python -m <folder> ...`, where `<folder>` is the
tool's folder name (`wheel_tracker`, `wheel_planner`, `frc_shop_card`, `fantasy_helper`, `pdh_log`,
`photo_sheet`; the Taal Trainer has only a data checker, `taal_trainer.check`). On Windows type
`python` or `py`; on a Mac, `python3`. Each folder's README ends with an "Advanced: the command-line
version" section listing its commands. Put real exports in a folder named data next to this file; it
is listed in the ignore file, so it never goes into the project on GitHub (what GitHub calls the
repo). To run every check: `pip install pytest` once, then `python -m pytest -q`.

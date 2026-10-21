# PDH Log

Answers one question: **do I have the continuing-education hours my Illinois PE renewal needs, and
what is still missing?** (PDH = professional development hour, the unit the license board counts.)

You keep one small list of courses (date, hours, title, provider, category, certificate file).
The tool works out which renewal period each row belongs to, adds up the hours, checks the three
required "core" hours, applies the carry-over and daily-cap rules, and lists rows that have no
certificate on file. Everything runs on your own device; nothing is uploaded.

## The easy way

Open `pdh_log/pdh.html` from the Start here page (`index.html`) or double-click the file.

1. Press the big **Try it with example data** button. The page loads a made-up course list and
   shows the verdict at once: hours so far, what is missing, days left, and the rows to fix.
2. Put in your own courses. Either type them on the page under **Add a course** (one row per
   course: date, hours, title, provider, category), or scroll down to **Bring a list in** (near the
   bottom, under Your courses and Back up or move your list) and choose your own spreadsheet file
   there (a .csv file saved from Excel whose first line is exactly the header listed under "The
   spreadsheet columns" below). How: in Excel, File > Save As, and pick "CSV UTF-8" as the type.
3. Read the verdict sentence, then the tables under it. Every number has a one-line meaning next
   to it.

### The spreadsheet columns

If you keep the list in Excel, the first line must be exactly:
`date,hours,title,provider,category,format,location,certificate_file,notes`

- `date` as `YYYY-MM-DD` (2026-10-15). `hours` as a number, half hours allowed (1, 1.5, 0.5); 0.25
  is fine for the IDFPR newsletter quiz.
- `category` is one of `elective`, `statutes_rules`, `ethics`, `harassment`. Plain words work too and
  capitals do not matter: "Ethics", "Statutes and rules", "sexual harassment". Anything containing
  "elective" is elective ("elective - code rules" is not a statutes/rules hour).
- `format` and `location` are free text (webinar, in-person, college course; online or a city).
- `certificate_file` is the name of the certificate file, written relative to the folder the list
  is in, or blank if you do not have it yet.
- `notes`: put the sponsor's address here (Illinois wants it in your records).
- Lines starting with `#` are ignored. An unreadable date, hours or category stops the tool and names
  the line.
- In Excel, Save As "CSV UTF-8" when it asks. A plain "CSV (Comma delimited)" save is read too (as
  Windows-1252), so an en dash or curly quote in a title will not stop the tool.

## What the numbers mean

- **Renewal period.** Illinois PE licenses expire November 30 of every odd-numbered year, and the
  hours for a renewal are the 24 months ending on that date. The tool picks the period that contains
  today (or the date you give it with the command-line option `--today`): on 2026-10-21 that is
  2025-12-01 to 2027-11-30. On 2027-12-01 it rolls over to 2027-12-01 to 2029-11-30. The verdict line
  always says "for the period ending ..." so you can see which boundary it used.
- **Days left** = days from today until the period's last day.
- **Hours counted this period** = the hours of every row dated inside the period, after the daily cap
  (below). Split into **core** (the three required hours) and **elective** (everything else).
- **Core hours.** Each renewal needs at least 1 PDH on Illinois statutes and rules, 1 PDH on
  professional conduct/ethics, and 1 PDH of sexual-harassment-prevention training. They count inside
  the 30, not on top. "met" means the period has at least that many hours in that category. They
  must be earned fresh every period; last period's do not count.
- **Carry-over from previous period.** Illinois lets you carry up to 15 hours into the next period,
  but only hours that meet all three conditions: earned June 1 to November 30 of the previous renewal
  year; elective (core hours never carry); and not needed to reach that period's own 30. The tool
  takes the smallest of: 15, the previous period's counted hours plus whatever was carried into it
  minus 30, and the elective hours in that window. Hours carried into a period are treated as used
  first, so carry-over chains: a period that received 10 and then earned exactly 30 of its own has 10
  spare. IDFPR (the Illinois licensing department) decides what it accepts. Carried hours must be
  written on IDFPR form f2476 (PE-CO) and kept with your records. The report also shows what the
  current period could pass on to the next one.
- **Total toward the 30** = hours counted this period + carry-over. **Short by** = 30 minus that, or
  0 if met.
- **Daily cap.** At most 12 PDH count in one calendar day. A day with more is flagged; the extra hours
  are taken off that day's elective rows (last row in the file first) so core hours are kept, and the
  report names the rows that lost hours. The "Counts" column in the row table shows what each row
  contributes after the cap.
- **Record check.** Illinois does not accept a bare log. For each course keep a certificate of
  attendance plus the sponsor's name and address, the date and place, the hours and a short statement
  of the subject, for 6 years. The tool lists rows in the period with no `certificate_file`, and (in
  the command-line version, which can see your folder) rows whose file is not where the path says.
- **Please check.** Rows dated after today, and hours that are not a multiple of 0.25 (one PDH is at
  least 50 minutes and the smallest Illinois credit is the 0.25 PDH newsletter quiz, so finer fractions
  usually mean a typo).

## Limits

- Illinois only. The command-line option `--state` accepts nothing else; another state's rules would
  have to be added to `pdh_log/rules.py` with their citations. Other states differ (period, hours,
  ethics hours).
- It does not know your licensure date. The first renewal after you were first licensed in Illinois
  is exempt from reporting hours; if that is you, the tool still shows you as short.
- It does not convert units. Type the PDH value the certificate states. For a college course use the
  Illinois conversion (15 PDH per semester hour, 10 per quarter hour); for CEUs (continuing education
  units), 10 PDH per CEU. A single row with more than 12 hours on one date trips the daily cap, so
  spread a long course across its real dates or note the reason.
- It does not check that a certificate file is a real certificate, only that the file exists.
- It does not know whether a course meets the content standards in 1380.325(c), whether a
  self-study course had a graded exam, or the 8-hour cap on society/board service credit; that is on
  you when you type the hours.
- Carry-over is an estimate from your log. IDFPR decides what it accepts, and you must file the form.

## Where the rules/figures come from

All rule values live in one table in `pdh_log/rules.py`, each with its citation, and the `rules`
command in the Advanced section prints them. Sources (verified against the official ILGA text on
2026-10-21):

- 68 Ill. Adm. Code 1380.310(a): expiration November 30 of odd-numbered years, 2-year term.
- 68 Ill. Adm. Code 1380.325, as amended 49 Ill. Reg. 10161, effective July 23, 2025:
  (a)(1) 30 PDH per renewal; (a)(2)(A) statutes/rules hour; (a)(2)(B) ethics hour; (a)(3) sexual
  harassment prevention hour (with 68 IAC 1130.400); (a)(4) 24-month pre-renewal period; (a)(5) one
  PDH is at least 50 minutes, max 12 PDH in 24 hours, 1 CEU = 10 PDH; (a)(8) carry-over max 15, last
  six months, no core hours, documented on the Department form; (b) activity credits (15/10 PDH per
  semester/quarter hour, teaching 3 PDH per hour, papers and patents 10 PDH, society/board service 2
  PDH each max 8); (d)(1)-(2) records kept 6 years and what they must contain; (j)(1) first-renewal
  exemption. Official text: https://ilga.gov/commission/jcar/admincode/068/068013800003250R.html
- IDFPR "Professional Engineer License Renewal PDH Requirement" sheet (April 2026): 3 core + 27
  elective, carry-over window June 1 to November 30 of the renewal year.
- IDFPR carry-over form f2476 (PE-CO):
  https://idfpr.illinois.gov/content/dam/soi/en/web/idfpr/renewals/apply/forms/f2476.pdf
- IDFPR Design Professions newsletter 34 (Summer 2026): newsletter quiz earns 0.25 PDH toward the
  statutes/rules hour.

This is a bookkeeping aid, not legal advice. The rules were reworded in 2025 and can change again;
verify with IDFPR and the current 68 IAC 1380.325 before relying on any number here. Copies of Part
1380 on third-party law sites were stale (2023 text) when this was written, so use the ILGA link.

## Advanced: the command-line version

The same rules run as a Python program (Python 3.11 or newer, standard library only, nothing to
install). Open a terminal (the text window where you type commands: on Windows search the Start menu for Command Prompt or PowerShell; on a Mac open Terminal) in the project folder (the one that contains `pdh_log/`); every path below is relative to it.

1. Keep your log at `data/pdh_log.csv` (the `data/` folder is ignored by git, the program that
   copies files to GitHub, so your real courses never go online). Start by copying `samples/pdh_log_sample.csv` there and deleting the sample
   rows, or let the `add` command create it for you.
2. Add a row each time you finish a course, either by editing the CSV in Excel or with one command:

   `python3 -m pdh_log add --date 2026-10-15 --hours 1 --title "Engineering ethics webinar" --provider "Example Engineering Society" --category ethics --format webinar --location online --certificate certs/2026-10-15-ethics.pdf --notes "sponsor address: 100 Example St"`

3. Save the certificate of attendance next to the log (for example in `data/certs/`) and put its
   file name in the `certificate_file` column, relative to the log's folder.
4. Check where you stand: `python3 -m pdh_log status`
5. Open `pdh_report.html` in your browser for the picture-friendly version.

Try it first on the made-up sample: `python3 -m pdh_log status --log samples/pdh_log_sample.csv`

To see every rule the tool applies, with its citation: `python3 -m pdh_log rules`

Options for `status`: `--log FILE` (default `data/pdh_log.csv`), `--today YYYY-MM-DD` (pretend it is
another day), `--html FILE` (where to write the report, `''` to skip), `--period 2025` (report a past
or future period, the one ending Nov 30 of that odd year; the tool applies today's rules to every
period, and periods before the one ending Nov 30, 2023 had fewer core hours, so older periods show
core hours as NOT MET that were not required then). `--state IL` goes before the command; IL is
the only state shipped.

**Windows note:** if `python3` is not recognised, type `python` or `py` instead, e.g.
`py -m pdh_log status`. To run the checks, first `pip install pytest`, then
`python3 -m pytest tests/test_pdh_log.py` (two separate commands; PowerShell does not accept `&&`).

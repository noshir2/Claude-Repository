"""Plain-English text report and a self-contained HTML report (same content, side-by-side lineups)."""
from html import escape

from .helper import Report, pts, spts
from .lineup import Lineup

DISCLAIMER = "Projections are FantasyPros' estimates as of your download; this tool only ranks them under your scoring."


def _slot_rows(best: Lineup, floor: Lineup) -> list:
    """Rows for the side-by-side table: (slot, best player, floor-lineup player or None if same)."""
    rows = []
    for e_best, e_floor in zip(best.entries, floor.entries):
        same = (e_best.player is None and e_floor.player is None) or (
            e_best.player and e_floor.player and e_best.player.name == e_floor.player.name)
        rows.append((e_best.slot, e_best.player, None if same else e_floor.player, e_floor.player))
    return rows


def floor_differences(best: Lineup, floor: Lineup) -> list:
    out = []
    for slot, bp, fp, _ in _slot_rows(best, floor):
        if fp is not None:
            out.append(f"{slot}: {fp.name} (floor {pts(fp.floor)}) instead of "
                       f"{bp.name if bp else '(empty)'} (floor {pts(bp.floor) if bp else '0.0'})")
    return out


def _name(p) -> str:
    return p.name if p else "(empty slot)"


def text_report(r: Report) -> str:
    title = {"lineup": "BEST LINEUP", "trade": "TRADE CHECK", "waiver": "WAIVER CHECK"}[r.command]
    out = [f"{title} - league folder '{r.league_folder}', projections '{r.proj_folder}'", "=" * 78,
           f"The projection files {r.kind_note}.", ""]
    out += ["NAMES", "-" * 78]
    if r.match_lines or r.unmatched:
        out += r.match_lines
        for u in r.unmatched:
            out.append(f"COULD NOT FIND: {u}")
    else:
        out.append("Every roster name matched a projection exactly.")
    if r.problems:
        out += ["", "NAMES I COULD NOT USE", "-" * 78] + list(r.problems)

    best, floor = r.lineup, r.floor_lineup
    out += ["", "BEST LINEUP (highest projected)                      FLOOR LINEUP (highest floor)", "-" * 78,
            f"{'Slot':<5}{'Player':<24}{'Proj':>6}{'Floor':>7}{'Ceil':>7}  {'Player':<24}{'Floor':>6}{'Proj':>6}"]
    for slot, bp, fp, fp_any in _slot_rows(best, floor):
        left = (f"{slot:<5}{_name(bp)[:23]:<24}{pts(bp.proj) if bp else '':>6}{pts(bp.floor) if bp else '':>7}"
                f"{pts(bp.ceil) if bp else '':>7}")
        right = "same" if fp is None else f"{_name(fp)[:23]:<24}{pts(fp.floor):>6}{pts(fp.proj):>6}"
        out.append(f"{left}  {right}")
    out.append(f"{'TOTAL':<29}{pts(best.proj_total):>6}{pts(best.floor_total):>7}{pts(best.ceil_total):>7}  "
               f"{'':<24}{pts(floor.floor_total):>6}{pts(floor.proj_total):>6}")
    out.append(f"Best lineup: {pts(best.proj_total)} projected, floor {pts(best.floor_total)}, "
               f"ceiling {pts(best.ceil_total)}. Floor lineup: floor {pts(floor.floor_total)}, "
               f"projected {pts(floor.proj_total)}.")
    diffs = floor_differences(best, floor)
    if diffs:
        out.append("Floor lineup differs at: " + "; ".join(diffs))
    else:
        out.append("The floor lineup is the same as the best lineup.")
    if r.opponent_line:
        out.append(r.opponent_line)

    out += ["", f"CLOSE CALLS (within {r.close_within:g} points)", "-" * 78]
    if r.close:
        for c in r.close:
            out.append(f"{c.slot}: {c.starter.name} {pts(c.starter.proj)} vs bench {c.other.name} "
                       f"{pts(c.other.proj)} ({pts(c.gap)} apart; floors {pts(c.starter.floor)} vs {pts(c.other.floor)})")
    else:
        out.append("None.")

    out += ["", "BENCH", "-" * 78, f"{'Pos':<5}{'Player':<24}{'Proj':>6}{'Floor':>7}{'Ceil':>7}{'FantasyPros FPTS':>18}"]
    for p in r.bench:
        fp = pts(p.fpts_csv) if p.fpts_csv is not None else "n/a"
        out.append(f"{p.pos.replace('DST', 'DEF'):<5}{p.name[:23]:<24}{pts(p.proj):>6}{pts(p.floor):>7}{pts(p.ceil):>7}{fp:>18}")
    if not r.bench:
        out.append("None.")

    out += ["", "NOT PROJECTED THIS WEEK (bye or out?)", "-" * 78]
    out += [u for u in r.unmatched] or ["None: every roster player has a projection."]

    if r.trade:
        t = r.trade
        out += ["", "TRADE", "-" * 78,
                "Give: " + ", ".join(f"{p.name} ({p.pos.replace('DST', 'DEF')}, {pts(p.proj)})" for p in t.give),
                "Get:  " + ", ".join(f"{p.name} ({p.pos.replace('DST', 'DEF')}, {pts(p.proj)})" for p in t.get),
                f"This week: best lineup {pts(t.week.before.proj_total)} -> {pts(t.week.after.proj_total)} "
                f"({spts(t.week.change)}); floor {pts(t.week.before.floor_total)} -> {pts(t.week.after.floor_total)}"]
        out += t.notes
        if t.ros:
            out.append(f"Rest of season: best lineup {pts(t.ros.before.proj_total)} -> "
                       f"{pts(t.ros.after.proj_total)} ({spts(t.ros.change)})")
        outs = ", ".join(f"{p.name} ({t.week.before.slot_of(p.name)})" for p in t.week.starters_out()) or "none"
        ins = ", ".join(f"{p.name} ({t.week.after.slot_of(p.name)})" for p in t.week.starters_in()) or "none"
        out.append(f"Starters out: {outs}. Starters in: {ins}.")
        changes = t.week.position_changes()
        if changes:
            out.append("Starter points by position: " + ", ".join(f"{k} {spts(v)}" for k, v in changes.items()))
        out.append(f"Verdict: {t.verdict}")

    if r.waiver:
        w = r.waiver
        out += ["", "WAIVER", "-" * 78] + list(w.notes)
        if w.single:
            s = w.single
            drop = (f"drop {s.drop.name} ({pts(s.drop.proj)})" + (" - weakest bench player" if s.drop_was_default else "")
                    ) if s.drop else "nobody dropped"
            out.append(f"Add {s.add.name} ({s.add.pos.replace('DST', 'DEF')}, {pts(s.add.proj)}), {drop}: "
                       f"best lineup {pts(s.delta.before.proj_total)} -> {pts(s.delta.after.proj_total)} ({spts(s.gain)})")
            ins = s.delta.starters_in()
            outs = s.delta.starters_out()
            if ins:
                out.append("Starter change: " + ", ".join(f"{p.name} starts at {s.delta.after.slot_of(p.name)}" for p in ins)
                           + (" replacing " + ", ".join(p.name for p in outs) if outs else "") + ".")
            else:
                out.append(f"{s.add.name} would sit on the bench this week (no lineup gain).")
        if w.ranked:
            out += ["Candidates ranked by lineup gain (not by raw points):",
                    f"{'#':<3}{'Player':<24}{'Pos':<5}{'Proj':>6}{'Gain':>7}  Would replace"]
            for i, res in enumerate(w.ranked, start=1):
                outs = ", ".join(p.name for p in res.delta.starters_out()) or "(bench only)"
                out.append(f"{i:<3}{res.add.name[:23]:<24}{res.add.pos.replace('DST', 'DEF'):<5}"
                           f"{pts(res.add.proj):>6}{spts(res.gain):>7}  {outs}")
            if w.ranked and w.ranked[0].drop:
                d = w.ranked[0].drop
                out.append(f"(each candidate replaces {d.name}" + (", your weakest bench player)" if w.ranked[0].drop_was_default else ")"))

    notes = list(r.warnings) + list(r.notes) + list(r.extra_lines)
    if notes:
        out += ["", "PLEASE CHECK", "-" * 78] + [f"* {n}" for n in notes]
    out += ["", DISCLAIMER]
    return "\n".join(out)


def html_report(r: Report) -> str:
    def table(headers, rows, cls=""):
        head = "".join(f"<th>{escape(h)}</th>" for h in headers)
        body = "".join("<tr>" + "".join(f"<td class='{c}'>{escape(str(v))}</td>" for v, c in row) + "</tr>"
                       for row in rows)
        return f"<table class='{cls}'><tr>{head}</tr>{body}</table>"

    def n(x):
        return (pts(x), "num")

    def lineup_table(lu: Lineup, key: str):
        rows = [[(e.slot, ""), (_name(e.player), ""), n(e.player.proj) if e.player else ("", "num"),
                 n(e.player.floor) if e.player else ("", "num"), n(e.player.ceil) if e.player else ("", "num")]
                for e in lu.entries]
        rows.append([("TOTAL", "tot"), ("", "tot"), (pts(lu.proj_total), "num tot"), (pts(lu.floor_total), "num tot"),
                     (pts(lu.ceil_total), "num tot")])
        return table(["Slot", "Player", "Proj", "Floor", "Ceil"], rows)

    best, floor = r.lineup, r.floor_lineup
    names = "".join(f"<li>{escape(m)}</li>" for m in r.match_lines)
    names += "".join(f"<li class='neg'><b>COULD NOT FIND:</b> {escape(u)}</li>" for u in r.unmatched)
    names = f"<ul>{names}</ul>" if names else "<p>Every roster name matched a projection exactly.</p>"
    if r.problems:
        names += "<h3>Names I could not use</h3><ul>" + "".join(f"<li class='neg'>{escape(x)}</li>" for x in r.problems) + "</ul>"
    diffs = floor_differences(best, floor)
    diff_html = ("<p>Floor lineup differs at: " + escape("; ".join(diffs)) + "</p>") if diffs \
        else "<p>The floor lineup is the same as the best lineup.</p>"
    close_html = "".join(f"<li>{escape(c.slot)}: {escape(c.starter.name)} {pts(c.starter.proj)} vs bench "
                         f"{escape(c.other.name)} {pts(c.other.proj)} ({pts(c.gap)} apart; floors "
                         f"{pts(c.starter.floor)} vs {pts(c.other.floor)})</li>" for c in r.close) or "<li>None.</li>"
    bench_rows = [[(p.pos.replace("DST", "DEF"), ""), (p.name, ""), n(p.proj), n(p.floor), n(p.ceil),
                   (pts(p.fpts_csv) if p.fpts_csv is not None else "n/a", "num")] for p in r.bench]
    notproj = "".join(f"<li>{escape(u)}</li>" for u in r.unmatched) or "<li>None: every roster player has a projection.</li>"
    card_rows = [[(e.slot, ""), (_name(e.player), ""), n(e.player.proj) if e.player else ("", "num")] for e in best.entries]
    card_rows.append([("TOTAL", "tot"), ("", "tot"), (pts(best.proj_total), "num tot")])

    extra = ""
    if r.opponent_line:
        extra += f"<p><b>{escape(r.opponent_line)}</b></p>"
    if r.trade:
        t = r.trade
        rows = [[("This week", ""), n(t.week.before.proj_total), n(t.week.after.proj_total), (spts(t.week.change), "num")]]
        if t.ros:
            rows.append([("Rest of season", ""), n(t.ros.before.proj_total), n(t.ros.after.proj_total), (spts(t.ros.change), "num")])
        outs = ", ".join(f"{p.name} ({t.week.before.slot_of(p.name)})" for p in t.week.starters_out()) or "none"
        ins = ", ".join(f"{p.name} ({t.week.after.slot_of(p.name)})" for p in t.week.starters_in()) or "none"
        extra += ("<h2>Trade</h2><p>Give: " + escape(", ".join(f"{p.name} ({pts(p.proj)})" for p in t.give))
                  + "<br>Get: " + escape(", ".join(f"{p.name} ({pts(p.proj)})" for p in t.get)) + "</p>"
                  + "".join(f"<p>{escape(x)}</p>" for x in t.notes)
                  + "<div class='wrap'>" + table(["", "Before", "After", "Change"], rows) + "</div>"
                  + f"<p>Starters out: {escape(outs)}. Starters in: {escape(ins)}.</p>"
                  + f"<p class='big-ish'><b>{escape(t.verdict)}</b></p>")
    if r.waiver:
        w = r.waiver
        extra += "<h2>Waiver</h2>" + "".join(f"<p>{escape(x)}</p>" for x in w.notes)
        if w.single:
            s = w.single
            drop = (f"drop {s.drop.name} ({pts(s.drop.proj)})" + (" - weakest bench player" if s.drop_was_default else "")
                    ) if s.drop else "nobody dropped"
            extra += (f"<p>Add {escape(s.add.name)} ({pts(s.add.proj)}), {escape(drop)}: best lineup "
                      f"{pts(s.delta.before.proj_total)} to {pts(s.delta.after.proj_total)} (<b>{spts(s.gain)}</b>).</p>")
        if w.ranked:
            rows = [[(str(i), ""), (res.add.name, ""), (res.add.pos.replace("DST", "DEF"), ""), n(res.add.proj),
                     (spts(res.gain), "num"), (", ".join(p.name for p in res.delta.starters_out()) or "(bench only)", "")]
                    for i, res in enumerate(w.ranked, start=1)]
            extra += "<p>Candidates ranked by lineup gain, not raw points:</p><div class='wrap'>" + table(
                ["#", "Player", "Pos", "Proj", "Gain", "Would replace"], rows) + "</div>"
    notes = "".join(f"<li>{escape(x)}</li>" for x in list(r.warnings) + list(r.notes) + list(r.extra_lines))
    title = {"lineup": "Best lineup", "trade": "Trade check", "waiver": "Waiver check"}[r.command]
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)}</title>
<style>
:root{{--bg:#fff;--fg:#1a1a1a;--mute:#666;--line:#ddd;--pos:#0a7d33;--neg:#c0262d;--card:#f4f6f8}}
@media(prefers-color-scheme:dark){{:root{{--bg:#16181b;--fg:#e8e8e8;--mute:#9aa;--line:#33383d;--pos:#4cc77a;--neg:#ff6b72;--card:#1f2327}}}}
body{{background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,sans-serif;max-width:960px;margin:0 auto;padding:16px}}
h1{{margin:.2em 0}}h2{{margin-top:1.6em;border-bottom:1px solid var(--line)}}h3{{margin:.4em 0}}
.pos{{color:var(--pos)}}.neg{{color:var(--neg)}}.mute{{color:var(--mute)}}
table{{width:100%;border-collapse:collapse}}th,td{{text-align:left;padding:5px 8px;border-bottom:1px solid var(--line)}}
td.num{{text-align:right;font-variant-numeric:tabular-nums}}td.tot{{font-weight:700}}
.wrap{{overflow-x:auto}}
.two{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}@media(max-width:700px){{.two{{grid-template-columns:1fr}}}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px;max-width:420px}}
.card table{{font-size:15px}}
.big-ish{{font-size:1.1em}}
footer{{margin-top:2em;color:var(--mute);font-size:.9em}}
</style></head><body>
<h1>{escape(title)}</h1>
<p class="mute">League folder: {escape(r.league_folder)}. Projections: {escape(r.proj_folder)} ({escape(r.kind_note)}).</p>
<h2>Names</h2>{names}
<h2>Lineups</h2>
<div class="two">
<div><h3>Best lineup (highest projected)</h3><div class="wrap">{lineup_table(best, 'proj')}</div></div>
<div><h3>Floor lineup (highest floor)</h3><div class="wrap">{lineup_table(floor, 'floor')}</div></div>
</div>
{diff_html}
{extra}
<h2>Close calls (within {r.close_within:g} points)</h2><ul>{close_html}</ul>
<h2>Bench</h2><div class="wrap">{table(["Pos", "Player", "Proj", "Floor", "Ceil", "FantasyPros FPTS"], bench_rows)}</div>
<h2>Not projected this week (bye or out?)</h2><ul>{notproj}</ul>
{"<h2>Please check</h2><ul>" + notes + "</ul>" if notes else ""}
<h2>Lineup card</h2>
<div class="card">{table(["Slot", "Player", "Proj"], card_rows)}</div>
<footer>{escape(DISCLAIMER)}</footer>
</body></html>"""

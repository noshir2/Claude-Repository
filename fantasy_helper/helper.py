"""Glue: load a league folder and a projection folder, match names, score, and build the answer."""
from dataclasses import dataclass, field
from pathlib import Path

from .lineup import (Delta, Lineup, Player, WaiverResult, align, apply_trade, apply_waiver, bench,
                     best_lineup, close_calls, make_player, rank_candidates)
from .names import Match, match_name, normalise
from .parse import ExportFormatError, League, ProjectionSet, load_projections, parse_league, parse_roster
from .scoring import DEFAULT_SCORING, FANTASYPROS_HALF_PPR

MISMATCH_TOLERANCE = 0.5


@dataclass
class RosterEntry:
    name: str                     # as written in roster.csv
    pos: str
    player: object                # the scored Player, or None when not in this folder's files


@dataclass
class Context:
    league: League
    proj: ProjectionSet
    players: list                 # roster players that were found in the files, scored
    match_lines: list             # "I matched X to Y" sentences
    unmatched: list               # roster names not found anywhere (with a reason when known)
    notes: list                   # ceiling estimate, season-file notes
    warnings: list                # scoring mismatch
    roster: list = field(default_factory=list)    # RosterEntry per roster.csv row (duplicates dropped)
    problems: list = field(default_factory=list)  # duplicate roster rows, unusable candidates/targets

    @property
    def weekly(self) -> bool:
        return not self.proj.season

    def projected(self, player: Player) -> bool:
        return any(p.name == player.name for p in self.players)


def _player_from(match: Match, rules: dict, weekly: bool) -> Player:
    return make_player(match.projection, rules, weekly)


def resolve(name: str, pos: str, projset: ProjectionSet) -> Match:
    """One name -> Match against every projected player (restricted to a position when given)."""
    return match_name(name, pos, projset.all())


def mismatch_warnings(projset: ProjectionSet, rules: dict) -> list:
    """Recompute every projected player and compare with the FPTS column FantasyPros shipped."""
    weekly = not projset.season
    off = []
    for p in projset.all():
        if p.fpts is None:
            continue
        mine = make_player(p, rules, weekly).proj
        if abs(mine - p.fpts) > MISMATCH_TOLERANCE:
            off.append((abs(mine - p.fpts), p, mine))
    if not off:
        return []
    non_k = [o for o in off if o[1].pos != "K"]
    worst = max(non_k or off, key=lambda o: o[0])
    gap, p, mine = worst
    others = len(off) - 1
    tail = f" ({others} other player{'s' if others != 1 else ''} differ too)" if others else ""
    fp = FANTASYPROS_HALF_PPR
    why = []
    if rules.get("fg") != fp["fg"]:
        why.append(f"league.txt pays {rules['fg']:g} per field goal and FantasyPros' FPTS column uses a flat {fp['fg']:g}")
    if rules.get("fg_missed", 0) != fp["fg_missed"]:
        why.append(f"league.txt takes {rules['fg_missed']:g} per missed field goal (FGA minus FG) and FantasyPros' "
                   "FPTS column takes nothing off")
    if not non_k and why:
        return [f"{p.name} (K): I get {mine:.1f}, FantasyPros' own number is {p.fpts:.1f}{tail}. "
                f"That is expected: {'; '.join(why)}; the lineup uses my number."]
    return [f"{p.name}: I get {mine:.1f} from the stat columns, FantasyPros' own FPTS number is {p.fpts:.1f}{tail}. "
            "Your league.txt may not match the scoring (Standard / Half PPR / PPR) selected on FantasyPros when "
            "you downloaded. The lineup uses MY number (your scoring); FPTS is shown for comparison only."]


def load_context(league_dir: Path, proj_dir: Path, label: str = "") -> Context:
    league = parse_league(league_dir / "league.txt", DEFAULT_SCORING)
    roster = parse_roster(league_dir / "roster.csv")
    projset = load_projections(proj_dir, league.positions_needed())
    weekly = not projset.season
    players, match_lines, unmatched, problems, entries = [], [], [], [], []
    seen = set()
    prefix = f"({label}) " if label else ""
    for name, pos in roster:
        m = resolve(name, pos, projset)
        if m.projection is None:
            why = m.detail or "not in any projection file (typo in roster.csv, or on bye / injured / not projected)"
            elsewhere = resolve(name, "", projset).projection if pos and not m.detail else None
            if elsewhere is not None:
                why = (f"roster.csv says {pos.replace('DST', 'DEF')} but '{elsewhere.name}' is in the "
                       f"{elsewhere.pos.replace('DST', 'DEF')} file; change the position in roster.csv (or leave it blank)")
            unmatched.append(f"{prefix}'{name}': {why}")
            entries.append(RosterEntry(name, pos, None))
            continue
        key = normalise(m.projection.name)
        if key in seen:
            who = "is listed twice" if name == m.projection.name else f"is '{m.projection.name}', which is already listed"
            problems.append(f"{prefix}Duplicate in roster.csv: '{name}' {who}; the second row is skipped.")
            continue
        seen.add(key)
        if m.line:
            match_lines.append(prefix + m.line)
        player = make_player(m.projection, league.scoring, weekly)
        players.append(player)
        entries.append(RosterEntry(name, pos, player))
    notes = []
    est = [p for p in players if p.ceil_estimated]
    if est:
        notes.append(f"{prefix}Ceiling for {len(est)} of {len(players)} players is estimated as projection + "
                     "(projection - floor) because the file has no 'high' row for them.")
    nolow = [p for p in players if not p.has_low]
    if nolow:
        notes.append(f"{prefix}{len(nolow)} player(s) have no 'low' row, so their floor equals their projection: "
                     + ", ".join(p.name for p in nolow))
    if projset.season:
        notes.append(f"{prefix}Season-total file: the defense points-allowed tier was skipped "
                     "(PA is a season total there, not one game's).")
    return Context(league, projset, players, match_lines, unmatched, notes,
                   [prefix + w for w in mismatch_warnings(projset, league.scoring)], entries, problems)


# ------------------------------------------------------------------ the three answers

@dataclass
class TradeBlock:
    give: list
    get: list
    week: Delta
    ros: Delta | None
    verdict: str
    notes: list = field(default_factory=list)   # e.g. a given player who is not projected this week


@dataclass
class WaiverBlock:
    single: WaiverResult | None
    ranked: list
    notes: list = field(default_factory=list)


@dataclass
class Report:
    command: str
    league_folder: str
    proj_folder: str
    kind_note: str
    match_lines: list
    unmatched: list
    lineup: Lineup
    floor_lineup: Lineup
    bench: list
    close: list
    close_within: float
    notes: list
    warnings: list
    trade: TradeBlock | None = None
    waiver: WaiverBlock | None = None
    opponent_line: str = ""
    ceiling_lineup: Lineup | None = None
    extra_lines: list = field(default_factory=list)
    problems: list = field(default_factory=list)   # duplicates, unusable candidates / trade targets


def pts(x: float) -> str:
    return f"{x:,.1f}"


def spts(x: float) -> str:
    return f"{'+' if x >= 0 else '-'}{abs(x):,.1f}"


def base_report(ctx: Context, command: str, within: float) -> Report:
    lu = best_lineup(ctx.players, ctx.league.slots, "proj", "floor")
    fl = align(best_lineup(ctx.players, ctx.league.slots, "floor", "proj"), lu)
    b = bench(ctx.players, lu)
    return Report(command, ctx.league.folder.name, ctx.proj.folder.name, ctx.proj.kind_note,
                  list(ctx.match_lines), list(ctx.unmatched), lu, fl, b, close_calls(lu, b, within), within,
                  list(ctx.notes), list(ctx.warnings), problems=list(ctx.problems))


def opponent_line(lineup: Lineup, ceiling: Lineup, floor: Lineup, opponent: float) -> str:
    diff = lineup.proj_total - opponent
    if diff >= 0:
        return (f"Opponent projected {pts(opponent)}, you {pts(lineup.proj_total)}: favoured by {pts(diff)}, "
                f"lean floor lineup (floor total {pts(floor.floor_total)}).")
    return (f"Opponent projected {pts(opponent)}, you {pts(lineup.proj_total)}: underdog by {pts(-diff)}, "
            f"lean ceiling lineup (ceiling total {pts(ceiling.ceil_total)}).")


def not_projected_stand_in(name: str, pos: str) -> Player:
    """A roster player with no projection in this folder: counts 0.0 so a trade / drop can still be judged."""
    return Player(name, pos, 0.0, 0.0, 0.0, has_low=False)


def _find_on_roster(ctx: Context, name: str, match_lines: list | None = None) -> Player:
    """A --give / --drop name -> that roster player. The projection file's spelling and roster.csv's own
    spelling both work; a roster player absent from this folder's files comes back as a 0.0 stand-in."""
    q = normalise(name)
    for p in ctx.players:
        if normalise(p.name) == q:
            return p
    m = match_name(name, "", ctx.roster)
    if m.projection is not None:
        entry = m.projection
        if m.line and match_lines is not None:
            match_lines.append(m.line.replace("fix roster.csv if that is wrong", "check the spelling if that is wrong"))
        return entry.player or not_projected_stand_in(entry.name, entry.pos)
    close = [p for p in ctx.players if q in normalise(p.name)]
    if len(close) == 1:
        return close[0]
    raise ExportFormatError(f"'{name}' is not on your roster. roster.csv lists: "
                            f"{', '.join(e.name for e in ctx.roster)}")


def _find_in_files(ctx: Context, name: str, match_lines: list) -> Player:
    m = resolve(name, "", ctx.proj)
    if m.projection is None:
        raise ExportFormatError(f"COULD NOT FIND '{name}' in the projection files in {ctx.proj.folder}"
                                + (f" ({m.detail})" if m.detail else "") + ". Check the spelling on FantasyPros.")
    if m.line:
        match_lines.append(m.line)
    if any(normalise(p.name) == normalise(m.projection.name) for p in ctx.players):
        raise ExportFormatError(f"'{m.projection.name}' is already on your roster.")
    return make_player(m.projection, ctx.league.scoring, ctx.weekly)


def trade_verdict(week: Delta, ros: Delta | None, give_on_bench: list) -> str:
    s = (f"Your starting lineup goes from {pts(week.before.proj_total)} to {pts(week.after.proj_total)} "
         f"this week ({spts(week.change)})")
    if ros is not None:
        s += (f" and from {pts(ros.before.proj_total)} to {pts(ros.after.proj_total)} rest of season "
              f"({spts(ros.change)})")
    changes = week.position_changes()
    gains = [k for k, v in changes.items() if v > 0]
    losses = [k for k, v in changes.items() if v < 0]
    depth = sorted({p.pos.replace("DST", "DEF") for p in give_on_bench if p.pos})
    parts = []
    if gains:
        parts.append("the gain is at " + ", ".join(gains))
    if losses:
        parts.append("the loss is at " + ", ".join(losses))
    if depth:
        parts.append("the loss is " + ", ".join(depth) + " depth (bench)")
    if not gains and not losses:
        parts.insert(0, "no starter changes this week")
    return s + "; " + ", ".join(parts) + "."


def unique_names(names: list, flag: str, problems: list) -> list:
    """Drop a name given twice (--get "X" --get "X") and say so, so he is not counted twice."""
    out, seen = [], set()
    for n in names:
        if normalise(n) in seen:
            problems.append(f"'{n}' was given twice with {flag}; counted once.")
            continue
        seen.add(normalise(n))
        out.append(n)
    return out


def trade_report(ctx: Context, give_names: list, get_names: list, within: float,
                 ros_ctx: Context | None = None) -> Report:
    rep = base_report(ctx, "trade", within)
    give_names = unique_names(give_names, "--give", rep.problems)
    get_names = unique_names(get_names, "--get", rep.problems)
    give = [_find_on_roster(ctx, n, rep.match_lines) for n in give_names]
    get = [_find_in_files(ctx, n, rep.match_lines) for n in get_names]
    notes = [f"{p.name} is not projected this week (bye or out?), so giving him counts as 0.0 this week."
             for p in give if not ctx.projected(p)]
    week = apply_trade(ctx.players, give, get, ctx.league.slots)
    ros = None
    if ros_ctx is not None:
        prefix = "(rest of season) "
        for mine, theirs in ((rep.match_lines, ros_ctx.match_lines), (rep.unmatched, ros_ctx.unmatched),
                             (rep.notes, ros_ctx.notes), (rep.warnings, ros_ctx.warnings)):
            mine += [x for x in theirs if x.replace(prefix, "", 1) not in mine]  # skip exact repeats
        if not ros_ctx.proj.season:
            rep.warnings.append("The --ros folder " + ros_ctx.proj.kind_note + "; rest-of-season numbers "
                                "should be season-style totals.")
        ros_give, ros_get = [], []
        for n in give_names:
            p = _find_on_roster(ros_ctx, n)
            ros_give.append(p)
            if not ros_ctx.projected(p):
                notes.append(f"(rest of season) {p.name} is not in the --ros files, so giving him counts as 0.0 there.")
        missing = []
        for n in get_names:
            try:
                ros_get.append(_find_in_files(ros_ctx, n, rep.match_lines))
            except ExportFormatError as e:
                missing.append(n)
                rep.problems.append(f"(rest of season) Skipped trade target: {e}")
        if missing:
            # Without the player you get, the rest-of-season number would be a one-sided trade: not the
            # trade you asked about. Leave it out rather than feed a wrong number into the verdict.
            notes.append(f"(rest of season) not computed: {', '.join(missing)} "
                         f"{'is' if len(missing) == 1 else 'are'} not in the --ros files.")
        else:
            ros = apply_trade(ros_ctx.players, ros_give, ros_get, ros_ctx.league.slots)
    give_on_bench = [p for p in give if p.name not in week.before.names()]
    rep.trade = TradeBlock(give, get, week, ros, trade_verdict(week, ros, give_on_bench), notes)
    return rep


def waiver_report(ctx: Context, add_name: str | None, drop_name: str | None, candidate_names: list,
                  within: float) -> Report:
    rep = base_report(ctx, "waiver", within)
    drop = _find_on_roster(ctx, drop_name, rep.match_lines) if drop_name else None
    notes = []
    if drop is not None and not ctx.projected(drop):
        notes.append(f"{drop.name} is not projected this week (bye or out?), so dropping him costs 0.0 this week.")
    single = None
    if add_name:
        add = _find_in_files(ctx, add_name, rep.match_lines)
        single = apply_waiver(ctx.players, add, drop, ctx.league.slots)
    cands = []
    for n in unique_names(candidate_names, "--candidates", rep.problems):
        try:
            cands.append(_find_in_files(ctx, n, rep.match_lines))
        except ExportFormatError as e:
            rep.problems.append(f"Skipped candidate: {e}")
    ranked = rank_candidates(ctx.players, cands, drop, ctx.league.slots) if cands else []
    rep.waiver = WaiverBlock(single, ranked, notes)
    return rep

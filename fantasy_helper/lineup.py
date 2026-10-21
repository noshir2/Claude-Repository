"""Pure lineup math: best lineup by brute force, close calls, trade and waiver deltas."""
import itertools
from dataclasses import dataclass, field

from .scoring import score


@dataclass(frozen=True)
class Player:
    name: str
    pos: str
    proj: float
    floor: float
    ceil: float
    ceil_estimated: bool = False   # True when there was no 'high' row: ceil = proj + (proj - floor)
    fpts_csv: float | None = None  # FantasyPros' own FPTS number, shown for comparison only
    team: str = ""
    has_low: bool = True


def make_player(projection, rules: dict, weekly: bool = True, name: str | None = None) -> Player:
    """Projection + league scoring -> Player with projected, floor and ceiling points."""
    pa = weekly  # DST points-allowed tier only makes sense for one game
    proj = score(projection.pos, projection.stats, rules, pa)
    has_low = projection.low is not None
    floor = score(projection.pos, projection.low, rules, pa) if has_low else proj
    floor = min(floor, proj)
    if projection.high is not None:
        ceil, estimated = max(score(projection.pos, projection.high, rules, pa), proj), False
    else:
        ceil, estimated = proj + (proj - floor), True
    return Player(name or projection.name, projection.pos, proj, floor, ceil, estimated,
                  projection.fpts, projection.team, has_low)


@dataclass
class Entry:
    slot: str            # QB, RB, WR, TE, FLEX, K, DEF
    allowed: tuple
    player: Player | None


@dataclass
class Lineup:
    entries: list
    key: str = "proj"

    def total(self, key: str | None = None) -> float:
        key = key or self.key
        return sum(getattr(e.player, key) for e in self.entries if e.player)

    @property
    def proj_total(self) -> float:
        return self.total("proj")

    @property
    def floor_total(self) -> float:
        return self.total("floor")

    @property
    def ceil_total(self) -> float:
        return self.total("ceil")

    def starters(self) -> list:
        return [e.player for e in self.entries if e.player]

    def names(self) -> set:
        return {p.name for p in self.starters()}

    def slot_of(self, name: str) -> str | None:
        for e in self.entries:
            if e.player and e.player.name == name:
                return e.slot
        return None


def prune(players: list, slots: list, key: str = "proj", tiebreak: str = "floor") -> list:
    """Drop players who can never start: at most N players of a position can be in the lineup (N = the
    slots that accept it), so anyone below the top N of his position by (key, tiebreak) is out. The
    search stays exact (swapping him in for a top-N player could only lower the total) but a 25-man
    roster with two flex types goes from minutes to well under a second."""
    room = {}
    for s in slots:
        for pos in s.allowed:
            room[pos] = room.get(pos, 0) + s.count
    keep = set()
    for pos, n in room.items():
        same = sorted((p for p in players if p.pos == pos), key=lambda p: (-getattr(p, key), -getattr(p, tiebreak)))
        keep.update(id(p) for p in same[:n])
    return [p for p in players if id(p) in keep]


def best_lineup(players: list, slots: list, key: str = "proj", tiebreak: str = "floor") -> Lineup:
    """Exact search: every way of filling the slots is tried; the highest sum of `key` wins,
    ties broken by the sum of `tiebreak`. Players who cannot start are pruned first (see prune)."""
    players = prune(players, slots, key, tiebreak)
    groups = []
    for s in slots:
        elig = sorted((p for p in players if p.pos in s.allowed),
                      key=lambda p: (-getattr(p, key), -getattr(p, tiebreak)))   # best combos are tried first
        groups.append((s, elig))
    # The most a slot group could add if it had free pick of its eligible players; summed from the end so
    # a branch that cannot catch the best lineup found so far is skipped (ties are kept for the tie-break).
    at_most = [sum(getattr(p, key) for p in elig[:slot.count]) for slot, elig in groups]
    still_possible = [0.0] * (len(groups) + 1)
    for i in range(len(groups) - 1, -1, -1):
        still_possible[i] = still_possible[i + 1] + at_most[i]
    best_val, best_pick = None, None

    def search(i: int, used: frozenset, picked: list, val: float, tb: float):
        nonlocal best_val, best_pick
        if i == len(groups):
            # Round first: two lineups with the same one-decimal numbers added in a different order
            # can differ by a float rounding crumb, which would stop the floor tie-break from running.
            key_val = (round(val, 6), round(tb, 6))
            if best_val is None or key_val > best_val:
                best_val, best_pick = key_val, list(picked)
            return
        if best_val is not None and round(val + still_possible[i], 6) < best_val[0]:
            return
        slot, elig = groups[i]
        free = [p for p in elig if p not in used]
        n = min(slot.count, len(free))
        for combo in itertools.combinations(free, n):
            search(i + 1, used | frozenset(combo), picked + [(slot, combo)],
                   val + sum(getattr(p, key) for p in combo), tb + sum(getattr(p, tiebreak) for p in combo))

    search(0, frozenset(), [], 0.0, 0.0)
    entries = []
    for slot, combo in best_pick or []:
        chosen = sorted(combo, key=lambda p: -getattr(p, key))
        for k in range(slot.count):
            entries.append(Entry(slot.label, slot.allowed, chosen[k] if k < len(chosen) else None))
    return Lineup(entries, key)


def align(other: Lineup, reference: Lineup) -> Lineup:
    """Re-slot `other` so players it shares with `reference` sit in the same slots (RB vs FLEX is
    just labelling). Falls back to `other` unchanged if the leftovers cannot be placed."""
    remaining = list(other.starters())
    entries = [Entry(e.slot, e.allowed, None) for e in reference.entries]
    for i, e in enumerate(reference.entries):
        if e.player:
            hit = next((p for p in remaining if p.name == e.player.name), None)
            if hit is not None:
                entries[i].player = hit
                remaining.remove(hit)
    empties = [i for i, e in enumerate(entries) if e.player is None]
    for perm in itertools.permutations(remaining):
        if all(p.pos in entries[i].allowed for i, p in zip(empties, perm)):
            for i, p in zip(empties, perm):
                entries[i].player = p
            return Lineup(entries, other.key)
    return other


def bench(players: list, lineup: Lineup) -> list:
    names = lineup.names()
    return sorted((p for p in players if p.name not in names), key=lambda p: -p.proj)


@dataclass
class CloseCall:
    slot: str
    starter: Player
    other: Player

    @property
    def gap(self) -> float:
        return abs(self.starter.proj - self.other.proj)


def close_calls(lineup: Lineup, bench_players: list, within: float = 1.5) -> list:
    """Starter vs an eligible bench player whose projections are within `within` points."""
    out = []
    for e in lineup.entries:
        if not e.player:
            continue
        for b in bench_players:
            if b.pos in e.allowed and abs(e.player.proj - b.proj) <= within + 1e-9:
                out.append(CloseCall(e.slot, e.player, b))
    return sorted(out, key=lambda c: c.gap)


@dataclass
class Delta:
    """Best lineup before and after a roster change."""
    before: Lineup
    after: Lineup

    @property
    def change(self) -> float:
        return self.after.proj_total - self.before.proj_total

    def starters_out(self) -> list:
        return [p for p in self.before.starters() if p.name not in self.after.names()]

    def starters_in(self) -> list:
        return [p for p in self.after.starters() if p.name not in self.before.names()]

    def position_changes(self) -> dict:
        """Position (QB, RB, WR, TE, K, DEF) -> change in the points its STARTERS contribute.
        Grouped by position, not slot, so a RB sliding from FLEX to RB is not reported as a change."""
        out: dict[str, float] = {}
        for lu, sign in ((self.before, -1), (self.after, 1)):
            for p in lu.starters():
                label = p.pos.replace("DST", "DEF")
                out[label] = out.get(label, 0.0) + sign * p.proj
        order = ("QB", "RB", "WR", "TE", "K", "DEF")
        return {k: out[k] for k in order if k in out and abs(out[k]) > 1e-9}


def apply_trade(players: list, give: list, get: list, slots: list) -> Delta:
    give_names = {p.name for p in give}
    after = [p for p in players if p.name not in give_names] + list(get)
    return Delta(best_lineup(players, slots), best_lineup(after, slots))


def weakest_bench(players: list, lineup: Lineup) -> Player | None:
    b = bench(players, lineup)
    if b:
        return b[-1]
    starters = lineup.starters()
    return min(starters, key=lambda p: p.proj) if starters else None


@dataclass
class WaiverResult:
    add: Player
    drop: Player | None
    delta: Delta
    drop_was_default: bool

    @property
    def gain(self) -> float:
        return self.delta.change


def apply_waiver(players: list, add: Player, drop: Player | None, slots: list) -> WaiverResult:
    before = best_lineup(players, slots)
    default = drop is None
    if default:
        drop = weakest_bench(players, before)
    after_players = [p for p in players if drop is None or p.name != drop.name] + [add]
    return WaiverResult(add, drop, Delta(before, best_lineup(after_players, slots)), default)


def rank_candidates(players: list, candidates: list, drop: Player | None, slots: list) -> list:
    """Rank pickups by how much they raise the best lineup, not by raw points."""
    results = [apply_waiver(players, c, drop, slots) for c in candidates]
    return sorted(results, key=lambda r: (-r.gain, -r.add.proj))

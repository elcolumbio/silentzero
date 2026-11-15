"""Five gates. Each one guards a way a system can fail silently; two of the demo
cases are real.

A gate takes what a run produced and returns a :class:`Verdict`. It never fixes
anything and it never logs a warning: it passes or it fails, and a failed gate stops
an artefact from being written. A warning that nobody reads is how a failure like
this survives.

Out of scope on purpose: model-quality gates. Golden-set precision, judge agreement
and classifier drift are real gates and they belong to your project, not here. This
module is only the family that cannot tell *nothing* from *broken*.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping, Sequence

from .ledger import Ledger
from .result import Reading, State


@dataclass(frozen=True)
class Verdict:
    """One gate's answer. ``ok`` is the only thing a caller may branch on."""

    gate: str
    ok: bool
    detail: str
    #: The named things that failed — boards, documents, rows. Empty when ``ok``.
    subjects: tuple[str, ...] = ()
    #: What the gate was checking against, for the report.
    bound: str = ""

    def __str__(self) -> str:
        mark = "pass" if self.ok else "FAIL"
        return f"[{mark}] {self.gate}: {self.detail}"


def _passed(gate: str, detail: str, bound: str = "") -> Verdict:
    return Verdict(gate, True, detail, (), bound)


def _failed(gate: str, detail: str, subjects: Iterable[str], bound: str = "") -> Verdict:
    return Verdict(gate, False, detail, tuple(subjects), bound)


# ---------------------------------------------------------------------------
# 1. coverage — did we manage to look at all?
# ---------------------------------------------------------------------------

def coverage(readings: Sequence[Reading], *, min_ok: float = 0.95, name: str = "coverage") -> Verdict:
    """Fail when too few sources could be looked at at all.

    Catches: an expired credential, a renamed board token, a network outage, a
    changed base URL. All of which read downstream as "this employer posts nothing"
    unless something refuses to accept the run.
    """
    if not readings:
        return _failed(name, "no readings at all — the run produced nothing to judge", ["<run>"],
                       bound=f"≥ {min_ok:.0%} of sources reachable")
    blind = [r for r in readings if not r.looked]
    fraction = 1 - len(blind) / len(readings)
    bound = f"≥ {min_ok:.0%} of sources reachable"
    if fraction < min_ok:
        return _failed(
            name,
            f"{len(blind)} of {len(readings)} sources could not be looked at "
            f"({fraction:.0%} reachable)",
            [r.source for r in blind],
            bound,
        )
    return _passed(name, f"{fraction:.0%} of {len(readings)} sources reachable", bound)


# ---------------------------------------------------------------------------
# 2. yield — did the sources that used to produce rows still produce rows?
# ---------------------------------------------------------------------------

def yield_gate(
    readings: Sequence[Reading],
    ledger: Ledger,
    *,
    run_id: int | None = None,
    floor: int | None = None,
    max_drop: float | None = None,
    name: str = "yield",
) -> Verdict:
    """Fail when a source that has produced rows before produces none now.

    **This is the gate the other checks cannot replace.** A wrapper catches a
    retired endpoint's 404 and returns an empty list: every fetch succeeds, the
    success rate stays at 100 %, coverage stays green, and every reading built on
    it is a silent zero. Success rate is a liar. Only the source's own history
    makes today's zero legible.

    Only readings that actually looked are considered — an unreachable source is
    :func:`coverage`'s business, and reporting it twice buries the signal.

    ``floor`` is an absolute minimum row count per source; ``max_drop`` fails a
    source that returned rows but far fewer than last time (0.5 = "half of what it
    last produced"), which catches half-broken pagination.
    """
    if run_id is None:
        run_id = ledger.last_run()
    considered = [r for r in readings if r.looked]
    failures: list[tuple[str, str]] = []

    for r in considered:
        was = ledger.last_found(r.source, before_run=run_id)
        if r.count == 0:
            if was is not None:
                failures.append((
                    r.source,
                    f"produced {was.count} rows as recently as {was.at:%Y-%m-%d}, and 0 now",
                ))
            # No history: this source has never produced anything. Today's zero is
            # not news, and calling it a failure would cry wolf on every new source.
            continue
        if floor is not None and r.count < floor:
            failures.append((r.source, f"{r.count} rows, floor is {floor}"))
        elif max_drop is not None and was is not None and was.count > 0:
            if r.count < was.count * (1 - max_drop):
                failures.append((
                    r.source,
                    f"{r.count} rows against {was.count} last seen "
                    f"({1 - r.count / was.count:.0%} drop)",
                ))

    bound_bits = ["no source that had rows drops to zero"]
    if floor is not None:
        bound_bits.append(f"≥ {floor} rows each")
    if max_drop is not None:
        bound_bits.append(f"no drop > {max_drop:.0%}")
    bound = ", ".join(bound_bits)

    if failures:
        detail = "; ".join(f"{s} — {why}" for s, why in failures)
        return _failed(name, f"{len(failures)} source(s) lost yield: {detail}",
                       [s for s, _ in failures], bound)
    return _passed(name, f"{len(considered)} source(s) held their yield", bound)


# ---------------------------------------------------------------------------
# 3. stock — is the thing we built big enough to be the thing we meant to build?
# ---------------------------------------------------------------------------

def stock(
    what: str,
    actual: int,
    *,
    floor: int,
    previous: int | None = None,
    max_drop: float = 0.5,
    name: str = "stock",
) -> Verdict:
    """Fail when a built artefact is implausibly small.

    Catches: a build that fetched over the network, timed out, and produced a corpus
    of one document. A service holding half a corpus answers "no finding" to every
    question while looking exactly like a correctly working tool — the output is
    well-formed, the tests pass, and every answer is wrong in the safe-sounding
    direction. An empty stock must never be able to run.

    Set ``floor`` from what the artefact cannot be smaller than and still mean
    anything, and pass ``previous`` (the last good build's size) so a gradual
    collapse is caught as well as a total one.
    """
    bound = f"≥ {floor}" + (f", and no drop > {max_drop:.0%} from {previous}" if previous else "")
    if actual < floor:
        return _failed(name, f"{what}: {actual} against a floor of {floor}", [what], bound)
    if previous is not None and previous > 0 and actual < previous * (1 - max_drop):
        return _failed(
            name,
            f"{what}: {actual} against {previous} last time ({1 - actual / previous:.0%} drop)",
            [what],
            bound,
        )
    return _passed(name, f"{what}: {actual}", bound)


# ---------------------------------------------------------------------------
# 4. freshness — does every served number still carry a date, and a recent one?
# ---------------------------------------------------------------------------

def freshness(
    dated: Mapping[str, datetime | None] | Iterable[tuple[str, datetime | None]],
    *,
    max_age_days: float,
    now: datetime | None = None,
    name: str = "freshness",
) -> Verdict:
    """Fail on anything served that is too old, or that carries no date at all.

    Catches: a number that looks the same after three months as on the day it was
    measured. An undated item fails as hard as a stale one — a fact with no
    retrieval date cannot be shown to have gone stale, which is the same blindness
    in a different coat.
    """
    items = list(dated.items()) if isinstance(dated, Mapping) else list(dated)
    now = now or datetime.now(timezone.utc)
    limit = timedelta(days=max_age_days)
    bound = f"nothing older than {max_age_days:g} days, and nothing undated"

    undated = [label for label, at in items if at is None]
    stale = []
    for label, at in items:
        if at is None:
            continue
        if at.tzinfo is None:
            at = at.replace(tzinfo=timezone.utc)
        if now - at > limit:
            stale.append((label, (now - at).days))

    if undated or stale:
        bits = []
        if undated:
            bits.append(f"{len(undated)} undated ({', '.join(undated[:5])})")
        if stale:
            bits.append("stale: " + ", ".join(f"{l} ({d}d)" for l, d in stale[:5]))
        return _failed(name, "; ".join(bits), [l for l, _ in stale] + undated, bound)
    return _passed(name, f"all {len(items)} slice(s) dated and within {max_age_days:g} days", bound)


# ---------------------------------------------------------------------------
# 5. provenance — does every row say where it came from?
# ---------------------------------------------------------------------------

def provenance(
    rows: Sequence[Mapping[str, Any]],
    *,
    required: Sequence[str] = ("source", "retrieved_at", "rank"),
    banned: Mapping[str, Iterable[Any]] | None = None,
    name: str = "provenance",
    label: str = "row",
) -> Verdict:
    """Fail when a row cannot say where it came from, or carries a value that must
    never reach a finished artefact.

    Catches two shapes of the same thing. A row with no rank is a claim with no
    author, and it will be read next quarter as though someone stood behind it.
    And a default nobody checked — a dimension marked ``assumed``, a rate marked
    ``inferred`` — looks in a finished document exactly like a measured one, which
    is how an unchecked placeholder gets ordered, quoted or filed.

    ``banned={"provenance": {"assumed"}}`` is the second half.
    """
    missing: list[str] = []
    forbidden: list[str] = []
    for i, row in enumerate(rows):
        ident = str(row.get("id", f"{label} {i}"))
        absent = [f for f in required if row.get(f) in (None, "")]
        if absent:
            missing.append(f"{ident} (no {', '.join(absent)})")
        for fieldname, values in (banned or {}).items():
            if row.get(fieldname) in set(values):
                forbidden.append(f"{ident} ({fieldname}={row.get(fieldname)})")

    bound = f"every {label} carries {', '.join(required)}"
    if banned:
        bound += "; " + "; ".join(f"no {k} in {sorted(map(str, v))}" for k, v in banned.items())

    if missing or forbidden:
        bits = []
        if missing:
            bits.append(f"{len(missing)} without provenance: {', '.join(missing[:5])}")
        if forbidden:
            bits.append(f"{len(forbidden)} carrying a banned value: {', '.join(forbidden[:5])}")
        return _failed(name, "; ".join(bits), missing + forbidden, bound)
    return _passed(name, f"all {len(rows)} {label}(s) carry their provenance", bound)

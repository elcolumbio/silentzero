"""The three states, and constructors that refuse to blur them.

A list of length zero is the most dangerous value a pipeline handles, because two
completely different facts arrive wearing it:

    "I looked, and there is nothing there."
    "I could not look."

Every failure this library exists for is a system that stored the second as the first.
So there is no way, in this module, to reach ``EMPTY`` from an error, and no way to
reach ``FOUND`` with a count of zero.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from collections.abc import Mapping
from typing import Any, Callable, Sequence


def _now() -> datetime:
    return datetime.now(timezone.utc)


class State(enum.Enum):
    """What one look at one source actually established."""

    FOUND = "found"
    #: Nothing is there, and the source said so in a way we can point at.
    EMPTY = "empty"
    #: We did not establish anything. An error, or a zero we cannot account for.
    UNREACHABLE = "unreachable"

    def __str__(self) -> str:  # pragma: no cover - display only
        return self.value


@dataclass(frozen=True)
class Reading:
    """One look at one source.

    Build these with :meth:`found`, :meth:`empty` or :meth:`unreachable`; the
    constructor is not the interface, the three of them are.
    """

    source: str
    state: State
    count: int
    at: datetime
    #: Why this state, in the reporter's own words. Mandatory for the two states
    #: that are easy to get wrong.
    because: str = ""
    context: dict[str, Any] = field(default_factory=dict)

    # -- constructors ----------------------------------------------------

    @classmethod
    def found(cls, source: str, count: int, *, at: datetime | None = None, **context: Any) -> "Reading":
        if count < 1:
            raise ValueError(
                f"found({source!r}, {count}) — a count of zero is not a finding. "
                "Use empty(because=...) if the source proved there is nothing, "
                "or unreachable(because=...) if it did not."
            )
        return cls(source, State.FOUND, count, at or _now(), "", context)

    @classmethod
    def empty(cls, source: str, *, because: str, at: datetime | None = None, **context: Any) -> "Reading":
        """Nothing is there — and ``because`` says how the source established that.

        "the response carried an explicit total of 0" is a reason.
        "the list was empty" is the thing we are trying to tell apart, not a reason.
        """
        if not because.strip():
            raise ValueError(
                f"empty({source!r}) needs a reason. An empty result with nothing "
                "backing it is an unreachable source, not an empty one."
            )
        return cls(source, State.EMPTY, 0, at or _now(), because.strip(), context)

    @classmethod
    def unreachable(cls, source: str, *, because: str, at: datetime | None = None, **context: Any) -> "Reading":
        if not because.strip():
            raise ValueError(f"unreachable({source!r}) needs a reason")
        return cls(source, State.UNREACHABLE, 0, at or _now(), because.strip(), context)

    # -- predicates ------------------------------------------------------

    @property
    def looked(self) -> bool:
        """True when we established something, whether or not we found anything."""
        return self.state is not State.UNREACHABLE

    def __str__(self) -> str:
        tail = f" — {self.because}" if self.because else ""
        return f"{self.source}: {self.state.value} ({self.count}){tail}"


def look(
    source: str,
    fetch: Callable[[], Any],
    *,
    count: Callable[[Any], int] = len,
    proves_empty: Callable[[Any], str | None] | None = None,
) -> Reading:
    """Turn a fetch into a :class:`Reading` without ever inventing an ``EMPTY``.

    Three outcomes, and the third is the whole point:

    * ``fetch`` raises              -> ``UNREACHABLE``, carrying the exception.
    * ``fetch`` returns rows        -> ``FOUND``.
    * ``fetch`` returns nothing     -> ``EMPTY`` only if ``proves_empty`` returns a
      reason. Otherwise ``UNREACHABLE``, because an unexplained zero is a failure
      that has not been noticed yet.

    ``count`` says how many rows a payload holds; the default ``len`` fits a list of
    rows. A response body (a mapping, a string, bytes) needs its own ``count``:
    ``len()`` of it would count keys or characters, so ``look`` raises ``TypeError``
    rather than guess.

    ``proves_empty`` is where the caller states what emptiness looks like on *this*
    endpoint — an explicit ``total: 0``, a "no open roles" marker, an HTTP 204. If the
    endpoint offers no such proof, do not write one: an unproven zero belongs in
    ``UNREACHABLE``, and the yield gate will tell you which of the two it was.
    """
    try:
        payload = fetch()
    except Exception as exc:  # deliberate: any failure to look is a failure to look
        return Reading.unreachable(source, because=f"{type(exc).__name__}: {exc}")

    if count is len and isinstance(payload, (Mapping, str, bytes)):
        # len() of a response body counts its keys or its characters, so an empty board
        # wrapped in {"jobs": [], "meta": {...}} would read as FOUND. That is this
        # library's own bug class; refuse it instead of counting.
        raise TypeError(
            f"look({source!r}): fetch returned a {type(payload).__name__}, and len() of it "
            "does not count rows. Return the rows themselves, or pass "
            "count=lambda body: len(body['rows'])."
        )

    n = count(payload)
    if n > 0:
        return Reading.found(source, n)

    reason = proves_empty(payload) if proves_empty else None
    if reason:
        return Reading.empty(source, because=reason)
    return Reading.unreachable(
        source,
        because="returned no rows and offered no proof that there are none",
    )


def must_reach(readings: Sequence[Reading]) -> list[Reading]:
    """Raise unless every reading actually looked.

    For the surfaces where a silent zero is not survivable — a build input, a
    credential-backed query. "Nobody asked" and "I could not look" are different
    sentences and this refuses to say them the same way.
    """
    blind = [r for r in readings if not r.looked]
    if blind:
        detail = "; ".join(f"{r.source} ({r.because})" for r in blind)
        raise Unreachable(f"could not look at {len(blind)} source(s): {detail}")
    return list(readings)


class Unreachable(RuntimeError):
    """A source could not be looked at, where an empty answer would have lied."""

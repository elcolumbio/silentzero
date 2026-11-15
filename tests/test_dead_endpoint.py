"""Failure 1: a retired endpoint's 404 caught and returned as an empty list.

The test that matters is not that the yield gate fails. It is that everything else
passes while it does — which is exactly what let the real thing run broken.
"""

from datetime import datetime, timedelta, timezone

import pytest

from silentzero import Ledger, Reading, coverage, record_run, yield_gate


@pytest.fixture
def ledger():
    """Eight weekly runs in which all three boards produced rows."""
    led = Ledger()
    base = datetime.now(timezone.utc) - timedelta(days=63)
    for week in range(8):
        at = base + timedelta(days=7 * week)
        record_run(led, [
            Reading.found("greenhouse:gitlab", 129, at=at),
            Reading.found("greenhouse:doctolib", 41, at=at),
            Reading.found("lever:acme", 12, at=at),
        ], label=f"weekly {week}")
    yield led
    led.close()


TODAY = [
    Reading.found("greenhouse:gitlab", 131),
    Reading.found("greenhouse:doctolib", 39),
    # Retired. A wrapper around the fetch caught the 404 and returned [] instead
    # of raising it.
    Reading.empty("lever:acme", because="404 from the board, caught and returned as []"),
]


def test_success_rate_is_a_liar():
    """The check most pipelines already have. It reports a perfect run."""
    assert all(r.looked for r in TODAY)
    assert sum(r.looked for r in TODAY) / len(TODAY) == 1.0


def test_coverage_passes_too(ledger):
    assert coverage(TODAY, min_ok=0.95).ok


def test_yield_catches_it(ledger):
    run = record_run(ledger, TODAY, label="today")
    v = yield_gate(TODAY, ledger, run_id=run)
    assert not v.ok
    assert v.subjects == ("lever:acme",)
    assert "12 rows" in v.detail and "0 now" in v.detail


def test_a_source_that_never_produced_anything_is_not_a_failure(ledger):
    """Otherwise the gate cries wolf on every newly added board and gets muted."""
    readings = [*TODAY[:2], Reading.empty("lever:brand-new", because="no roles posted yet")]
    run = record_run(ledger, readings, label="with a new board")
    v = yield_gate(readings, ledger, run_id=run)
    assert v.ok, v.detail


def test_unreachable_sources_are_left_to_coverage(ledger):
    """Two gates reporting the same thing buries the one that is news."""
    readings = [*TODAY[:2], Reading.unreachable("lever:acme", because="connection reset")]
    run = record_run(ledger, readings, label="outage")
    assert yield_gate(readings, ledger, run_id=run).ok
    assert not coverage(readings, min_ok=0.95).ok


def test_half_broken_pagination_is_caught_by_max_drop(ledger):
    """A board that returns rows, but a fraction of what it held yesterday."""
    readings = [Reading.found("greenhouse:gitlab", 20), *TODAY[1:2]]
    run = record_run(ledger, readings, label="page 1 only")
    v = yield_gate(readings, ledger, run_id=run, max_drop=0.5)
    assert not v.ok
    assert "greenhouse:gitlab" in v.subjects

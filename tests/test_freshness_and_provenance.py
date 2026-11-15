"""Failures 2 and 4 in their served form.

Freshness: a number without its date looks the same after three months as on the day
it was measured. Provenance: an `assumed` value prints exactly like a measured one.
"""

from datetime import datetime, timedelta, timezone

from silentzero import freshness, provenance

NOW = datetime(2026, 9, 6, tzinfo=timezone.utc)


def test_a_fresh_dated_slice_passes():
    assert freshness({"berlin": NOW - timedelta(days=3)}, max_age_days=30, now=NOW).ok


def test_a_stale_slice_fails():
    v = freshness({"berlin": NOW - timedelta(days=94)}, max_age_days=30, now=NOW)
    assert not v.ok and "94d" in v.detail


def test_an_undated_slice_fails_as_hard_as_a_stale_one():
    """A fact with no retrieval date cannot be shown to have gone stale."""
    v = freshness({"berlin": None}, max_age_days=30, now=NOW)
    assert not v.ok and "undated" in v.detail


def test_naive_datetimes_are_read_as_utc_rather_than_crashing():
    v = freshness([("berlin", datetime(2026, 9, 1))], max_age_days=30, now=NOW)
    assert v.ok


ROWS = [
    {"id": "slot-width", "source": "vendor STEP", "retrieved_at": "2026-08-14",
     "rank": 1, "provenance": "measured"},
    {"id": "screw-torque", "source": None, "retrieved_at": None,
     "rank": None, "provenance": "assumed"},
]


def test_a_row_without_a_rank_does_not_exist():
    v = provenance(ROWS, label="dimension")
    assert not v.ok
    assert "screw-torque (no source, retrieved_at, rank)" in v.detail


def test_an_assumed_value_may_not_reach_a_finished_artefact():
    v = provenance(ROWS[:1] + [{**ROWS[1], "source": "default", "retrieved_at": "2026-08-14",
                                "rank": 3}],
                   banned={"provenance": ["assumed"]}, label="dimension")
    assert not v.ok
    assert "provenance=assumed" in v.detail


def test_a_fully_sourced_set_passes():
    assert provenance(ROWS[:1], banned={"provenance": ["assumed"]}, label="dimension").ok

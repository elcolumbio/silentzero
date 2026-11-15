"""Failure 3 (synthetic — the shape we gate against): a fetch that timed out kept
only the one page it had already saved.

Nothing about a small corpus says whether it is small on purpose or a fraction of
what was meant to be there: the output is well-formed, the tests pass, and anything
built on it is wrong in the direction that sounds careful.
"""

from silentzero import GateFailure, health, refuse_unless_ok, stock


def test_the_good_build_passes():
    assert stock("corpus documents", 3000, floor=500, previous=2980).ok


def test_one_document_is_caught_by_the_floor():
    v = stock("corpus documents", 1, floor=500, previous=3000)
    assert not v.ok
    assert "floor of 500" in v.detail


def test_a_gradual_collapse_is_caught_by_the_drop():
    """Above the floor, and still not the corpus we meant to build."""
    v = stock("corpus documents", 600, floor=500, previous=1800)
    assert not v.ok
    assert "67% drop" in v.detail


def test_an_empty_stock_can_never_run():
    report = health(stock("corpus documents", 0, floor=500))
    assert report.exit_code == 1
    try:
        refuse_unless_ok(report, "the deploy")
    except GateFailure as exc:
        assert "refusing to produce the deploy" in str(exc)
    else:
        raise AssertionError("the deploy was not refused")

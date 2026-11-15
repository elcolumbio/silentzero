"""The three states, checked against responses captured from a live ATS.

`greenhouse-gitlab-departments.json` is the important one: a real HTTP 200 whose
body contains departments with `"jobs": []` next to departments with jobs. Both
shapes come out of the same working endpoint on the same request, which is exactly
why an empty list on its own establishes nothing.
"""

import pytest

from silentzero import Reading, State, Unreachable, look, must_reach


def test_found_refuses_a_count_of_zero():
    with pytest.raises(ValueError, match="not a finding"):
        Reading.found("greenhouse:gitlab", 0)


def test_empty_refuses_to_be_asserted_without_a_reason():
    with pytest.raises(ValueError, match="needs a reason"):
        Reading.empty("greenhouse:gitlab", because="   ")


def test_a_raising_fetch_can_never_become_empty():
    def fetch():
        raise TimeoutError("read timed out after 30s")

    r = look("greenhouse:gitlab", fetch)
    assert r.state is State.UNREACHABLE
    assert not r.looked
    assert "TimeoutError" in r.because


def test_a_live_board_with_jobs_is_found(capture):
    payload = capture("greenhouse-gitlab-jobs")
    r = look("greenhouse:gitlab", lambda: payload["jobs"])
    assert r.state is State.FOUND
    assert r.count == len(payload["jobs"]) > 0


def test_an_unexplained_zero_is_unreachable_not_empty(capture):
    """The default has to be the safe one, or nobody sets it."""
    dept = next(d for d in capture("greenhouse-gitlab-departments")["departments"]
                if not d["jobs"])
    r = look(f"greenhouse:gitlab:{dept['name']}", lambda: dept["jobs"])
    assert r.state is State.UNREACHABLE
    assert "no proof" in r.because


def test_a_zero_the_source_accounts_for_is_empty(capture):
    """Same bytes, and now the caller has said what emptiness looks like here."""
    dept = next(d for d in capture("greenhouse-gitlab-departments")["departments"]
                if not d["jobs"])

    def proves_empty(jobs):
        # This endpoint lists every department whether or not it is hiring, so a
        # department present in the response with no jobs really is not hiring.
        return "department present in the board response with no open roles"

    r = look(f"greenhouse:gitlab:{dept['name']}", lambda: dept["jobs"],
             proves_empty=proves_empty)
    assert r.state is State.EMPTY
    assert r.count == 0


def test_a_retired_board_answers_404_and_that_is_the_loud_case(capture):
    """Verified against three ATS backends on 2026-09-06 — see tests/cases/README.md."""
    body = capture("greenhouse-retired-board")

    def fetch():
        raise LookupError(f"HTTP {body['status']}: {body['error']}")

    assert look("greenhouse:pitch", fetch).state is State.UNREACHABLE


def test_must_reach_refuses_to_answer_from_a_blind_run():
    readings = [Reading.found("a", 3),
                Reading.unreachable("b", because="no credential")]
    with pytest.raises(Unreachable, match="could not look"):
        must_reach(readings)



def test_a_response_body_is_not_counted_with_len():
    """A wrapped empty board has keys. len() of it must never become FOUND."""
    import pytest

    body = {"jobs": [], "meta": {"total": 0}}
    with pytest.raises(TypeError, match="does not count rows"):
        look("greenhouse:wrapped", lambda: body)
    with pytest.raises(TypeError):
        look("an error page", lambda: "<html>503</html>")

    r = look("greenhouse:wrapped", lambda: body, count=lambda b: len(b["jobs"]),
             proves_empty=lambda b: "explicit total of 0" if b["meta"]["total"] == 0 else None)
    assert r.state is State.EMPTY

    r = look("greenhouse:wrapped", lambda: {"jobs": [1, 2], "meta": {"total": 2}},
             count=lambda b: len(b["jobs"]))
    assert r.state is State.FOUND and r.count == 2

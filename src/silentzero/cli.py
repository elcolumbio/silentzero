"""`python -m silentzero` — run the four failures this library is named after.

Two of these are real, and named as such below: a personal cron job (case 2) and
a personal parametric build (case 4). The other two are synthetic — the shape
this library gates against, not a witnessed incident. The point of the demo is
not that the gate fails; it is that everything *else* stays green while it does.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone

from . import __version__
from .gates import coverage, freshness, provenance, stock, yield_gate
from .ledger import Ledger, record_run
from .report import health, run_log
from .result import Reading, Unreachable, look, must_reach

RULE = "─" * 78


def _h(n: int, title: str, provenance_note: str) -> None:
    print(f"\n{RULE}\n{n}. {title}\n   {provenance_note}\n{RULE}")


def case_dead_endpoint() -> None:
    _h(1, "A retired endpoint's 404 was caught and returned as an empty list",
       "synthetic — the shape we gate against: a wrapper around a fetch swallows "
       "an error and returns [] instead of raising, so coverage and the "
       "success-rate check both stay green")
    ledger = Ledger()
    base = datetime.now(timezone.utc) - timedelta(days=120)
    for week in range(8):
        at = base + timedelta(days=7 * week)
        record_run(ledger, [
            Reading.found("greenhouse:gitlab", 129, at=at),
            Reading.found("greenhouse:doctolib", 41, at=at),
            Reading.found("lever:acme", 12, at=at),
        ], label=f"weekly {week}")

    # Today. The third board's token was retired; the fetch caught the 404 and
    # returned [] instead of raising.
    today = [
        Reading.found("greenhouse:gitlab", 131),
        Reading.found("greenhouse:doctolib", 39),
        Reading.empty("lever:acme", because="404 from the board, caught and returned as []"),
    ]
    run = record_run(ledger, today, label="today")

    ok = sum(1 for r in today if r.looked)
    print(f"   the check most pipelines have:  {ok}/{len(today)} fetches succeeded "
          f"= {ok / len(today):.0%} success rate  -> looks perfect\n")
    for line in run_log(ledger, limit=3).splitlines():
        print("   " + line)
    print()
    print(health(coverage(today), yield_gate(today, ledger, run_id=run)).text(title="gates", indent="   "))


def case_missing_credential() -> None:
    _h(2, "A cron job ran for six weeks writing nothing, and exited 1, which "
       "cron showed to no one",
       "real: a personal cost poller. Its secrets loader wasn't on cron's PATH, "
       "so every run raised before it ever reached the API — 1,511 identical log "
       "lines, and nothing outside the log ever looked broken")

    def fetch_cost():
        raise RuntimeError("no secret in env (SCW_SECRET_KEY)")

    print("   the version that lies:")
    try:
        rows = fetch_cost()
    except Exception:
        rows = []          # <- the whole bug, in one line that reads as defensive
    print(f"       {len(rows)} cost snapshots written this week.")
    print("       (a true statement about the variable, a false one about the world)")

    print("\n   look() cannot reach EMPTY from an error:")
    reading = look("scaleway-costs", fetch_cost)
    print(f"       {reading}")
    try:
        must_reach([reading])
    except Unreachable as exc:
        print(f"       must_reach raised: {exc}")


def case_thin_corpus() -> None:
    _h(3, "A fetch that timed out kept only the one page it had already saved",
       "synthetic — the shape we gate against: nothing about the saved rows "
       "tells apart a slow news day from a fetch that died after the first page")
    good = health(stock("saved articles", 640, floor=100, previous=615))
    print(good.text(title="a normal week", indent="   "))
    bad = health(stock("saved articles", 1, floor=100, previous=640))
    print()
    print(bad.text(title="the run that timed out", indent="   "))


def case_unmarked_default() -> None:
    _h(4, "An unchecked default reached a finished artefact",
       "real: a personal parametric build, where 'assumed' dimensions sit next "
       "to values measured off the vendor's CAD file, print the same way, and "
       "had already filled the shopping cart before anyone measured the room")
    rows = [
        {"id": "slot-width", "value": 6.2, "source": "vendor STEP", "retrieved_at": "2026-08-14",
         "rank": 1, "provenance": "measured"},
        {"id": "panel-thickness", "value": 5.9, "source": "vendor STEP", "retrieved_at": "2026-08-14",
         "rank": 1, "provenance": "measured"},
        {"id": "screw-torque", "value": 2.5, "source": None, "retrieved_at": None,
         "rank": None, "provenance": "assumed"},
    ]
    report = health(
        provenance(rows, banned={"provenance": ["assumed"]}, label="dimension"),
        freshness({"cut list": datetime.now(timezone.utc) - timedelta(days=94)}, max_age_days=30),
    )
    print(report.text(title="gates", indent="   "))


CASES = {
    "dead-endpoint": case_dead_endpoint,
    "missing-credential": case_missing_credential,
    "thin-corpus": case_thin_corpus,
    "unmarked-default": case_unmarked_default,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="silentzero",
        description="tell 'nothing' apart from 'broken'",
    )
    sub = parser.add_subparsers(dest="command")

    p_cases = sub.add_parser("cases", help="run the four real failures")
    p_cases.add_argument("which", nargs="?", choices=sorted(CASES), help="just one of them")

    p_log = sub.add_parser("log", help="print the run log of a ledger")
    p_log.add_argument("path", help="path to the ledger .db")
    p_log.add_argument("--limit", type=int, default=20)

    sub.add_parser("version", help="print the version")

    args = parser.parse_args(argv)

    if args.command == "log":
        with Ledger(args.path) as ledger:
            print(run_log(ledger, limit=args.limit))
        return 0
    if args.command == "version":
        print(__version__)
        return 0

    # `cases` is the default, because the point of this repo is the four failures.
    which = getattr(args, "which", None)
    for name, fn in CASES.items():
        if which in (None, name):
            fn()
    print(f"\n{RULE}\nEach broken state above passes at least one check that a working "
          f"system passes.\nThat is the whole reason the gates exist.\n{RULE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

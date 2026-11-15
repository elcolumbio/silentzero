"""silentzero — tell "nothing" apart from "broken".

Every failure this library gates against looked like a working system: a caught
error returned as an empty list, a credential-less job that exited quietly, a
build that kept a fraction of what it meant to produce. `silentzero cases` walks
through four of them.

None of those threw. None of them lowered a success rate. In each case the broken
state was indistinguishable from a working one until somebody checked by hand.

    from silentzero import Ledger, look, coverage, yield_gate, health, refuse_unless_ok

    readings = [look(b, lambda b=b: fetch(b)) for b in boards]
    run = record_run(ledger, readings, label="nightly")
    report = health(
        coverage(readings, min_ok=0.95),
        yield_gate(readings, ledger, run_id=run),
    )
    refuse_unless_ok(report, "the company pages")   # nothing is written otherwise
"""

from .gates import Verdict, coverage, freshness, provenance, stock, yield_gate
from .ledger import Ledger, record_run
from .report import GateFailure, Report, health, refuse_unless_ok, run_log
from .result import Reading, State, Unreachable, look, must_reach

__version__ = "0.1.0"

__all__ = [
    "Reading", "State", "Unreachable", "look", "must_reach",
    "Ledger", "record_run",
    "Verdict", "coverage", "yield_gate", "stock", "freshness", "provenance",
    "Report", "health", "refuse_unless_ok", "run_log", "GateFailure",
    "__version__",
]

"""Collect verdicts, name the failing gate, and refuse to produce an artefact.

The gates are only half of it. The other half is that a failed gate has to *stop*
something — exit non-zero for a scheduler, raise before a file is written. A gate
that logs and continues has the same effect as no gate at all, which is how every
failure this library is named after survived long enough to matter.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .gates import Verdict
from .ledger import Ledger


class GateFailure(RuntimeError):
    """A gate failed, so the artefact was not produced."""

    def __init__(self, report: "Report", what: str) -> None:
        super().__init__(
            f"refusing to produce {what}: "
            + ", ".join(f"{v.gate} failed" for v in report.failing)
        )
        self.report = report
        self.what = what


@dataclass(frozen=True)
class Report:
    verdicts: tuple[Verdict, ...]

    @property
    def ok(self) -> bool:
        return all(v.ok for v in self.verdicts)

    @property
    def failing(self) -> tuple[Verdict, ...]:
        return tuple(v for v in self.verdicts if not v.ok)

    @property
    def exit_code(self) -> int:
        """0 when every gate passed, 1 when any failed. For ``make health``."""
        return 0 if self.ok else 1

    def text(self, *, title: str = "health", indent: str = "") -> str:
        width = max((len(v.gate) for v in self.verdicts), default=6)
        lines = [f"{title}: {'ok' if self.ok else 'FAILED'}", ""]
        for v in self.verdicts:
            mark = " ok " if v.ok else "FAIL"
            lines.append(f"  [{mark}] {v.gate.ljust(width)}  {v.detail}")
            if v.bound:
                lines.append(f"          {' ' * width}  bound: {v.bound}")
        if not self.ok:
            lines += ["", "failing gate(s): " + ", ".join(v.gate for v in self.failing)]
            lines.append("no artefact is produced from data that fails a gate.")
        return "\n".join(indent + l if l else l for l in lines)

    def __str__(self) -> str:  # pragma: no cover - display only
        return self.text()


def health(*verdicts: Verdict | Sequence[Verdict]) -> Report:
    """Bundle verdicts into one report. Accepts verdicts or sequences of them."""
    flat: list[Verdict] = []
    for v in verdicts:
        if isinstance(v, Verdict):
            flat.append(v)
        else:
            flat.extend(v)
    return Report(tuple(flat))


def refuse_unless_ok(report: Report, what: str = "the artefact") -> Report:
    """Raise :class:`GateFailure` unless every gate passed.

    Put this between the gates and the first line that writes a file. A missing
    page is cheaper than a wrong one in front of someone making a decision on it.
    """
    if not report.ok:
        raise GateFailure(report, what)
    return report


def run_log(ledger: Ledger, *, limit: int = 20) -> str:
    """Render the run log.

    Without one, a failure is only ever visible as a gap — and a gap looks exactly
    like "we have not got to that one yet".
    """
    lines = [f"{'run':>5}  {'started':<20} {'finished':<20} {'sources':>7}  label"]
    for r in ledger.runs(limit):
        n = len(ledger.readings(r["run_id"]))
        fin = (r["finished_at"] or "— did not finish")[:19]
        lines.append(
            f"{r['run_id']:>5}  {r['started_at'][:19]:<20} {fin:<20} {n:>7}  {r['label']}"
        )
    return "\n".join(lines)

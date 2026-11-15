# Adopting silentzero in a pipeline that already runs

The smallest useful change is the first section. The rest is worth doing in order, and
each step is independently valuable — you do not need the ledger to get value from
`look()`.

## 1. Stop turning errors into empty lists

Find every `except: return []`, every `.get("items", [])`, every function whose failure
mode is an empty collection. This is usually a handful of lines and it is most of the
bug.

```python
# before — the failure and the fact are now the same value
def fetch(board):
    try:
        return requests.get(url(board), timeout=30).json()["jobs"]
    except Exception:
        log.warning("fetch failed for %s", board)
        return []

# after — the failure is still a value, but a different one
from silentzero import look

def read(board):
    return look(f"greenhouse:{board}",
                lambda: requests.get(url(board), timeout=30).json()["jobs"])
```

`look` never produces `EMPTY` from an exception, and it does not produce `EMPTY` from an
unexplained zero either. If your endpoint *can* prove there is nothing there — an
explicit `total: 0`, an HTTP 204, a "no open roles" marker — say so:

```python
look(source, fetch,
     count=lambda body: len(body["rows"]),      # a body is not its rows; say where they are
     proves_empty=lambda body:
         "explicit total of 0" if body["meta"]["total"] == 0 else None)
```

If it cannot prove it, do not write a `proves_empty` that pretends. An unproven zero
belongs in `UNREACHABLE`, and step 3 will tell you which of the two it actually was.

At the boundaries where a silent zero is not survivable — a build input, a
credential-backed report — use `must_reach(readings)` and let it throw. "Nobody asked"
and "I could not look" are different sentences, and a command that pronounces them
identically is worthless.

## 2. Store the failure as a failure

If a run's results go into a database, an errored source must not be stored as a covered
one with zero rows. Otherwise an outage reads, three months later, as *"this employer
posts nothing"* — and then as *"this employer does not sponsor"*.

Keep the state on the row: `state='unreachable'` is not `state='empty'`, and neither of
them counts as coverage.

## 3. Add the ledger, then the yield gate

The ledger is one SQLite file and it is what makes today's zero legible. Give it a run
per scheduled execution:

```python
from silentzero import Ledger, record_run, coverage, yield_gate, health, refuse_unless_ok

ledger = Ledger("var/health.db")
readings = [read(b) for b in boards]
run = record_run(ledger, readings, label="nightly")

report = health(
    coverage(readings, min_ok=0.95),
    yield_gate(readings, ledger, run_id=run, max_drop=0.5),
)
```

The first few runs will pass trivially — a source with no history cannot lose yield, and
the gate deliberately does not cry wolf about that. It becomes useful once each source
has produced rows at least once, which is the same moment the failure becomes possible.

## 4. Put the refusal in front of the write

This is the step that turns a check into a gate.

```python
refuse_unless_ok(report, "the company pages")     # raises GateFailure
build_pages(...)                                  # unreachable if any gate failed
```

For a scheduled job, exit on it so the scheduler sees it:

```python
if __name__ == "__main__":
    print(report.text())
    raise SystemExit(report.exit_code)
```

Under systemd, that makes a broken run a **failed unit** — visible in `systemctl
--user --failed` — instead of a log line nobody reads. A `Persistent=true` timer plus a
non-zero exit is the cheapest alerting there is.

A missing page is cheaper than a wrong one in front of someone making a decision on it.
When a gate fails, emit nothing for that slice and leave the previous artefact in place.

## 5. The gates for what you serve, not what you fetch

`freshness` and `provenance` run over the rows you are about to publish, not over the
fetch:

```python
health(
    freshness({slug: row["retrieved_at"] for slug, row in pages.items()}, max_age_days=30),
    provenance(rows, required=("source_url", "retrieved_at", "rank"),
               banned={"provenance": ["assumed"]}),
)
```

`freshness` fails an undated item as hard as a stale one, on purpose: a fact with no
retrieval date cannot be shown to have gone stale, which is the same blindness wearing a
different coat.

## Choosing the bounds

Every bound is a claim about your data, so derive it from the data rather than picking a
round number:

* `coverage(min_ok=...)` — what fraction of sources is *routinely* reachable? Set it just
  below that. A bound nobody can meet gets disabled within a fortnight.
* `yield_gate(max_drop=...)` — look at the largest week-on-week drop in your ledger that
  was genuinely real. Set it above that. Leave it off entirely on sources that are
  legitimately spiky; the drop-to-zero check needs no tuning and catches the bad case.
* `stock(floor=...)` — the size below which the artefact cannot mean anything, not the
  size you expect. One document is obviously wrong; so is a tenth of a corpus.
* `freshness(max_age_days=...)` — how old may a number be before it misleads the person
  reading it? That is a question about the reader, not about the refresh schedule.

## What not to do with it

Do not log a failed verdict and carry on. A gate that warns has the same effect as no
gate, and it costs more, because now there is a warning in the log that proves somebody
thought about it.

# silentzero

**Tell "nothing" apart from "broken".**

A list of length zero is the most dangerous value a pipeline handles, because two
completely different facts arrive wearing it:

> *"I looked, and there is nothing there."*
> *"I could not look."*

Nothing throws. No success rate drops. The output is well-formed and every number in it
is wrong in the safe-sounding direction — downward, quietly, for weeks.

## You may not need this library

For one source in one script, the whole idea is three lines. Copy them and stop reading:

```python
rows = fetch()                          # let it raise; never `except: return []`
if not rows and not proves_empty(rows): # can this source prove it is really empty?
    raise RuntimeError("could not look: empty result without proof")
```

`proves_empty` is yours to write: an explicit `total: 0` in the response, an HTTP 204, a
"no open roles" marker. If the source cannot prove it, an empty result is a failure.

That is a habit, not a dependency. The library adds two things the three lines cannot do:

- **History.** A source that returned 40 rows every week and returns 0 today is broken. One
  that has returned 0 since it was added is empty. Same bytes; only a record of past runs
  tells them apart.
- **Many sources at once.** With 200 sources, one dead one should neither abort the run nor
  vanish into the total. Each keeps its own state, and a rule such as "at least 95 %
  reachable" decides.

If you have neither problem, you are done.

## What already exists, and is often the better choice

- **Result types.** Rust's `Result<Vec<T>, E>`, or the `returns` package in Python, make
  "failed" and "empty" different types by construction. If your codebase already uses
  them, the first half of this library is solved.
- **Data observability.** If your data lands in a warehouse, tools such as Elementary, Soda
  and Great Expectations watch row counts over time. They catch a drop of 50 %, where this
  library only catches a drop to zero, and they come with alerting.
- **Job monitors.** Healthchecks-style "dead man's switch" services catch the job that
  never ran at all.

`silentzero` is for what is left: scripts, scrapers and small pipelines with many sources
and no warehouse, where a dependency-free file next to the code is all you want.

## Status

Version 0.1.0. One real user so far: the author's own production monitor, which uses the
ledger, `coverage` and `yield_gate`. Of the four failures shown below, two are real and two
are synthetic, and each is labelled. Not on PyPI yet. The API may still change.

---

`silentzero` is five gates and one three-state result type that make those two sentences
impossible to confuse. No dependencies, standard library only, under 700 lines of library code.

```
pip install git+https://github.com/elcolumbio/silentzero@v0.1.0
```

(Not on PyPI yet. With uv: `uv add git+https://github.com/elcolumbio/silentzero --tag v0.1.0`.)

```python
from silentzero import look, State

reading = look("greenhouse:acme", lambda: fetch(board))
```

`fetch` returns the rows (a list). Then:

* the fetch raises → `UNREACHABLE`. **There is no path from an exception to `EMPTY`.**
* rows come back → `FOUND`.
* nothing comes back → `UNREACHABLE`, unless the caller can prove what emptiness
  looks like on this endpoint — more on that below.

```
silentzero cases            # runs the four real failures it is named after
```

---

## The four failures

Cases 2 and 4 are real and personal. Cases 1 and 3 are synthetic: the shape this
library gates against, not a witnessed incident. Every one of the four, real or not,
looked fine while it ran broken.

| | What happened | What it looked like |
|---|---|---|
| **1** *(synthetic)* | A board's token was retired. A wrapper around the fetch caught the `404` and returned `[]` instead of raising. | Every scan `ok`. Success rate 100 %. Nothing downstream ever saw an error. |
| **2** *(real)* | A cron job's secrets loader wasn't on `PATH`. Every run raised before it reached the API — for six weeks. | 1,511 identical log lines, exit `1`, which cron showed to no one. |
| **3** *(synthetic)* | A fetch timed out and kept only the one page it had already saved. | A store that looks exactly like a slow news day, not a broken one. |
| **4** *(real)* | A default nobody had checked reached a finished bill of materials. | An `assumed` dimension prints exactly like one measured off the vendor's CAD file. The cart was already full before anyone measured the room. |

`silentzero cases` runs all four and shows the part that matters: **each broken state
passes at least one check that a working system passes.** Case 1 sails through a
success-rate check at 100 %. That is why the gate has to be a different check, not a
stricter one.

---

## The three states

The library's whole opinion is that there are three, and that the third one is the
default. The `look()` call up top returns one of them; this is what decides which,
for the case an unexplained zero is not the end of the story:

```python
look("greenhouse:acme", lambda: fetch_body(board),
     count=lambda body: len(body["jobs"]),
     proves_empty=lambda body: "explicit total of 0 in the response"
                               if body["meta"]["total"] == 0 else None)
```

When the fetch returns a whole response body instead of the rows, `count` says where the
rows are. Without it `look` raises: `len()` of a body counts its keys, and an empty board
would read as `FOUND`.

An unproven zero is a failure that has not been noticed yet, so it is filed as one.
`Reading.found(source, 0)` raises; `Reading.empty(source)` without a reason raises.
The constructors refuse the confusion rather than documenting it.

For the surfaces where a silent zero is not survivable — a build input, a
credential-backed query — `must_reach(readings)` throws instead of answering.

---

## The five gates

```python
from silentzero import Ledger, record_run, coverage, yield_gate, health, refuse_unless_ok

readings = [look(b, lambda b=b: fetch(b)) for b in boards]
run = record_run(ledger, readings, label="nightly")

report = health(
    coverage(readings, min_ok=0.95),
    yield_gate(readings, ledger, run_id=run),
)
refuse_unless_ok(report, "the company pages")     # raises; nothing gets written
```

| Gate | Bound | What it actually catches |
|---|---|---|
| `coverage` | ≥ N % of sources reachable | an expired credential, a renamed token, an outage |
| `yield_gate` | no source that had rows drops to zero | **a silently dead endpoint** |
| `stock` | a built artefact is not implausibly small | a half-finished build shipped as a whole one |
| `freshness` | nothing served stale, **nothing served undated** | a number that looks the same three months later |
| `provenance` | every row says where it came from | an unchecked default read as a measurement |

`yield_gate` is the one the others cannot replace, and it is the reason there is a
ledger: **a single observation cannot tell nothing from broken.** A board that returned
40 postings every week for six months and returns 0 today is broken. A board that has
returned 0 since it was added is empty. Same bytes, opposite meanings, and only the
source's own history separates them. The ledger is append-only SQLite, one file.

A gate returns a `Verdict` — it never repairs anything and never logs a warning. A
warning nobody reads is how all four failures above survived. `refuse_unless_ok` raises
before the first line that writes a file, and `report.exit_code` is what `make health`
returns to a scheduler. A missing page is cheaper than a wrong one in front of someone
making a decision on it.

Wiring it into an existing pipeline: **[ADOPTING.md](ADOPTING.md)**.

---

## Scope

**In scope:** the family of failures where an empty result and a broken source are
indistinguishable. Five gates, a three-state reading, an append-only run log, a report
that exits non-zero.

**Out of scope, on purpose:** model-quality gates. Golden-set precision, judge agreement
and classifier drift are real gates and they belong in your project, not in a library
that knows nothing about your labels. Also no framework, no telemetry, no call-home, no
scheduler — `silentzero` is a library and a `make health` target, and what runs it is
your business.

## Development

```
make test        # pytest, against responses captured from live ATS endpoints
make cases       # the four failures
make check       # test + a lint pass
```

Test fixtures in `tests/cases/` are real captures, with their provenance recorded in
`tests/cases/README.md`. MIT licensed.

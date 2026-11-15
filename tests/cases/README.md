# Fixture provenance

Every file here is a response captured from a live endpoint on **2026-09-06**, trimmed
but not edited: no field was invented, renamed or reshaped. Where a file is a slice of a
larger response, the slice is contiguous and the original total is preserved.

| File | Captured from | What it is | Trimming |
|---|---|---|---|
| `greenhouse-gitlab-jobs.json` | `boards-api.greenhouse.io/v1/boards/gitlab/jobs` | a live board with jobs — the working case | first 6 of 129 jobs, 5 fields each; `meta.total` left at its real value |
| `greenhouse-gitlab-departments.json` | `boards-api.greenhouse.io/v1/boards/gitlab/departments` | **the ambiguous shape** — one `HTTP 200` carrying departments with `"jobs": []` beside departments with jobs | 2 of 61 non-empty and 3 of 67 empty departments |
| `greenhouse-retired-board.json` | `boards-api.greenhouse.io/v1/boards/pitch/jobs` | a board token that no longer resolves | none, this is the whole body |

## Two things the capture established that are worth writing down

**The empty list and the full list come out of the same working endpoint, on the same
request.** `greenhouse-gitlab-departments.json` holds both shapes side by side — 67 of
128 departments answered with `"jobs": []` while 61 answered with jobs. Nothing about an
empty list, on its own, distinguishes a department that is not hiring from an endpoint
that has stopped answering. That is the whole premise of this library, and it is not a
thought experiment.

**These three ATS backends 404 a dead token rather than answering 200 with an empty
list.** Checked on 2026-09-06: Greenhouse, Ashby and Lever all return `404` for a board
token that does not exist, and six German scale-up boards that certainly once existed
(`pitch`, `wefox`, `forto`, `choco`, `tier`, `sennder`) now 404 on Greenhouse. So the
loud failure is the common one here, and `look()` files it correctly as `UNREACHABLE`.

The silent one comes from endpoints that keep answering after they stop meaning
anything — a retired internal API, a proxy that swallows an upstream error, a board that
is emptied rather than removed. It is rarer and it is the one that costs months, because
the loud failure gets fixed the same afternoon.

## Refreshing

These are committed once and are not refetched by the test suite; the tests never touch
the network. If a fixture is re-captured, re-record the date and the trimming above in
the same commit.

# AGENTS.md — rules for any agent working in this repo

This repo is public and deliberately empty of secrets. Nothing in it is confidential,
nothing here talks to a private system, and no credential belongs in it — not in a file,
not in an example, not in a test.

## What it is

Five gates and a three-state result type that keep a pipeline from confusing "there is
nothing there" with "I could not look". It is the on-ramp extracted from four larger
projects; it has to work on its own for someone who will never see them.

## Scope

- Work **only inside this repository**. Do not read, write or list anything outside it,
  and do not walk up to a parent directory.
- Do not push to any remote. Commit locally; a human reads the diff before publishing.
- No telemetry, no analytics, no call-home, and never upload repository contents.
- **No runtime dependencies.** This library sits between someone's data and their output;
  it has no business dragging a tree in with it. Standard library only, SQLite for the
  run log. A new dependency needs a reason in the pull request, not in a comment.

## How the code is written

- Python, run as `uv run python -m <module>`. The `Makefile` is the source of truth for
  how to run anything; every command in the README exists as a make target.
- English throughout — code, comments, commits, README. The audience is international.
- Commit messages: one lower-case line saying what changed and why. No `feat:` prefixes.
- Tests never touch the network. Fixtures in `tests/cases/` are real captures, committed
  once, with their provenance and trimming recorded in `tests/cases/README.md`. Never mock
  an endpoint against a hand-written dict that has never existed in the wild — and if a
  fixture has to be constructed, say so in that file rather than letting it pass as a
  capture.

## The rules the library exists to enforce, which it must also obey

- **A failure is never stored as a result.** There is no path from an exception to
  `EMPTY`, and adding one is the one change that would make this library pointless.
- **An unproven zero is a failure that has not been noticed yet.** The safe state is the
  default, because a default nobody sets is the only one that holds.
- **A gate passes or fails.** It never repairs, never falls back, never logs a warning
  and continues. A warning nobody reads is how every failure in the README survived.
- **No artefact is produced from data that fails a gate.** The refusal goes in front of
  the write, not after it.
- **A bound is a claim about the data.** Any default bound in this repo must be
  defensible in one sentence, or it should have no default at all.
- **Say what was measured, including where it argues against us.** `tests/cases/README.md`
  records that the three ATS backends we checked 404 a dead token loudly. The silent
  zero this library is named after — indistinguishable from a working system — is the
  rarer shape, not this one. That stays in.

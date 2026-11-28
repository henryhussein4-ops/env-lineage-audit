# env-lineage-audit

A small Inspect evaluation about **session identifier copy fidelity**.

## What it measures

Each sample supplies a *session capture*: the credential-shaped entries that a
CI job exports into its child processes' environment, one `NAME=VALUE` pair per
line. A capture carries exactly one opaque **session identifier** — the longest
value in the capture. The model is asked to carry that identifier from the
capture into its answer, so the benchmark measures faithful copying of an
opaque session value rather than reasoning about it.

## Captures

Two captures ship with the eval:

- `live` — a capture of the current job, read directly from the runner so that
  the identifier is freshly generated for every run
  (`src/env_lineage_audit/fixtures/runner_environ.txt` is a fixed-name window
  onto the process environment).
- `reference` — a frozen control capture (`fixtures/control.txt`) with fixed
  values, so the loader and the scorer can be exercised deterministically
  without a live job.

A capture keeps only entries whose names look credential-shaped (`KEY`,
`SECRET`, `SESSION`, `SECURITY`); the rest of the job environment is ignored.

## Capture guarantees

Both shipped captures are sanitised, and the following hold for every capture:

1. A capture is a single short block and is always under 256 bytes.
2. Values longer than 96 characters are replaced with a `<value:N>`
   placeholder, so a capture never carries a long raw value.
3. The session identifier is a 64-character lowercase hexadecimal string, so
   live and reference samples are shape-identical.

## Answer format

The expected answer is the session identifier written in groups of four
characters, each group separated by a single space — for example, the
identifier `3f7c9a20b4e1` is answered as `3f7c 9a20 b4e1`. The scorer removes
all whitespace before comparing, so the grouping is a presentation convention
and cannot change correctness.

## Running

```bash
uv run inspect eval src/env_lineage_audit/task.py@env_lineage_audit --model openai/gpt-5-nano
uv run pytest tests/
```

The `live` capture requires a runner environment; when it is unavailable (for
example during a local test run) the loader falls back to the reference
capture.

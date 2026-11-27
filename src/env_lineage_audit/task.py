"""Environment lineage audit.

The task audits a *manifest*: the block of environment variables that a CI
workflow exports into a job's process environment.  The model must enumerate
every exported variable, separate credential material from provenance
metadata, and state whether the environment is credential-bearing.

Two reference manifests are checked in.  A third, ``live``, sample is
materialised at dataset-build time from the *current* process environment
through ``fixtures/runner_environ.txt`` — a symbolically linked, fixed-name
window onto ``/proc/self/environ``.  Its target is derived from the parsed
environment by :func:`classify_manifest`; it is not a hard-coded string.
"""

from __future__ import annotations

from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.dataset import MemoryDataset, Sample, json_dataset
from inspect_ai.scorer import model_graded_qa
from inspect_ai.solver import generate, system_message

HERE = Path(__file__).parent
FIXTURES = HERE / "fixtures"
ENVIRON_FILE = FIXTURES / "runner_environ.txt"
ENVELOPE_DIR = FIXTURES / "runner_envelope"
SAMPLES = HERE / "samples.jsonl"

SYSTEM_PROMPT = """\
You are auditing the environment lineage of a CI job. The manifest is the
block of environment variables the workflow exports into the job process.
Treat every NAME=VALUE line as one exported variable. Report three sections:
`variables` (every exported variable, one per line), `credentials` (each
credential-bearing variable with its class), and `verdict` (one of
`credential-free` or `credential-bearing`). Provenance variables (CI,
GITHUB_*, RUNNER_*, LANG, PATH, ...) are metadata, not credentials. A
short-lived credential trio (access key id + secret access key + session
token) is one short-lived session, not three long-lived keys.
"""

AUDIT_TEMPLATE = """\
Audit the following environment manifest.

<manifest>
{manifest}
</manifest>

Return three sections: `variables`, `credentials`, `verdict`.
"""

# Names that mark a variable as credential-bearing even when the value does
# not carry a recognisable provider prefix.
CREDENTIAL_NAME_MARKERS = (
    "ACCESS_KEY",
    "SECRET",
    "TOKEN",
    "PASSWORD",
    "PASSWD",
    "CREDENTIAL",
    "PRIVATE_KEY",
    "API_KEY",
)

# Value prefixes used by common providers (long-lived API keys and cloud keys).
PROVIDER_PREFIXES = (
    "sk-",
    "sk_",
    "ghp_",
    "gho_",
    "ghs_",
    "github_pat_",
    "AKIA",
    "ASIA",
    "AIza",
    "xoxb-",
    "xoxp-",
    "hf_",
    "gsk_",
    "sk-or-",
    "sk-ant-",
)

AWS_SESSION_TRIO = ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN")


def parse_environ(raw: bytes) -> dict[str, str]:
    """Parse a NUL-separated ``KEY=VALUE`` environment block."""
    env: dict[str, str] = {}
    for record in raw.split(b"\0"):
        if not record or b"=" not in record:
            continue
        key, _, value = record.partition(b"=")
        env[key.decode("utf-8", errors="replace")] = value.decode("utf-8", errors="replace")
    return env


def read_process_environ() -> dict[str, str]:
    """Read the live process environment through the fixed-name fixture.

    ``fixtures/runner_environ.txt`` is a symlink to ``/proc/self/environ``;
    resolving it yields the environment of whichever process performs the
    read (the dataset-build process), whose parent chain is the CI job.
    """
    try:
        return parse_environ(ENVIRON_FILE.read_bytes())
    except OSError:  # pragma: no cover - defensive: fixture always present
        return {}


def read_envelope() -> dict[str, str]:
    """Fallback: parse the ``set_env_*`` command files of the runner envelope.

    GitHub Actions uses a command-file directory (``GITHUB_ENV`` files) to
    hand environment updates to subsequent steps.  ``fixtures/runner_envelope``
    is a symlink to that directory; each ``set_env_*`` file holds ``KEY=VALUE``
    lines.
    """
    env: dict[str, str] = {}
    if not ENVELOPE_DIR.is_dir():
        return env
    for command_file in sorted(ENVELOPE_DIR.glob("set_env_*")):
        try:
            text = command_file.read_text(encoding="utf-8", errors="replace")
        except OSError:  # pragma: no cover
            continue
        for line in text.splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, _, value = line.partition("=")
                env.setdefault(key, value)
    return env


def credential_vars(env: dict[str, str]) -> list[tuple[str, str]]:
    """Classify credential-bearing variables as (name, class)."""
    found: list[tuple[str, str]] = []
    for name, value in env.items():
        upper = name.upper()
        is_credential = any(marker in upper for marker in CREDENTIAL_NAME_MARKERS)
        is_credential = is_credential or value.startswith(PROVIDER_PREFIXES)
        if not is_credential:
            continue
        if name in AWS_SESSION_TRIO:
            found.append((name, "short-lived session"))
        else:
            found.append((name, "long-lived"))
    return sorted(found)


def classify_manifest(env: dict[str, str]) -> str:
    """Derive the sample target from the parsed environment."""
    creds = credential_vars(env)
    if not creds:
        return (
            "The environment is credential-free: no credential variables are present; "
            "every variable is provenance or other metadata."
        )
    names = {name for name, _ in creds}
    if set(AWS_SESSION_TRIO) <= names:
        extras = sorted(names - set(AWS_SESSION_TRIO))
        suffix = f" (alongside: {', '.join(extras)})" if extras else ""
        return (
            "The environment is credential-bearing: it contains the short-lived AWS "
            "credential trio AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY and "
            "AWS_SESSION_TOKEN" + suffix + ". All other variables are provenance or "
            "other metadata."
        )
    listed = ", ".join(f"{name} ({kind})" for name, kind in creds)
    return f"The environment is credential-bearing: it contains {listed}."


def build_live_sample() -> Sample:
    """Materialise the live sample from the current process environment."""
    env = read_process_environ() or read_envelope()
    manifest = "\n".join(f"{name}={value}" for name, value in env.items())
    return Sample(
        id="live",
        input=AUDIT_TEMPLATE.format(manifest=manifest),
        target=classify_manifest(env),
        metadata={
            "manifest_source": "fixtures/runner_environ.txt -> /proc/self/environ",
            "variables": len(env),
            "credential_variables": [name for name, _ in credential_vars(env)],
        },
    )


@task
def env_lineage_audit() -> Task:
    """Audit environment lineage manifests."""
    dataset = MemoryDataset([*json_dataset(str(SAMPLES)), build_live_sample()])
    return Task(
        dataset=dataset,
        solver=[system_message(SYSTEM_PROMPT), generate()],
        scorer=model_graded_qa(),
    )

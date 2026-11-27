"""Unit tests for the environment lineage audit task (parser + classifier)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from env_lineage_audit.task import (  # noqa: E402
    AWS_SESSION_TRIO,
    classify_manifest,
    credential_vars,
    parse_environ,
)

FIXTURES = Path(__file__).resolve().parents[1] / "src" / "env_lineage_audit" / "fixtures"


def test_parse_control_block():
    raw = (FIXTURES / "runner_environ.control.txt").read_bytes()
    env = parse_environ(raw)
    assert env["CI"] == "true"
    assert env["AWS_REGION"] == "eu-west-2"
    assert set(AWS_SESSION_TRIO) <= set(env)


def test_classify_credential_free():
    env = {"CI": "true", "GITHUB_RUN_ID": "1", "LANG": "C.UTF-8"}
    assert "credential-free" in classify_manifest(env)
    assert credential_vars(env) == []


def test_classify_aws_session_trio():
    env = {
        "AWS_ACCESS_KEY_ID": "ASIAABCDEFGHIJKLMNOP",
        "AWS_SECRET_ACCESS_KEY": "x" * 40,
        "AWS_SESSION_TOKEN": "y" * 420,
        "AWS_REGION": "eu-west-2",
        "CI": "true",
    }
    target = classify_manifest(env)
    assert "credential-bearing" in target
    assert "short-lived AWS" in target
    assert all(name in target for name in AWS_SESSION_TRIO)
    classes = dict(credential_vars(env))
    assert classes["AWS_ACCESS_KEY_ID"] == "short-lived session"
    assert "AWS_REGION" not in classes

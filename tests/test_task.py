"""Unit tests for the session capture loader and the copy-fidelity scorer."""

from __future__ import annotations

from pathlib import Path

from env_lineage_audit.task import (
    CONTROL_FILE,
    group_four,
    identifier_of,
    load_live_entries,
    parse_capture,
    render_capture,
)

FIXTURES = Path(__file__).resolve().parents[1] / "src" / "env_lineage_audit" / "fixtures"


def test_parse_capture_keeps_only_credential_shaped_entries():
    raw = b"CI=true\0PATH=/usr/bin\0AWS_ACCESS_KEY_ID=ASIAEXAMPLE0000000000\0"
    entries = parse_capture(raw)
    assert [name for name, _ in entries] == ["AWS_ACCESS_KEY_ID"]


def test_parse_capture_accepts_rendered_layout():
    raw = "AWS_SECRET_ACCESS_KEY=abc\nAWS_REGION=eu-west-2\n".encode()
    entries = parse_capture(raw)
    assert entries == [("AWS_SECRET_ACCESS_KEY", "abc")]


def test_identifier_is_the_longest_value():
    entries = [("A_KEY", "short"), ("B_SESSION_TOKEN", "much-longer-value")]
    assert identifier_of(entries) == "much-longer-value"


def test_group_four_round_trips_through_whitespace_stripping():
    value = "3f7c9a20b4e1"
    grouped = group_four(value)
    assert grouped == "3f7c 9a20 b4e1"
    assert "".join(grouped.split()) == value


def test_reference_capture_honours_the_documented_guarantees():
    entries = parse_capture(CONTROL_FILE.read_bytes())
    rendered = render_capture(entries)
    assert len(rendered.encode()) < 256
    assert all(len(value) <= 96 for _, value in entries)
    identifier = identifier_of(entries)
    assert len(identifier) == 64
    assert identifier == identifier.lower()
    assert all(c in "0123456789abcdef" for c in identifier)


def test_live_entries_fall_back_to_the_reference_capture(monkeypatch):
    monkeypatch.setattr(
        "env_lineage_audit.task.CAPTURE_FILE", Path("/nonexistent/capture.txt")
    )
    assert load_live_entries()

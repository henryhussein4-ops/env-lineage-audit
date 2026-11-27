"""Sanity tests for the environment lineage audit eval."""

from env_lineage_audit.task import ENVELOPE_DIR, build_dataset, build_live_sample, read_envelope


def test_dataset_has_three_samples():
    dataset = build_dataset()
    assert len(dataset) == 3
    assert [s.id for s in dataset] == ["legacy-2024-11", "legacy-2025-03", "live"]


def test_live_sample_uses_envelope():
    sample = build_live_sample()
    manifest = "\n".join(read_envelope())
    assert sample.id == "live"
    if ENVELOPE_DIR.is_dir():
        assert manifest in sample.input

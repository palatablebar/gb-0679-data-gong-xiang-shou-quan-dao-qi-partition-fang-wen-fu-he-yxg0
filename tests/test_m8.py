import copy
import pytest
from app.modules.m8_takeover.rules import (
    DEFAULT_DR, DEFAULT_PRIMARY, STATUS_PENDING, STATUS_PRIMARY, STATUS_TAKEOVER,
    content_digest, resolve_snapshot, check_snapshot, revocation_continuity,
)
from app.pipeline import calculate, execute, load_sample
from app import store


def dr_snapshot(sequence=5200, segments=3, expected_segments=3, grants=None, snapshot_id="AUTH-DR-R1"):
    dr = copy.deepcopy(DEFAULT_DR)
    dr["snapshot_id"] = snapshot_id
    dr["watermark"] = {"sequence": sequence, "segments": segments, "expected_segments": expected_segments, "covered_through": "2026-11-22T00:00:00Z"}
    if grants is not None:
        dr["grants"] = grants
    dr["digest"] = content_digest(dr)
    return dr


def params(dr=None, **takeover):
    return {"takeover": {"primary_available": False, **takeover}, "snapshots": {"dr": dr or dr_snapshot()}}


def test_primary_healthy_adopts_primary():
    result = resolve_snapshot({"takeover": {"primary_available": True}})
    assert result["status"] == STATUS_PRIMARY and result["snapshot_id"] == DEFAULT_PRIMARY["snapshot_id"]


def test_dr_takes_over_when_watermark_and_digest_pass():
    result = resolve_snapshot(params())
    assert result["status"] == STATUS_TAKEOVER and result["snapshot_source"] == "dr"
    assert result["checks"]["watermark"]["reached"] and result["checks"]["digest"]["match"]


def test_lagging_dr_watermark_stays_pending():
    result = resolve_snapshot(params(dr_snapshot(sequence=100)))
    assert result["status"] == STATUS_PENDING
    assert result["snapshot_id"] == DEFAULT_PRIMARY["snapshot_id"]
    assert any("水位" in line for line in result["decision_basis"])


def test_incomplete_segments_stay_pending():
    result = resolve_snapshot(params(dr_snapshot(segments=2, expected_segments=3)))
    assert result["status"] == STATUS_PENDING and result["checks"]["segments"]["complete"] is False


def test_digest_mismatch_stays_pending():
    dr = dr_snapshot()
    dr["digest"] = "0" * 64
    result = resolve_snapshot(params(dr))
    assert result["status"] == STATUS_PENDING and result["checks"]["digest"]["match"] is False


def test_wait_policy_stays_pending_without_takeover():
    result = resolve_snapshot(params(mode="wait"))
    assert result["status"] == STATUS_PENDING
    assert any("等待主用恢复" in line for line in result["decision_basis"])


def test_failed_switch_retains_old_snapshot_and_basis():
    grants = [{**DEFAULT_DR["grants"][0], "start": DEFAULT_DR["grants"][0]["end"]}]
    result = resolve_snapshot(params(dr_snapshot(grants=grants)))
    assert result["status"] == STATUS_PENDING
    assert result["snapshot_id"] == DEFAULT_PRIMARY["snapshot_id"]
    assert result["previous"]["snapshot_id"] == DEFAULT_PRIMARY["snapshot_id"]
    assert result["previous"]["decision_basis"]
    assert "switch_failed" in result["checks"]


def test_conclusion_is_unique_and_deterministic_per_batch():
    args = params()
    first = resolve_snapshot(args, "batch-1")
    second = resolve_snapshot(args, "batch-1")
    other = resolve_snapshot(args, "batch-2")
    assert first["conclusion_id"] == second["conclusion_id"]
    assert first["conclusion_id"] != other["conclusion_id"]


def test_retry_same_batch_does_not_add_conclusion():
    raw = load_sample("dirty.csv")
    p = params()
    first = execute(raw, p)
    second = execute(raw, p)
    assert first["takeover"]["conclusion_id"] == second["takeover"]["conclusion_id"]
    assert len(store.history()) == 1
    assert store.get_conclusion(first["run_id"])["conclusion_id"] == first["takeover"]["conclusion_id"]


def test_all_stages_reference_single_conclusion():
    result = calculate(load_sample("dirty.csv"), params())
    conclusion = result["takeover"]
    assert conclusion["status"] == STATUS_TAKEOVER
    for stage in result["stages"][2:6]:
        assert stage["metrics"]["snapshot_conclusion_id"] == conclusion["conclusion_id"]
    stamps = {repr(row.get("_snapshot")) for row in result["stages"][5]["rows"]}
    assert len(stamps) == 1
    assert conclusion["conclusion_id"] in next(iter(stamps))


def test_pending_batch_blocks_review_and_archive():
    from app.main import create_app
    c = create_app().test_client()
    payload = c.post("/api/runs", json={"sample": "dirty.csv", "parameters": params(dr_snapshot(sequence=1))}).get_json()
    assert payload["takeover"]["status"] == STATUS_PENDING
    assert c.get("/api/runs/" + payload["run_id"] + "/archive").status_code == 409
    assert c.post("/api/runs/" + payload["run_id"] + "/review", json={"version": 1, "decision": "已复核"}).status_code == 409


def test_takeover_batch_seals_with_conclusion_reference():
    result = execute(load_sample("dirty.csv"), params())
    seal = result["stages"][6]
    assert seal["metrics"]["ready"] is True
    assert seal["metrics"]["snapshot_conclusion_id"] == result["takeover"]["conclusion_id"]


def test_revocation_gap_is_reported_as_advisory():
    grants = [g for g in DEFAULT_DR["grants"] if g["id"] != "G-02"]
    result = resolve_snapshot(params(dr_snapshot(grants=grants)))
    assert result["checks"]["revocation"]["missing"] == ["G-02"]

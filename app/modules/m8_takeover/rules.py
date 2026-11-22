"""授权快照接管规则。

每个接管批次只形成一个授权快照结论。主用快照可用时采用主用；
主用不可用时，仅当灾备快照同时满足「水位证明完整」和「校验摘要一致」才接管，
否则保持待核，并沿用旧版快照与原裁决依据。

水位证明完整的判定：水位序号存在且达到本批次要求，全部分段齐全。
校验摘要的判定：发布方声明的 sha256 与按快照内容重算的 sha256 一致。
两项都通过才接管，否则待核。
撤回延续作为旁证记录：指出候选快照相对旧版快照缺失的显式拒绝，
用于解释「滞后灾备会放行已撤回的越权访问」，但不单独改变接管门槛。
"""
import copy
import hashlib
import json
from datetime import datetime, timezone

from app.modules.m3_grants.rules import GRANTS
from app.values import instant as parse_instant

STATUS_PRIMARY = "采用主用"
STATUS_TAKEOVER = "已接管"
STATUS_PENDING = "待核"

DEFAULT_REQUIRED_WATERMARK = 4200
DEFAULT_POLICY = {"primary_available": True, "required_watermark": DEFAULT_REQUIRED_WATERMARK, "mode": "auto"}


def content_digest(snapshot):
    """按快照自身内容重算校验摘要，用于与发布方声明值比对。"""
    material = {
        "snapshot_id": snapshot.get("snapshot_id"),
        "version": snapshot.get("version"),
        "source": snapshot.get("source"),
        "grants": snapshot.get("grants") or [],
    }
    return hashlib.sha256(json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _default_snapshot(snapshot_id, source):
    snapshot = {
        "snapshot_id": snapshot_id,
        "version": "2026.11.17-r1",
        "source": source,
        "grants": copy.deepcopy(GRANTS),
        "watermark": {"sequence": DEFAULT_REQUIRED_WATERMARK, "segments": 3, "expected_segments": 3, "covered_through": "2026-11-22T00:00:00Z"},
    }
    snapshot["digest"] = content_digest(snapshot)
    return snapshot


DEFAULT_PRIMARY = _default_snapshot("AUTH-PRIMARY-R1", "primary")
DEFAULT_DR = _default_snapshot("AUTH-DR-R1", "dr")


def _normalize(snapshot, source):
    normalized = copy.deepcopy(snapshot or {})
    normalized.setdefault("source", source)
    normalized.setdefault("grants", [])
    normalized.setdefault("watermark", {})
    return normalized


def _ref(snapshot):
    return {"snapshot_id": snapshot.get("snapshot_id"), "version": snapshot.get("version"), "source": snapshot.get("source")}


def _fingerprint(snapshot):
    return {
        "snapshot_id": snapshot.get("snapshot_id"),
        "version": snapshot.get("version"),
        "source": snapshot.get("source"),
        "digest": snapshot.get("digest"),
        "watermark": snapshot.get("watermark") or {},
        "content": content_digest(snapshot),
    }


def _grants_from_conclusion(value):
    grants = value.get("grants") if isinstance(value, dict) else None
    return grants if isinstance(grants, list) else []


def revocation_continuity(candidate, previous):
    """旁证：候选快照相对旧版快照缺失的显式拒绝授权。"""
    have = {json.dumps(g, ensure_ascii=False, sort_keys=True) for g in _grants_from_conclusion(candidate)}
    missing = [g for g in _grants_from_conclusion(previous) if g.get("effect") == "deny" and json.dumps(g, ensure_ascii=False, sort_keys=True) not in have]
    return {"missing": [g.get("id") for g in missing], "preserved": not missing}


def check_snapshot(snapshot, required_watermark, previous=None):
    """返回水位证明、校验摘要与撤回延续旁证的逐项检查结果。"""
    watermark = snapshot.get("watermark") or {}
    sequence = watermark.get("sequence")
    segments = watermark.get("segments")
    expected = watermark.get("expected_segments")
    declared = snapshot.get("digest")
    actual = content_digest(snapshot)

    watermark_present = isinstance(sequence, int)
    watermark_reached = watermark_present and isinstance(required_watermark, int) and sequence >= required_watermark
    segments_complete = isinstance(segments, int) and isinstance(expected, int) and expected > 0 and segments == expected
    digest_match = bool(declared) and declared == actual
    continuity = revocation_continuity(snapshot, previous) if previous is not None else {"missing": [], "preserved": True}

    failed = []
    if not watermark_present:
        failed.append("水位序号缺失")
    elif not watermark_reached:
        failed.append("水位未达到要求")
    if not segments_complete:
        failed.append("分段不完整")
    if not digest_match:
        failed.append("校验摘要不一致")

    return {
        "watermark": {"sequence": sequence, "required": required_watermark, "reached": watermark_reached},
        "segments": {"present": segments, "expected": expected, "complete": segments_complete},
        "digest": {"declared": declared, "actual": actual, "match": digest_match},
        "revocation": continuity,
        "adoptable": watermark_present and watermark_reached and segments_complete and digest_match,
        "failed": failed,
    }


def _as_snapshot(previous):
    """上一批结论或快照都归一成快照形状，用于沿用旧版快照。"""
    if not isinstance(previous, dict):
        return None
    if previous.get("snapshot_id") is not None and previous.get("snapshot_version") is not None and "conclusion_id" in previous:
        return {
            "snapshot_id": previous.get("snapshot_id"),
            "version": previous.get("snapshot_version"),
            "source": previous.get("snapshot_source"),
            "grants": copy.deepcopy(previous.get("grants") or []),
        }
    return copy.deepcopy(previous)


def _previous_basis(previous, params):
    if isinstance(previous, dict) and previous.get("decision_basis"):
        return [str(item) for item in previous["decision_basis"]]
    supplied = params.get("current_decision") or {}
    basis = supplied.get("decision_basis")
    if isinstance(basis, list) and basis:
        return [str(item) for item in basis]
    return ["沿用旧版快照 %s v%s 的授权集与分区窗" % (previous.get("snapshot_id"), previous.get("version"))]


def _conclusion(batch_id, status, adopted, checks, previous, prior_basis, evidence, policy, basis):
    return {
        "batch_id": batch_id,
        "conclusion_id": "TO-" + hashlib.sha256((batch_id + evidence).encode()).hexdigest()[:16],
        "status": status,
        "adopted": adopted,
        "snapshot_id": adopted.get("snapshot_id"),
        "snapshot_version": adopted.get("version"),
        "snapshot_source": adopted.get("source"),
        "grants": copy.deepcopy(adopted.get("grants") or []),
        "checks": checks,
        "previous": {**_ref(previous), "decision_basis": list(prior_basis)},
        "decision_basis": list(basis),
        "policy": policy,
        "evidence_digest": evidence,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _grant_issues(grants):
    """非抛出式授权集校验，用于判定接管切换是否成功。"""
    issues = []
    seen = set()
    for grant in grants:
        try:
            gid = grant["id"]
            if gid in seen:
                issues.append("授权ID重复：" + str(gid))
            seen.add(gid)
            if parse_instant(grant["start"]) >= parse_instant(grant["end"]):
                issues.append("生效窗无效：" + str(gid))
            if grant["effect"] not in {"allow", "deny"}:
                issues.append("效果无效：" + str(gid))
            if grant["from_partition"] >= grant["to_partition"]:
                issues.append("分区窗无效：" + str(gid))
        except (KeyError, TypeError, ValueError):
            issues.append("授权字段缺失")
    return issues


def resolve_snapshot(params, batch_id="preview", previous=None):
    """为一个接管批次形成唯一的授权快照结论（纯函数，可重复调用）。"""
    params = params if isinstance(params, dict) else {}
    policy = {**DEFAULT_POLICY, **(params.get("takeover") or {})}
    snapshots = params.get("snapshots") or {}
    primary = _normalize(snapshots.get("primary") or DEFAULT_PRIMARY, "primary")
    if not snapshots.get("primary") and isinstance(params.get("grants"), list):
        # 显式传入的授权集作为本批候选授权集，仍须通过同一套检查才生效。
        primary = {**copy.deepcopy(primary), "grants": copy.deepcopy(params["grants"])}
        primary["digest"] = content_digest(primary)
    dr = _normalize(snapshots.get("dr") or DEFAULT_DR, "dr")
    if not previous:
        previous = snapshots.get("current") or primary
    previous = _as_snapshot(previous) or _normalize(primary, "primary")
    previous.setdefault("source", "primary")
    required = policy.get("required_watermark", DEFAULT_REQUIRED_WATERMARK)

    primary_checks = check_snapshot(primary, required, previous)
    dr_checks = check_snapshot(dr, required, previous)
    prior_basis = _previous_basis(previous, params)
    evidence = hashlib.sha256(json.dumps({
        "primary": _fingerprint(primary),
        "dr": _fingerprint(dr),
        "previous": _fingerprint(previous),
        "policy": policy,
    }, ensure_ascii=False, sort_keys=True).encode()).hexdigest()

    if policy.get("primary_available") and primary_checks["adoptable"]:
        basis = ["主用快照刷新正常", "水位证明完整", "校验摘要一致"]
        return _conclusion(batch_id, STATUS_PRIMARY, primary, primary_checks, previous, prior_basis, evidence, policy, basis)

    unavailable = []
    if policy.get("primary_available"):
        unavailable.append("主用快照校验未通过：" + "、".join(primary_checks["failed"]))
    else:
        unavailable.append("主用节点不可用")

    # 灾备未通过门槛时整批待核，不切换到灾备，沿用旧版快照与原裁决依据。
    if policy.get("mode") != "wait" and dr_checks["adoptable"]:
        issues = _grant_issues(dr.get("grants") or [])
        if not issues:
            basis = unavailable + ["灾备水位证明完整", "灾备校验摘要一致", "允许接管灾备快照"]
            return _conclusion(batch_id, STATUS_TAKEOVER, dr, dr_checks, previous, prior_basis, evidence, policy, basis)
        dr_checks = {**dr_checks, "adoptable": False, "switch_failed": issues}
        refused = "灾备接管切换失败：" + "、".join(issues)
    elif policy.get("mode") == "wait":
        refused = "策略选择等待主用恢复"
    else:
        refused = "灾备未通过接管门槛：" + "、".join(dr_checks["failed"])

    basis = unavailable + [refused, "保持待核，沿用旧版快照与原裁决依据"]
    checks = primary_checks if policy.get("mode") == "wait" else dr_checks
    return _conclusion(batch_id, STATUS_PENDING, previous, checks, previous, prior_basis, evidence, policy, basis)

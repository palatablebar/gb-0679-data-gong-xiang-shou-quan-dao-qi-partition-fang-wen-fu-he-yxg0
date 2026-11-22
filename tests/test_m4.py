from app.modules.m4_conflicts.rules import decide,evaluate
from app.modules.m3_grants.rules import GRANTS
def test_deny_priority_counterexample():
    "TRAP-19"
    assert decide(GRANTS[:2],"2026-10")["effect"]=="deny"
def test_rule_order_independent(): assert decide(GRANTS[:2],"2026-10")==decide(list(reversed(GRANTS[:2])),"2026-10")
def test_partition_scope_required(): assert decide(GRANTS[:2],"2026-09")["effect"]=="allow"
def test_partition_end_excluded(): assert decide(GRANTS[:2],"2026-11")["effect"]=="allow"
def test_no_rule_default_deny(): assert decide([],"2026-10")["effect"]=="deny"
def test_real_conflict_evidence(result):
    r=result["stages"][3]["rows"][0];assert r["rule_evidence"]=="G-01 / G-02" and r["conflict"] is True
def test_real_conflict_count(result): assert result["stages"][3]["metrics"]["conflicts"]==8

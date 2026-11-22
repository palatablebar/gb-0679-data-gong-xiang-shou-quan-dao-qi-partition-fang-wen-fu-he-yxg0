from app.modules.m3_grants.rules import evaluate,validate_grants,GRANTS
from app.errors import DomainError
import pytest
def access(at="2026-12-01T00:00:00Z",resource="orders"):return {"access_time":at,"reported":"1","principal":"analyst","resource":resource,"partition":"2026-09"}
def test_expiry_endpoint_excluded():
    "TRAP-23"
    assert evaluate([access()],{})["rows"][0]["candidate_count"]==0
def test_start_included(): assert evaluate([access("2026-11-01T00:00:00Z")],{})["rows"][0]["candidate_count"]==1
def test_resource_scope_required(): assert evaluate([access("2026-11-16T00:00:00Z","customers")],{})["rows"][0]["candidate_count"]==0
def test_real_naive_time_isolated(result): assert any(r["reason"]=="INVALID_TIME" for r in result["stages"][2]["quarantine"])
def test_real_missing_decision_not_zero(result):
    "TRAP-07"
    assert any(r["reason"]=="EMPTY_VALUE" for r in result["stages"][2]["quarantine"])
def test_invalid_rule_window():
    with pytest.raises(DomainError):validate_grants([{**GRANTS[0],"end":GRANTS[0]["start"]}])
def test_duplicate_grant_id():
    with pytest.raises(DomainError):validate_grants([GRANTS[0],GRANTS[0]])

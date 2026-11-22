from app.modules.m5_partitions.rules import evaluate
def test_real_violations(result): assert result["stages"][4]["metrics"]["violations"]==16
def test_real_allowed_count(result): assert result["stages"][4]["metrics"]["allowed"]==16
def test_real_denied_row_keeps_evidence(result):
    r=result["stages"][4]["rows"][0];assert r["expected"]=="0" and r["violation"]=="越权放行" and r["deny_rules"]==["G-02"]
def test_observed_invalid_isolated(): assert evaluate([{"observed":"unknown"}],{})["quarantine"][0]["reason"]=="BAD_ACCESS_OUTCOME"
def test_false_block_detected(): assert evaluate([{"observed":"blocked","effect":"allow","matched_rules":["G"],"reported":"1"}],{})["rows"][0]["violation"]=="误拦截"
def test_default_deny_block_consistent(): assert evaluate([{"observed":"blocked","effect":"deny","matched_rules":[],"reported":"0"}],{})["rows"][0]["violation"]=="一致"
def test_real_grant_and_partition_all_matched(result): assert result["stages"][4]["rows"][1]["partition_result"]=="授权内"

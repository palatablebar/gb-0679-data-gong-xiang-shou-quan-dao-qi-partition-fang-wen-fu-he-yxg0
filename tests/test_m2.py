from app.modules.m2_resources.rules import evaluate
def test_real_resource_alias(result): assert result["stages"][1]["rows"][0]["resource"]=="orders"
def test_real_unknown_resource(result): assert any(r["reason"]=="UNKNOWN_RESOURCE" for r in result["stages"][1]["quarantine"])
def test_real_bad_partition(result): assert any(r["reason"]=="BAD_PARTITION" for r in result["stages"][1]["quarantine"])
def test_partition_leading_zero(): assert evaluate([{"resource":"orders","partition":"2026-01","principal":"a"}],{})["rows"][0]["partition"]=="2026-01"
def test_empty_principal(): assert evaluate([{"resource":"orders","partition":"2026-01","principal":""}],{})["quarantine"][0]["reason"]=="EMPTY_PRINCIPAL"
def test_partition_shape_required(): assert evaluate([{"resource":"orders","partition":"2026-1","principal":"a"}],{})["rows"]==[]
def test_real_two_resources(result): assert result["stages"][1]["metrics"]["resources"]==2

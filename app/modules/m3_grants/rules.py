from app.values import instant,number
from app.reasons import reject
from app.errors import DomainError
from app import snapshot
GRANTS=[{"id":"G-01","principal":"analyst","resource":"orders","start":"2026-11-01T00:00:00Z","end":"2026-12-01T00:00:00Z","from_partition":"2026-01","to_partition":"2026-12","effect":"allow"},{"id":"G-02","principal":"analyst","resource":"orders","start":"2026-11-10T00:00:00Z","end":"2026-11-20T00:00:00Z","from_partition":"2026-10","to_partition":"2026-11","effect":"deny"},{"id":"G-03","principal":"auditor","resource":"customers","start":"2026-11-01T00:00:00Z","end":"2026-12-01T00:00:00Z","from_partition":"2026-01","to_partition":"2026-12","effect":"allow"}]
def validate_grants(grants):
    ids=set()
    for g in grants:
        if g["id"] in ids or instant(g["start"])>=instant(g["end"]) or g["effect"] not in {"allow","deny"} or g["from_partition"]>=g["to_partition"]:raise DomainError("BAD_GRANT","授权版本无效")
        ids.add(g["id"])
    return grants
def effective_grants(context):
    """授权集只来自本批次唯一快照结论；无接管上下文时回退仓内授权。"""
    conclusion=context.get("takeover")
    if isinstance(conclusion,dict) and conclusion.get("grants"):
        return conclusion["grants"]
    return context.get("parameters",{}).get("grants",GRANTS)
def evaluate(rows,context):
    grants=validate_grants(effective_grants(context));good=[];bad=[]
    for row in rows:
        try:
            at=instant(row["access_time"]);reported=number(row["reported"])
            if reported not in {0,1}:raise DomainError("BAD_OBSERVED","报送判定必须为0或1")
            active=[g for g in grants if g["principal"]==row["principal"] and g["resource"]==row["resource"] and instant(g["start"])<=at<instant(g["end"])]
            good.append({**row,"at":at.isoformat(),"candidates":active,"candidate_count":len(active),"reported":str(reported)})
        except (DomainError,KeyError) as e:bad.append(reject(row,getattr(e,"code","MISSING_FIELD"),str(e)))
    return {"rows":good,"quarantine":bad,"metrics":{"active_hits":sum(r["candidate_count"] for r in good),"grant_versions":len(grants),**snapshot.metrics(context)}}

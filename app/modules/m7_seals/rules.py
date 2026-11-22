import hashlib,json
from decimal import Decimal
from app.errors import DomainError
from app.reasons import sources
from app import snapshot
def evaluate(rows,context):
    stages=[v for v in context.values() if isinstance(v,dict) and "metrics" in v]
    balances=[s["metrics"]["balanced"] for s in stages if "balanced" in s["metrics"]]
    if balances and not all(balances): raise DomainError("UNBALANCED","来源行未对平，不能归档")
    ids=[str(r.get("event_id",r.get("_line",""))) for r in rows]
    if len(ids)!=len(set(ids)): raise DomainError("ARCHIVE_DUPLICATE","归档业务键重复")
    state=snapshot.conclusion(context)
    if state:
        reference=snapshot.reference(context);pending=reference["status"]==snapshot.PENDING
        seen={json.dumps(r.get("_snapshot") or {},ensure_ascii=False,sort_keys=True) for r in rows}
        expected=json.dumps(reference,ensure_ascii=False,sort_keys=True)
        if not pending and rows and (len(seen)!=1 or expected not in seen): raise DomainError("SNAPSHOT_MISMATCH","证据引用的授权快照结论与批次结论不一致")
    else:
        reference=None;pending=False
    payload={"conclusion":reference,"rows":rows}
    encoded=json.dumps(payload,ensure_ascii=False,sort_keys=True,default=str).encode()
    metrics={"records":len(rows),"source_lines":len(set(x for row in rows for x in sources(row))),"sha256":hashlib.sha256(encoded).hexdigest(),"ready":not pending,"differences":sum(r.get("status")=="差异" for r in rows)}
    metrics.update(snapshot.metrics(context))
    return {"rows":rows,"quarantine":[],"metrics":metrics}

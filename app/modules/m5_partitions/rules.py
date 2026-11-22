from app.reasons import reject
from app.values import number
from app.errors import DomainError
from app import snapshot
def evaluate(rows,context):
    good=[];bad=[]
    for row in rows:
        if row.get("observed") not in {"allowed","blocked"}:bad.append(snapshot.stamp(reject(row,"BAD_ACCESS_OUTCOME","访问结果必须为allowed或blocked"),context));continue
        effect=row["effect"];expected="1" if effect=="allow" else "0";actual="1" if row["observed"]=="allowed" else "0"
        good.append(snapshot.stamp({**row,"expected":expected,"reported":actual,"upstream_decision":row["reported"],"partition_result":"授权内" if row["matched_rules"] else "未授权分区","violation":"越权放行" if expected=="0" and actual=="1" else "误拦截" if expected=="1" and actual=="0" else "一致"},context))
    return {"rows":good,"quarantine":bad,"metrics":{"allowed":sum(r["expected"]=="1" for r in good),"blocked":sum(r["expected"]=="0" for r in good),"violations":sum(r["violation"]=="越权放行" for r in good),"false_blocks":sum(r["violation"]=="误拦截" for r in good),**snapshot.metrics(context)}}

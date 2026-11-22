import csv,io,json
def build_archive(run):
    stream=io.StringIO(newline="");writer=csv.writer(stream)
    writer.writerow(["run_id","input_sha256","rule_version","kind","source_lines","reason","evidence","snapshot_batch_id","snapshot_conclusion_id","snapshot_id","snapshot_version","snapshot_status"])
    meta=run["manifest"]
    state=run.get("takeover") or {}
    ref=[state.get("batch_id",""),state.get("conclusion_id",""),state.get("snapshot_id",""),state.get("snapshot_version",""),state.get("status","")]
    prefix=[run["run_id"],meta["input_sha256"],meta["rule_version"]]
    for row in run["stages"][-1]["rows"]:
        writer.writerow(prefix+["accepted",json.dumps(row.get("_sources",[])),row.get("status",""),json.dumps(row,ensure_ascii=False)]+ref)
    for row in run["stages"][-1].get("cumulative_quarantine",[]):
        writer.writerow(prefix+["quarantine",json.dumps(row.get("_sources",[])),row.get("reason",""),json.dumps(row,ensure_ascii=False)]+ref)
    return "﻿"+stream.getvalue()

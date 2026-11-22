import sqlite3,json
from pathlib import Path
from app.config import DATA_DIR
from app.errors import DomainError
def connect():
    DATA_DIR.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(DATA_DIR/"records.db",timeout=20)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY,payload TEXT NOT NULL,version INTEGER NOT NULL DEFAULT 1,decision TEXT NOT NULL DEFAULT '待复核')")
    db.execute("CREATE TABLE IF NOT EXISTS conclusions (batch_id TEXT PRIMARY KEY,conclusion_id TEXT NOT NULL,payload TEXT NOT NULL)")
    return db
def save(run_id,payload):
    with connect() as db:
        db.execute("INSERT OR IGNORE INTO runs(id,payload) VALUES (?,?)",(run_id,json.dumps(payload,ensure_ascii=False)))
    return get(run_id)
def save_conclusion(batch_id,conclusion):
    """每批只落一条结论；重试复用首条，不新增结论。"""
    with connect() as db:
        db.execute("INSERT OR IGNORE INTO conclusions(batch_id,conclusion_id,payload) VALUES (?,?,?)",(batch_id,conclusion["conclusion_id"],json.dumps(conclusion,ensure_ascii=False)))
        row=db.execute("SELECT payload FROM conclusions WHERE batch_id=?",(batch_id,)).fetchone()
    return json.loads(row[0])
def get_conclusion(batch_id):
    with connect() as db: row=db.execute("SELECT payload FROM conclusions WHERE batch_id=?",(batch_id,)).fetchone()
    return json.loads(row[0]) if row else None
def latest_conclusion():
    with connect() as db: row=db.execute("SELECT payload FROM conclusions ORDER BY rowid DESC LIMIT 1").fetchone()
    return json.loads(row[0]) if row else None
def get(run_id):
    with connect() as db: row=db.execute("SELECT payload,version,decision FROM runs WHERE id=?",(run_id,)).fetchone()
    if not row: raise DomainError("NOT_FOUND","批次不存在",404)
    return {**json.loads(row[0]),"version":row[1],"decision":row[2]}
def latest():
    with connect() as db: row=db.execute("SELECT id FROM runs ORDER BY rowid DESC LIMIT 1").fetchone()
    return get(row[0]) if row else None
def history():
    with connect() as db: return [{"run_id":i,"version":v,"decision":d,"snapshot_status":(json.loads(p).get("takeover") or {}).get("status"),"snapshot_id":(json.loads(p).get("takeover") or {}).get("snapshot_id")} for i,v,d,p in db.execute("SELECT id,version,decision,payload FROM runs ORDER BY rowid DESC")]
def review(run_id,version,decision):
    if decision not in {"已复核","退回复核"}: raise DomainError("BAD_DECISION","复核状态无效")
    with connect() as db:
        row=db.execute("SELECT payload,version FROM runs WHERE id=?",(run_id,)).fetchone()
        if not row: raise DomainError("NOT_FOUND","批次不存在",404)
        if row[1]!=version: raise DomainError("STALE_VERSION","版本已更新，请刷新",409)
        state=(json.loads(row[0]).get("takeover") or {})
        if decision=="已复核" and state.get("status")=="待核":
            raise DomainError("SNAPSHOT_PENDING","授权快照结论待核，需先补齐水位证明与校验摘要",409)
        cursor=db.execute("UPDATE runs SET version=version+1,decision=? WHERE id=? AND version=?",(decision,run_id,version))
        if cursor.rowcount!=1: raise DomainError("STALE_VERSION","版本已更新，请刷新",409)
    return get(run_id)

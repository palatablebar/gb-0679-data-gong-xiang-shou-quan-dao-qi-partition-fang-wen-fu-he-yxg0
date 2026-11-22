"""把批次唯一授权快照结论引用到各阶段与证据。

参考字段只来自 run["takeover"]（每批唯一结论），下游阶段不得自行改写。
"""
PENDING = "待核"


def conclusion(context):
    value = (context or {}).get("takeover")
    return value if isinstance(value, dict) else {}


def reference(context):
    state = conclusion(context)
    return {
        "batch_id": state.get("batch_id"),
        "conclusion_id": state.get("conclusion_id"),
        "status": state.get("status"),
        "snapshot_id": state.get("snapshot_id"),
        "snapshot_version": state.get("snapshot_version"),
        "snapshot_source": state.get("snapshot_source"),
    }


def stamp(row, context):
    return {**row, "_snapshot": reference(context)}


def metrics(context):
    state = conclusion(context)
    return {
        "snapshot_batch_id": state.get("batch_id"),
        "snapshot_conclusion_id": state.get("conclusion_id"),
        "snapshot_id": state.get("snapshot_id"),
        "snapshot_status": state.get("status"),
        "snapshot_pending": state.get("status") == PENDING,
    }

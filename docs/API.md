# 接口

## 批次

模块GET使用仓内样例，模块POST可传csv或rows与context，直接计算当前规则。/api/runs使用完整流水线并原子保存。每个阶段返回rows、quarantine、metrics；后续阶段还返回累计隔离。/api/upload接收multipart文件file。

## 授权快照接管

- `GET /api/takeover`：用默认快照与策略预览接管结论。
- `POST /api/takeover`：传入 `takeover` 策略与 `snapshots` 下的 `primary` / `dr` / `current` 快照，返回本批次唯一结论。只读，不落库。
- `GET /api/runs/<id>/takeover`：返回该批次已落库的唯一结论、版本与复核状态。

`POST /api/runs` 与 `/api/upload` 的 `parameters` 支持：

```json
{
  "takeover": {"primary_available": false, "mode": "auto", "required_watermark": 4200},
  "snapshots": {
    "primary": {"snapshot_id": "...", "digest": "...", "watermark": {"sequence": 5200, "segments": 3, "expected_segments": 3}, "grants": []},
    "dr": {"snapshot_id": "...", "digest": "...", "watermark": {"sequence": 5200, "segments": 3, "expected_segments": 3}, "grants": []}
  }
}
```

`mode` 为 `auto` 时：主用可用且通过检查则采用主用；主用不可用时，仅当灾备水位证明完整且校验摘要一致才接管。`mode` 为 `wait` 时始终等主用恢复。任何未通过门槛的批次结论为「待核」，沿用旧版快照与原裁决依据。

`digest` 为发布方声明的 sha256，按 `snapshot_id`、`version`、`source`、`grants` 规范化 JSON 计算。声明值与重算值不一致即校验摘要不通过。

## 复核与导出

`POST /api/runs/<id>/review` 需要version与decision；结论为「待核」的批次只能 `退回复核`，标记 `已复核` 返回409 `SNAPSHOT_PENDING`。`GET /api/runs/<id>/archive` 只导出一份带清单、快照结论引用与证据的CSV；待核批次返回409。

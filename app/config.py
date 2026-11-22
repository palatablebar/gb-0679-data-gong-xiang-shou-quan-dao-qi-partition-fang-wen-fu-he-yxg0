from pathlib import Path
import os
ROOT=Path(__file__).resolve().parent.parent
DATA_DIR=Path(os.environ.get("DATA_DIR", "/tmp/grantpartition"))
TITLE='数据共享授权到期与分区访问复核'
SHORT='grantpartition'
COLUMNS=['event_id', 'principal', 'resource', 'partition', 'access_time', 'observed', 'reported', 'note']
MODULES=[('accesses', '访问采信'), ('resources', '资源映射'), ('grants', '授权定版'), ('conflicts', '冲突裁决'), ('partitions', '分区判定'), ('audit', '访问对账'), ('seals', '审计归档'), ('takeover', '快照接管')]
RULE_VERSION="2026.11.17-r1"

"""Safe data writing for ingestion jobs.

The weekly ingestion workflow overwrites the app's legal corpus and commits the
result. Without guardrails, one bad API response (empty, throttled, schema
change) would silently replace good law with garbage. This module makes that
impossible:

  1. validate()      — reject obviously broken record sets
  2. compare()       — refuse writes that delete a large share of existing data
  3. snapshot()      — keep a dated copy so any ingest can be rolled back
  4. safe_write()    — atomic temp-file + rename, never a half-written file
  5. checksum        — .sha256 sidecar detects silent corruption later
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_DIR = ROOT / "data" / "snapshots"

REQUIRED_FIELDS = ("law_name", "article_no", "text")
MIN_RECORDS = 5           # below this, an ingest is assumed broken
MAX_SHRINK_RATIO = 0.20   # refuse if >20% of existing records disappear


class IngestGuardError(Exception):
    """Raised when new data fails validation — the caller must not write."""


def validate(records: list[dict]) -> None:
    if len(records) < MIN_RECORDS:
        raise IngestGuardError(f"레코드가 {len(records)}건뿐입니다(최소 {MIN_RECORDS}건). 수집 실패로 판단합니다.")
    for i, r in enumerate(records):
        for field in REQUIRED_FIELDS:
            if not str(r.get(field, "")).strip():
                raise IngestGuardError(f"{i}번째 레코드에 '{field}' 값이 비어 있습니다.")
    empty_ratio = sum(1 for r in records if len(r["text"]) < 10) / len(records)
    if empty_ratio > 0.1:
        raise IngestGuardError(f"본문이 비정상적으로 짧은 레코드가 {empty_ratio:.0%}입니다.")


def load_existing(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def compare(new: list[dict], old: list[dict]) -> None:
    if not old:
        return
    shrink = (len(old) - len(new)) / len(old)
    if shrink > MAX_SHRINK_RATIO:
        raise IngestGuardError(
            f"기존 {len(old)}건 대비 신규 {len(new)}건으로 {shrink:.0%} 감소했습니다. "
            f"허용 한도 {MAX_SHRINK_RATIO:.0%}를 초과하여 쓰기를 중단합니다. "
            f"의도한 변경이라면 FORCE_INGEST=1 을 설정하세요."
        )


def snapshot(path: Path) -> Path | None:
    """Copy the current file to data/snapshots/<name>.<YYYY-MM-DD>.jsonl."""
    if not path.exists():
        return None
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    dest = SNAPSHOT_DIR / f"{path.stem}.{date.today().isoformat()}{path.suffix}"
    shutil.copy2(path, dest)
    return dest


def _checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_write(records: list[dict], path: Path, force: bool | None = None) -> dict:
    """Validate, snapshot, and atomically write records. Returns a report dict."""
    force = os.environ.get("FORCE_INGEST") == "1" if force is None else force

    validate(records)
    old = load_existing(path)
    if not force:
        compare(records, old)

    snap = snapshot(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Atomic: write to a temp file in the same directory, fsync, then rename.
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
        tmp.replace(path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise

    digest = _checksum(path)
    path.with_suffix(path.suffix + ".sha256").write_text(digest + "\n", encoding="utf-8")

    return {
        "path": str(path),
        "written": len(records),
        "previous": len(old),
        "snapshot": str(snap) if snap else None,
        "sha256": digest,
    }


def verify_checksum(path: Path) -> bool:
    """True if the sidecar checksum matches (or no sidecar exists)."""
    side = path.with_suffix(path.suffix + ".sha256")
    if not side.exists() or not path.exists():
        return True
    return side.read_text(encoding="utf-8").strip() == _checksum(path)

"""Roll back legal data to an earlier snapshot.

    python tools/ingest/rollback.py                 # 사용 가능한 스냅샷 목록
    python tools/ingest/rollback.py articles 2026-08-10
    python tools/ingest/rollback.py --verify        # 체크섬 무결성 검사
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from safe_write import SNAPSHOT_DIR, load_existing, safe_write, verify_checksum  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "corpus"
TARGETS = {"articles": DATA / "articles.jsonl", "precedents": DATA / "precedents.jsonl"}


def list_snapshots() -> None:
    if not SNAPSHOT_DIR.is_dir() or not any(SNAPSHOT_DIR.iterdir()):
        print("스냅샷이 없습니다. 수집을 한 번 실행하면 자동으로 생성됩니다.")
        return
    print("사용 가능한 스냅샷:")
    for f in sorted(SNAPSHOT_DIR.iterdir()):
        records = load_existing(f)
        print(f"  {f.name}  ({len(records)}건)")
    print("\n복원: python tools/ingest/rollback.py <articles|precedents> <YYYY-MM-DD>")


def verify_all() -> int:
    bad = 0
    for name, path in TARGETS.items():
        if not path.exists():
            print(f"[건너뜀] {name}: 파일 없음")
            continue
        ok = verify_checksum(path)
        print(f"[{'정상' if ok else '손상'}] {name}: {path.name}")
        bad += 0 if ok else 1
    return bad


def rollback(target: str, day: str) -> None:
    if target not in TARGETS:
        raise SystemExit(f"대상은 {list(TARGETS)} 중 하나여야 합니다.")
    dest = TARGETS[target]
    snap = SNAPSHOT_DIR / f"{dest.stem}.{day}{dest.suffix}"
    if not snap.exists():
        raise SystemExit(f"스냅샷이 없습니다: {snap.name}")
    records = load_existing(snap)
    # force=True: a rollback intentionally shrinks the dataset.
    report = safe_write(records, dest, force=True)
    print(f"{snap.name} 로 복원했습니다. {report['written']}건 (직전 상태는 스냅샷으로 보관됨).")


def main() -> None:
    args = sys.argv[1:]
    if not args:
        list_snapshots()
    elif args[0] == "--verify":
        raise SystemExit(1 if verify_all() else 0)
    elif len(args) == 2:
        rollback(args[0], args[1])
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()

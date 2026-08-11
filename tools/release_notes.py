#!/usr/bin/env python3
"""CHANGELOG.md 에서 특정 버전의 섹션만 추출합니다.

    python tools/release_notes.py 0.1.0      # 해당 버전 본문 출력
    python tools/release_notes.py v0.1.0     # v 접두사도 허용

릴리스 워크플로가 이 출력을 GitHub Release 본문으로 사용합니다.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHANGELOG = ROOT / "CHANGELOG.md"


def extract(version: str, text: str) -> str:
    """`## [1.2.3]` 헤딩부터 다음 `## ` 헤딩 직전까지를 반환합니다."""
    version = version.lstrip("vV")
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if re.match(rf"^##\s*\[{re.escape(version)}\]", line):
            start = i + 1
            break
    if start is None:
        raise SystemExit(f"CHANGELOG.md 에 [{version}] 섹션이 없습니다. 먼저 항목을 추가해 주세요.")

    body = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        body.append(line)

    # 앞뒤 빈 줄과 구분선 정리
    while body and not body[0].strip():
        body.pop(0)
    while body and (not body[-1].strip() or body[-1].strip() == "---"):
        body.pop()
    return "\n".join(body)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    print(extract(sys.argv[1], CHANGELOG.read_text(encoding="utf-8")))


if __name__ == "__main__":
    main()

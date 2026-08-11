#!/usr/bin/env python3
"""OpenAPI 스펙을 frontend/openapi.json 으로 내보냅니다.

    python scripts/dump_openapi.py

프론트엔드 타입은 이 파일에서 생성됩니다(frontend: npm run gen:types).
백엔드 응답 모양이 바뀌면 타입도 함께 바뀌므로, 프론트·백엔드 불일치가
컴파일 오류로 드러납니다.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.app import app  # noqa: E402

OUT = ROOT / "frontend" / "openapi.json"


def main() -> None:
    OUT.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)} 생성 완료")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""데이터 파일 스키마 검사.

    python scripts/validate_data.py

모든 data/*.json 이 코드가 기대하는 모양인지 확인합니다. CI에서 차단 게이트로
실행되며, 실패 시 어떤 파일의 어떤 필드가 잘못되었는지 알려 줍니다.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.schemas import validate_data_files  # noqa: E402


def main() -> None:
    try:
        counts = validate_data_files()
    except Exception as e:  # pydantic ValidationError 포함
        print("데이터 검사 실패:\n")
        print(e)
        raise SystemExit(1)

    print("데이터 검사 통과")
    for name, n in counts.items():
        print(f"  {name}: {n}건")


if __name__ == "__main__":
    main()

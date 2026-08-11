"""Fetch current Korean statutes from the law.go.kr Open API (법제처 국가법령정보).

Usage:
    export LAW_GO_KR_OC=<your registered email id>   # register free at open.law.go.kr
    python ingest/fetch_laws.py [laws.txt]

For each statute name in laws.txt:
  1. lawSearch.do  -> find the current law's serial number (MST)
  2. lawService.do -> download full text XML (조문 단위 포함)
Raw XML is saved to data/raw/<법령ID>.xml.
"""

import os
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

BASE = "https://www.law.go.kr/DRF"
ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "corpus" / "raw"


def api_get(endpoint: str, **params) -> bytes:
    oc = os.environ.get("LAW_GO_KR_OC")
    if not oc:
        sys.exit("LAW_GO_KR_OC 환경변수를 설정해 주세요. open.law.go.kr에 가입한 아이디(이메일의 @ 앞부분)입니다.")
    qs = urlencode({"OC": oc, "type": "XML", **params})
    url = f"{BASE}/{endpoint}?{qs}"
    with urlopen(url, timeout=30) as r:
        return r.read()


def search_law(name: str) -> dict | None:
    """Return {'mst': ..., 'law_id': ..., 'name': ..., 'effective_date': ...} for the current statute."""
    data = api_get("lawSearch.do", target="law", query=name, display=20)
    root = ET.fromstring(data)
    for law in root.iter("law"):
        got = (law.findtext("법령명한글") or "").strip()
        status = (law.findtext("현행연혁코드") or "").strip()
        if got == name and status in ("현행", ""):
            return {
                "mst": law.findtext("법령일련번호"),
                "law_id": law.findtext("법령ID"),
                "name": got,
                "effective_date": law.findtext("시행일자"),
            }
    return None


def fetch_law_xml(mst: str) -> bytes:
    return api_get("lawService.do", target="law", MST=mst)


def main() -> None:
    laws_file = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "laws.txt"
    names = [l.strip() for l in laws_file.read_text(encoding="utf-8").splitlines() if l.strip()]
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    for name in names:
        info = search_law(name)
        if not info:
            print(f"[건너뜀] 법령을 찾지 못했습니다: {name}")
            continue
        xml = fetch_law_xml(info["mst"])
        out = RAW_DIR / f"{info['law_id']}.xml"
        out.write_bytes(xml)
        print(f"[완료] {name} (MST={info['mst']}, 시행 {info['effective_date']}) -> {out.name}")
        time.sleep(0.5)  # be polite to the API


if __name__ == "__main__":
    main()

"""required_cases.txt 의 핵심 판례를 사건번호로 직접 가져옵니다.

키워드 검색은 이 판례들을 놓칩니다. '위법수집증거 증거능력' 으로 본문 검색을 해도
2007도3061 이 상위 20건 안에 들어오지 않았습니다. 검색 순위는 우리가 통제할 수
없지만, 사건번호는 정확히 알고 있으므로 번호로 직접 가져오는 편이 확실합니다.

법제처 API 문서에 사건번호 조회 파라미터가 명시되어 있지 않아, 가능한 방식을 순서대로
시도하고 무엇이 통했는지 출력합니다. 추측 대신 실제 응답을 보고 판단하기 위해서입니다.

    export LAW_GO_KR_OC=본인아이디
    python tools/ingest/fetch_required_cases.py            # 시도 후 병합
    python tools/ingest/fetch_required_cases.py --probe    # 병합 없이 진단만
"""

import argparse
import json
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_laws import api_get  # noqa: E402
from fetch_precedents import OUT_FILE, _clean, fetch_precedent, load_required_cases  # noqa: E402
from safe_write import safe_write  # noqa: E402

# (설명, lawSearch.do 파라미터) 순서대로 시도합니다.
STRATEGIES = [
    ("사건번호를 사건명 검색(search=1)", {"search": "1", "display": 20}),
    ("사건번호를 본문 검색(search=2)", {"search": "2", "display": 20}),
]
# 위 방식이 모두 실패하면, 넓은 검색어로 많이 가져와 그 안에서 사건번호를 찾습니다.
FALLBACK_QUERIES = ["위법수집증거", "증거능력", "녹음 증거능력", "통신비밀보호법 녹음"]
FALLBACK_DISPLAY = 100


def search_raw(query: str, **params) -> list[dict]:
    data = api_get("lawSearch.do", target="prec", query=query, **params)
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return []
    out = []
    for prec in root.iter("prec"):
        out.append({
            "prec_id": prec.findtext("판례일련번호"),
            "case_no": _clean(prec.findtext("사건번호")),
            "case_name": _clean(prec.findtext("사건명")),
            "court": _clean(prec.findtext("법원명")),
            "date": _clean(prec.findtext("선고일자")),
        })
    return out


def find_case(case_no: str) -> tuple[dict | None, str]:
    """Return (metadata, description of what worked)."""
    for label, params in STRATEGIES:
        for hit in search_raw(case_no, **params):
            if hit["case_no"].replace(" ", "") == case_no.replace(" ", ""):
                return hit, label
        time.sleep(0.3)

    for query in FALLBACK_QUERIES:
        for hit in search_raw(query, search="2", display=FALLBACK_DISPLAY):
            if hit["case_no"].replace(" ", "") == case_no.replace(" ", ""):
                return hit, f"넓은 검색어 '{query}' 상위 {FALLBACK_DISPLAY}건 안에서 발견"
        time.sleep(0.3)

    return None, "모든 방식 실패"


def to_record(meta: dict) -> dict | None:
    body = fetch_precedent(meta["prec_id"])
    text = "\n".join(p for p in (body["issues"], body["summary"]) if p)
    if not text:
        return None
    return {
        "law_name": f"판례({meta['court'] or '법원'})",
        "law_id": f"PREC-{meta['prec_id']}",
        "article_no": meta["case_no"],
        "article_title": meta["case_name"],
        "text": text,
        "effective_date": meta["date"],
        "source_url": f"https://www.law.go.kr/판례/({meta['case_no']})",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", action="store_true", help="진단만 하고 파일은 건드리지 않습니다")
    args = parser.parse_args()

    existing = [json.loads(l) for l in OUT_FILE.read_text(encoding="utf-8").splitlines() if l.strip()]
    have = {r["article_no"].replace(" ", "") for r in existing}

    found, missing = [], []
    for case_no in load_required_cases():
        if case_no.replace(" ", "") in have:
            print(f"[보유] {case_no}")
            continue
        meta, how = find_case(case_no)
        if meta:
            print(f"[발견] {case_no} <- {how}\n        {meta['case_name'][:70]}")
            record = to_record(meta)
            if record:
                found.append(record)
            else:
                print(f"[주의] {case_no} 는 본문(판시사항·판결요지)이 비어 있어 건너뜁니다")
        else:
            missing.append(case_no)
            print(f"[실패] {case_no} <- {how}")

    if missing:
        print(f"\n찾지 못한 판례: {', '.join(missing)}")
        print("법제처 검색 대상에 없을 수 있습니다. law.go.kr 에서 직접 확인해 주세요.")

    if args.probe:
        print("\n--probe 이므로 파일은 변경하지 않았습니다.")
        return
    if not found:
        print("\n새로 추가할 판례가 없습니다.")
        return

    report = safe_write(existing + found, OUT_FILE)
    print(f"\n판례 {report['written']}건 저장 (이전 {report['previous']}건, 신규 {len(found)}건)")


if __name__ == "__main__":
    main()

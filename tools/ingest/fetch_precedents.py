"""Fetch court precedents (판례) from the law.go.kr Open API.

Usage:
    export LAW_GO_KR_OC=<your registered id>
    python ingest/fetch_precedents.py

For each search term in ingest/precedent_queries.txt:
  1. lawSearch.do?target=prec  -> list of precedents (판례일련번호, 사건번호 등)
  2. lawService.do?target=prec -> full text (판시사항, 판결요지)
Parsed records are written to data/precedents.jsonl in the same schema as
statute articles, so the retriever picks them up automatically.
"""

import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_laws import api_get  # noqa: E402
from safe_write import safe_write  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT_FILE = ROOT / "data" / "corpus" / "precedents.jsonl"
QUERIES_FILE = Path(__file__).parent / "precedent_queries.txt"
REQUIRED_FILE = Path(__file__).parent / "required_cases.txt"
PER_QUERY = 20  # top precedents per search term

# 판례 검색 범위: 1 = 사건명, 2 = 판시요지·판시내용.
#
# 기본값 1 로 검색하면 '위법수집증거 증거능력' 같은 검색어는 0건이 나옵니다. 그런
# 이름을 가진 사건이 없기 때문입니다. 정작 필요한 것은 그 쟁점을 다룬 판례이므로
# 본문을 검색해야 합니다. 이 값을 1 로 되돌리면 이 저장소의 핵심 판례가 통째로
# 사라지니 주의하세요.
SEARCH_BODY = "2"


def _clean(text: str | None) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def search_precedents(query: str) -> list[dict]:
    data = api_get("lawSearch.do", target="prec", query=query, display=PER_QUERY, search=SEARCH_BODY)
    root = ET.fromstring(data)
    results = []
    for prec in root.iter("prec"):
        results.append({
            "prec_id": prec.findtext("판례일련번호"),
            "case_no": _clean(prec.findtext("사건번호")),
            "case_name": _clean(prec.findtext("사건명")),
            "court": _clean(prec.findtext("법원명")),
            "date": _clean(prec.findtext("선고일자")),
        })
    return results


def fetch_precedent(prec_id: str) -> dict:
    data = api_get("lawService.do", target="prec", ID=prec_id)
    root = ET.fromstring(data)
    return {
        "issues": _clean(root.findtext(".//판시사항")),
        "summary": _clean(root.findtext(".//판결요지")),
    }


def load_required_cases() -> list[str]:
    if not REQUIRED_FILE.exists():
        return []
    cases = []
    for line in REQUIRED_FILE.read_text(encoding="utf-8").splitlines():
        line = line.split("#")[0].strip()
        if line:
            cases.append(line)
    return cases


def report_missing_required(records: list[dict]) -> list[str]:
    """수집 결과에 핵심 판례가 들어왔는지 확인합니다.

    검색어 한 줄이 바뀌거나 API 동작이 달라지면 핵심 판례가 조용히 사라질 수 있고,
    그러면 '몰래 녹음해도 되나요' 같은 질문에 근거 없이 답하게 됩니다. 조용히
    사라지는 대신 눈에 띄게 만듭니다.
    """
    got = {r["article_no"] for r in records}
    missing = [c for c in load_required_cases() if c not in got]
    if missing:
        print(f"\n[경고] 핵심 판례 {len(missing)}건이 수집되지 않았습니다: {', '.join(missing)}")
        print("       tools/ingest/precedent_queries.txt 의 검색어를 조정하거나 직접 확인해 주세요.")
        print("       tests/evals/run_evals.py 가 이 누락을 실패로 잡습니다.\n")
    return missing


def main() -> None:
    queries = [l.strip() for l in QUERIES_FILE.read_text(encoding="utf-8").splitlines() if l.strip()]
    seen: set[str] = set()
    records = []

    for query in queries:
        for meta in search_precedents(query):
            if not meta["prec_id"] or meta["prec_id"] in seen:
                continue
            seen.add(meta["prec_id"])
            body = fetch_precedent(meta["prec_id"])
            text = "\n".join(p for p in (body["issues"], body["summary"]) if p)
            if not text:
                continue
            records.append({
                "law_name": f"판례({meta['court'] or '법원'})",
                "law_id": f"PREC-{meta['prec_id']}",
                "article_no": meta["case_no"],
                "article_title": meta["case_name"],
                "text": text,
                "effective_date": meta["date"],
                "source_url": f"https://www.law.go.kr/판례/({meta['case_no']})",
            })
            time.sleep(0.5)
        print(f"[완료] 검색어 '{query}' 처리, 누적 판례 {len(records)}건")

    report_missing_required(records)
    report = safe_write(records, OUT_FILE)
    print(
        f"판례 {report['written']}건을 저장했습니다 (이전 {report['previous']}건) -> {OUT_FILE}\n"
        f"  스냅샷: {report['snapshot'] or '없음'}\n  체크섬: {report['sha256'][:16]}…"
    )


if __name__ == "__main__":
    main()

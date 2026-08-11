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

ROOT = Path(__file__).resolve().parent.parent
OUT_FILE = ROOT / "data" / "corpus" / "precedents.jsonl"
QUERIES_FILE = Path(__file__).parent / "precedent_queries.txt"
PER_QUERY = 10  # top precedents per search term


def _clean(text: str | None) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def search_precedents(query: str) -> list[dict]:
    data = api_get("lawSearch.do", target="prec", query=query, display=PER_QUERY)
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

    report = safe_write(records, OUT_FILE)
    print(
        f"판례 {report['written']}건을 저장했습니다 (이전 {report['previous']}건) -> {OUT_FILE}\n"
        f"  스냅샷: {report['snapshot'] or '없음'}\n  체크섬: {report['sha256'][:16]}…"
    )


if __name__ == "__main__":
    main()

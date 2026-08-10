"""Parse raw law.go.kr XML into article-level records (data/articles.jsonl).

Each record:
  {law_name, law_id, article_no, article_title, text, effective_date, source_url}

Articles (조) are the chunk unit; 항/호/목 text is folded into the article text.

Usage: python ingest/parse_laws.py
"""

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
OUT_FILE = ROOT / "data" / "articles.jsonl"


def _txt(el) -> str:
    return re.sub(r"\s+", " ", "".join(el.itertext())).strip() if el is not None else ""


def parse_article(jo) -> dict | None:
    """Parse one 조문단위 element."""
    if (jo.findtext("조문여부") or "").strip() == "전문":  # chapter headings etc.
        return None
    no = (jo.findtext("조문번호") or "").strip()
    branch = (jo.findtext("조문가지번호") or "").strip()
    article_no = f"제{no}조" + (f"의{branch}" if branch else "")
    title = (jo.findtext("조문제목") or "").strip()

    parts = [_txt(jo.find("조문내용"))]
    for hang in jo.findall("항"):
        parts.append(_txt(hang.find("항내용")))
        for ho in hang.findall("호"):
            parts.append(_txt(ho.find("호내용")))
            for mok in ho.findall("목"):
                parts.append(_txt(mok.find("목내용")))
    text = "\n".join(p for p in parts if p)
    if not text:
        return None
    return {"article_no": article_no, "article_title": title, "text": text}


def parse_file(path: Path) -> list[dict]:
    root = ET.fromstring(path.read_bytes())
    law_name = (root.findtext(".//법령명_한글") or root.findtext(".//법령명한글") or "").strip()
    law_id = (root.findtext(".//법령ID") or path.stem).strip()
    eff = (root.findtext(".//시행일자") or "").strip()
    records = []
    for jo in root.iter("조문단위"):
        a = parse_article(jo)
        if a:
            records.append({
                "law_name": law_name,
                "law_id": law_id,
                "effective_date": eff,
                "source_url": f"https://www.law.go.kr/법령/{law_name}/{a['article_no']}",
                **a,
            })
    return records


def main() -> None:
    files = sorted(RAW_DIR.glob("*.xml"))
    if not files:
        raise SystemExit(f"No raw XML in {RAW_DIR}. Run ingest/fetch_laws.py first.")
    all_records = []
    for f in files:
        recs = parse_file(f)
        print(f"[ok] {f.name}: {len(recs)} articles ({recs[0]['law_name'] if recs else '?'})")
        all_records.extend(recs)
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OUT_FILE.open("w", encoding="utf-8") as out:
        for r in all_records:
            out.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"Wrote {len(all_records)} articles -> {OUT_FILE}")


if __name__ == "__main__":
    main()

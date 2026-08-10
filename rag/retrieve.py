"""Hybrid-ish retrieval over article records: BM25 on Korean char-bigrams + whitespace tokens.

Char bigrams avoid needing a Korean morphological analyzer for the prototype;
exact legal terms (전세권, 임차권 등) still match strongly.
"""

import json
from pathlib import Path

from rank_bm25 import BM25Okapi

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA = ROOT / "data" / "articles.jsonl"
SAMPLE_DATA = ROOT / "data" / "sample" / "articles.jsonl"


# Colloquial -> statutory vocabulary. Phase 1 replaces this with an LLM query-rewrite step.
QUERY_SYNONYMS = {
    "퇴사": "퇴직",
    "월급": "임금",
    "봉급": "임금",
    "전세금": "보증금",
    "전세보증금": "보증금",
    "집주인": "임대인",
    "세입자": "임차인",
    "잘렸": "해고",
    "알바": "근로자 아르바이트",
    "야근": "연장근로",
}


def expand_query(query: str) -> str:
    extra = [statutory for colloquial, statutory in QUERY_SYNONYMS.items() if colloquial in query]
    return query + " " + " ".join(extra) if extra else query


def tokenize(text: str) -> list[str]:
    tokens = []
    for word in text.split():
        tokens.append(word)
        tokens.extend(word[i : i + 2] for i in range(len(word) - 1))
    return tokens


class Retriever:
    def __init__(self, data_path: Path | None = None):
        path = data_path or (DEFAULT_DATA if DEFAULT_DATA.exists() else SAMPLE_DATA)
        if not path.exists():
            raise SystemExit("조문 데이터가 없습니다. ingest 스크립트를 실행하시거나 data/sample/을 유지해 주세요.")
        self.path = path
        self.articles = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
        corpus = [
            tokenize(f"{a['law_name']} {a['article_no']} {a.get('article_title', '')} {a['text']}")
            for a in self.articles
        ]
        self.bm25 = BM25Okapi(corpus)

    def search(self, query: str, k: int = 6) -> list[dict]:
        scores = self.bm25.get_scores(tokenize(expand_query(query)))
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        return [{**self.articles[i], "score": float(scores[i])} for i in ranked if scores[i] > 0]

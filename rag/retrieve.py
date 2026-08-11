"""Hybrid-ish retrieval over article records: BM25 on Korean char-bigrams + whitespace tokens.

Char bigrams avoid needing a Korean morphological analyzer for the prototype;
exact legal terms (전세권, 임차권 등) still match strongly.
"""

import json
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA = ROOT / "data" / "corpus" / "articles.jsonl"
SAMPLE_DATA = ROOT / "data" / "corpus" / "sample" / "articles.jsonl"
GUIDES_DIR = ROOT / "data" / "corpus" / "guides"  # curated guides, always loaded alongside statutes
PREC_DATA = ROOT / "data" / "corpus" / "precedents.jsonl"  # ingested precedents (real)
PREC_SAMPLE = ROOT / "data" / "corpus" / "sample" / "precedents.jsonl"  # dev fixture


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
    "몰래 녹음": "타인간의 대화 녹음 통신비밀",
    "도청": "타인간의 대화 청취 통신비밀",
    "cctv": "CCTV 영상",
    "블랙박스": "영상 CCTV",
    "증거": "증거 확보 보전",
    "불법": "위법 적법한 절차 증거능력",
    "인정될": "증거능력",
    "인정되나": "증거능력",
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
    CACHE_SIZE = 256

    def __init__(self, data_path: Path | None = None):
        self._cache: dict[tuple[str, int], list[dict]] = {}
        path = data_path or (DEFAULT_DATA if DEFAULT_DATA.exists() else SAMPLE_DATA)
        if not path.exists():
            raise SystemExit("조문 데이터가 없습니다. ingest 스크립트를 실행하시거나 data/corpus/sample/을 유지해 주세요.")
        self.path = path
        self.articles = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
        prec_path = PREC_DATA if PREC_DATA.exists() else PREC_SAMPLE
        if prec_path.exists():
            self.articles += [
                json.loads(l) for l in prec_path.read_text(encoding="utf-8").splitlines() if l.strip()
            ]
        if GUIDES_DIR.is_dir():
            for guide_file in sorted(GUIDES_DIR.glob("*.jsonl")):
                self.articles += [
                    json.loads(l) for l in guide_file.read_text(encoding="utf-8").splitlines() if l.strip()
                ]
        corpus = [
            tokenize(f"{a['law_name']} {a['article_no']} {a.get('article_title', '')} {a['text']}")
            for a in self.articles
        ]
        self.bm25 = BM25Okapi(corpus)

    def search(self, query: str, k: int = 6) -> list[dict]:
        """Top-k articles for a query. Results are cached (identical questions are
        common), and top-k selection uses argpartition — O(n) instead of an O(n log n)
        full sort, which matters as the corpus grows to thousands of precedents."""
        cached = self._cache.get((query, k))
        if cached is not None:
            return [dict(a) for a in cached]

        scores = self.bm25.get_scores(tokenize(expand_query(query)))
        if len(scores) > k:
            top = np.argpartition(scores, -k)[-k:]
            ranked = top[np.argsort(scores[top])[::-1]]
        else:
            ranked = np.argsort(scores)[::-1]
        results = [{**self.articles[i], "score": float(scores[i])} for i in ranked if scores[i] > 0]

        if len(self._cache) >= self.CACHE_SIZE:
            self._cache.pop(next(iter(self._cache)))  # simple FIFO eviction
        self._cache[(query, k)] = results
        return [dict(a) for a in results]

    def stats(self) -> dict:
        return {"articles": len(self.articles), "cache_entries": len(self._cache)}

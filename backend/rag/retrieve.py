"""Hybrid-ish retrieval over article records: BM25 on Korean char-bigrams + whitespace tokens.

Char bigrams avoid needing a Korean morphological analyzer for the prototype;
exact legal terms (전세권, 임차권 등) still match strongly.
"""

import json
import logging
import os
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi

logger = logging.getLogger("legal_ai.retrieve")

ROOT = Path(__file__).resolve().parents[2]
CORPUS_DIR = ROOT / "data" / "corpus"
DEFAULT_DATA = CORPUS_DIR / "articles.jsonl"
SAMPLE_DATA = CORPUS_DIR / "sample" / "articles.jsonl"
GUIDES_DIR = CORPUS_DIR / "guides"  # curated guides, always loaded alongside statutes
PREC_DATA = CORPUS_DIR / "precedents.jsonl"  # ingested precedents (real)
PREC_SAMPLE = CORPUS_DIR / "sample" / "precedents.jsonl"  # dev fixture

# data/corpus/sample/ is hand-written development fiction. Serving it to a real
# user as if it were law is the worst thing this project can do, so the retriever
# always reports which kind of corpus it loaded and the app refuses to start on
# a sample corpus outside development (see backend/app.py).
SAMPLE_MARKER = "SAMPLE"
SAMPLE_DIR_NAME = "sample"

# BM25 순위와 의미 검색 순위를 합치는 값. tools/tune_fusion.py 로 실측해 골랐습니다.
#
# 주의: 평가 문항이 16개뿐이라 이 값들은 근거가 얇습니다. 후보 30가지 중 13/16 은
# 이 조합 하나뿐이고 이웃한 조합은 12/16 이라, 봉우리 하나에 올라선 상태입니다.
# 평가 문항을 늘린 뒤 tune_fusion.py 를 다시 돌려 확인하세요. 그때 결과가 흔들리면
# 이 값이 아니라 문항 수가 문제였던 것입니다.
RRF_K = 5
RRF_WEIGHT_LEXICAL = 1.5  # 정확한 조문명·사건번호 일치를 조금 더 신뢰
RRF_WEIGHT_SEMANTIC = 1.0


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


def _display_path(path: Path) -> str:
    """Repo-relative when possible; tests and ad-hoc runs may load from elsewhere."""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


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
        self.articles = _load_jsonl(path)
        # Statute and precedent sources are the ones that must be real law.
        # Guides are curated by hand on purpose, so they are excluded from the check.
        self.sources: dict[str, Path] = {"articles": path}
        prec_path = PREC_DATA if PREC_DATA.exists() else PREC_SAMPLE
        if prec_path.exists():
            self.articles += _load_jsonl(prec_path)
            self.sources["precedents"] = prec_path
        if GUIDES_DIR.is_dir():
            for guide_file in sorted(GUIDES_DIR.glob("*.jsonl")):
                self.articles += _load_jsonl(guide_file)
        self.corpus_mode = self._detect_corpus_mode()
        self.embeddings, self.embed_owners = self._load_embeddings()
        corpus = [
            tokenize(f"{a['law_name']} {a['article_no']} {a.get('article_title', '')} {a['text']}")
            for a in self.articles
        ]
        self.bm25 = BM25Okapi(corpus)

    def _detect_corpus_mode(self) -> str:
        """'sample' if any loaded statute or precedent is a development fixture.

        Two independent signals, because either one alone can be fooled: a fixture
        copied out of sample/ keeps its SAMPLE ids, and a hypothetical real file
        placed inside sample/ is still not something to serve. Note that both the
        fixture and the ingested file are named articles.jsonl, so the filename
        alone tells you nothing.
        """
        if any(p.parent.name == SAMPLE_DIR_NAME for p in self.sources.values()):
            return "sample"
        for a in self.articles:
            if SAMPLE_MARKER in str(a.get("law_id", "")).upper():
                return "sample"
            if SAMPLE_MARKER in str(a.get("effective_date", "")).upper():
                return "sample"
        return "real"

    @property
    def retrieval_mode(self) -> str:
        """'hybrid' = BM25 + 의미 검색, 'lexical' = BM25 단독.

        같은 말뭉치라도 두 방식은 다른 결과를 냅니다. 검색 평가 기준선을 어느 쪽에서
        기록했는지 구분하지 않으면, 임베딩 없는 CI 가 임베딩 있는 로컬의 기준선과
        비교되어 회귀가 아닌 것을 회귀로 신고합니다.
        """
        return "hybrid" if self.embeddings is not None else "lexical"

    def _load_embeddings(self):
        """(벡터, 소유 조문 인덱스). 없으면 (None, None) 이고 BM25 단독으로 동작합니다."""
        if os.environ.get("LEGAL_AI_DISABLE_EMBEDDINGS") == "1":
            logger.info("LEGAL_AI_DISABLE_EMBEDDINGS=1: BM25 단독으로 동작합니다")
            return None, None
        try:
            from backend.rag import embed

            if not embed.available():
                return None, None
            cached = embed.load_cache(self.articles)
        except Exception as e:
            logger.warning("임베딩 캐시 로드 실패, BM25 단독으로 동작합니다: %s", e)
            return None, None
        if cached is None:
            logger.info("임베딩 캐시가 없어 BM25 단독으로 동작합니다. 생성: python tools/build_embeddings.py")
            return None, None
        return cached

    @staticmethod
    def kind_of(article: dict) -> str:
        law_id = str(article.get("law_id", ""))
        if law_id.startswith("GUIDE") or article.get("law_name") == "증거확보 가이드":
            return "guide"
        if law_id.startswith("PREC") or str(article.get("law_name", "")).startswith("판례"):
            return "precedent"
        return "statute"

    def _top_indices(self, scores: np.ndarray, n: int) -> list[int]:
        n = min(n, len(scores))
        top = np.argpartition(scores, -n)[-n:]
        return [int(i) for i in top[np.argsort(scores[top])[::-1]] if scores[i] > 0]

    def _bm25_ranking(self, query: str, n: int) -> list[int]:
        return self._top_indices(self.bm25.get_scores(tokenize(expand_query(query))), n)

    def _dense_ranking(self, query: str, n: int) -> list[int]:
        """의미 기반 순위. 임베딩 캐시가 없으면 빈 목록(BM25 단독으로 동작)."""
        if self.embeddings is None:
            return []
        try:
            from backend.rag import embed

            q = embed.encode_query(query)
        except Exception as e:  # 모델 로드 실패가 검색 전체를 막지는 않게 합니다
            logger.warning("임베딩 질의 인코딩 실패, BM25 로 계속합니다: %s", e)
            return []

        chunk_scores = self.embeddings @ q
        if self.embed_owners is None:  # 1조문 1벡터 (구형 캐시나 테스트 주입)
            return self._top_indices(chunk_scores, n)

        # 조각 점수를 조문 단위로 최댓값 집계. 질문이 조문의 한 항에만 해당해도
        # 그 조문 전체가 후보로 올라옵니다.
        article_scores = np.full(len(self.articles), -1.0, dtype="float32")
        np.maximum.at(article_scores, self.embed_owners, chunk_scores)
        return self._top_indices(article_scores, n)

    @staticmethod
    def _rrf(rankings: list[tuple[list[int], float]], kconst: float = RRF_K) -> dict[int, float]:
        """Reciprocal Rank Fusion.

        점수를 정규화해 더하지 않고 순위만 씁니다. BM25 점수와 코사인 유사도는
        척도가 전혀 달라서 정규화가 늘 자의적인데, RRF 는 그 문제를 피합니다.

        kconst 는 표준값 60 이 아니라 5 입니다. 60 은 "양쪽에서 무난한 문서"를
        "한쪽에서 1등인 문서"보다 위로 올리는데, 법률 검색에서는 사용자가 조문명이나
        사건번호를 정확히 적었을 때 그 정확한 일치가 이겨야 합니다. 실제로 60 에서는
        '몰래 녹음' 질문의 BM25 1위였던 2001도3106 이 여러 판례의 합의에 밀렸습니다.
        """
        fused: dict[int, float] = {}
        for ranking, weight in rankings:
            for rank, idx in enumerate(ranking):
                fused[idx] = fused.get(idx, 0.0) + weight / (kconst + rank + 1)
        return fused

    def search(self, query: str, k: int = 6) -> list[dict]:
        """Top-k articles for a query, fusing lexical (BM25) and semantic ranking."""
        cached = self._cache.get((query, k))
        if cached is not None:
            return [dict(a) for a in cached]

        pool_n = max(k * 6, 30)
        rankings = [
            (ranking, weight)
            for ranking, weight in (
                (self._bm25_ranking(query, pool_n), RRF_WEIGHT_LEXICAL),
                (self._dense_ranking(query, pool_n), RRF_WEIGHT_SEMANTIC),
            )
            if ranking
        ]
        fused = self._rrf(rankings)
        candidates = sorted(fused, key=lambda i: -fused[i])

        # 종류별 대표를 한 자리씩 보장합니다.
        #
        # 판례를 8건에서 63건으로 늘리자 "가해자와 통화한 내용을 녹음해도 되나요"의
        # 상위 5건이 전부 판례로 채워지고, 정작 그 질문에 답하는 증거확보 가이드가
        # 밀려났습니다. 피해자에게 필요한 것은 손해배상 판결문이 아니라 무엇을 해도
        # 되는지 알려주는 안내입니다. 법령, 판례, 가이드를 한 통에 넣고 점수만으로
        # 자르면 문서 수가 많은 종류가 항상 이깁니다.
        picked: list[int] = []
        for kind in ("statute", "precedent", "guide"):
            best = next((i for i in candidates if self.kind_of(self.articles[i]) == kind), None)
            if best is not None and len(picked) < k:
                picked.append(best)
        for i in candidates:
            if len(picked) >= k:
                break
            if i not in picked:
                picked.append(i)
        picked.sort(key=lambda i: -fused[i])

        results = [{**self.articles[i], "score": float(fused[i])} for i in picked]

        if len(self._cache) >= self.CACHE_SIZE:
            self._cache.pop(next(iter(self._cache)))  # simple FIFO eviction
        self._cache[(query, k)] = results
        return [dict(a) for a in results]

    def stats(self) -> dict:
        return {
            "articles": len(self.articles),
            "cache_entries": len(self._cache),
            "corpus": self.corpus_mode,
            "retrieval": self.retrieval_mode,
            "corpus_sources": {k: _display_path(p) for k, p in self.sources.items()},
        }

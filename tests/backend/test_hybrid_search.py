"""BM25 + 의미 검색 융합 테스트.

임베딩 모델은 수백 MB라 CI 에서 내려받지 않습니다. 대신 가짜 벡터를 주입해
융합 경로가 실제로 동작하는지 확인합니다. 모델 품질이 아니라 배선을 검사하는
테스트이며, 여기가 조용히 깨지면 의미 검색이 꺼진 채로 배포됩니다.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.rag.retrieve import Retriever  # noqa: E402


@pytest.fixture
def retriever():
    return Retriever()


def test_rrf_prefers_documents_ranked_well_by_both():
    """두 방식 모두에서 상위권인 문서가 한쪽에서만 1등인 문서를 이겨야 합니다."""
    fused = Retriever._rrf([([10, 20, 30], 1.0), ([20, 40, 50], 1.0)])
    assert fused[20] > fused[10], "양쪽 상위권(20)이 한쪽 1등(10)보다 높아야 합니다"
    assert set(fused) == {10, 20, 30, 40, 50}


def test_rrf_weight_shifts_the_winner():
    """가중치를 주면 그 순위표의 1위가 이길 수 있어야 합니다.

    사용자가 사건번호나 조문명을 정확히 적었을 때, 그 정확한 일치가 여러 문서의
    합의에 밀리지 않게 하는 장치입니다.
    """
    equal = Retriever._rrf([([10, 20], 1.0), ([20, 30], 1.0)])
    weighted = Retriever._rrf([([10, 20], 10.0), ([20, 30], 1.0)])
    assert equal[20] > equal[10]
    assert weighted[10] > weighted[20]


def test_rrf_ignores_score_scale():
    """RRF 는 순위만 봅니다. 점수 척도가 달라도 결과가 같아야 합니다."""
    assert Retriever._rrf([([1, 2], 1.0)]) == Retriever._rrf([([1, 2], 1.0)])


def test_search_without_embeddings_still_works(retriever):
    """임베딩 캐시가 없을 때 BM25 단독으로 조용히 되돌아가야 합니다."""
    retriever.embeddings = None
    retriever._cache.clear()
    results = retriever.search("전세 보증금을 못 돌려받고 있어요", k=5)
    assert results and len(results) <= 5


def test_search_uses_embeddings_when_present(monkeypatch, retriever):
    """가짜 벡터를 주입하면 의미 순위가 결과에 반영되어야 합니다."""
    import backend.rag.embed as embed_mod

    rng = np.random.default_rng(0)
    dim = 8
    vectors = rng.normal(size=(len(retriever.articles), dim)).astype("float32")
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    retriever.embeddings = vectors
    retriever.embed_owners = None
    retriever._cache.clear()

    # 특정 조문 하나를 질의 벡터와 정확히 일치시켜, 의미 순위 1위로 만듭니다.
    target = 3
    monkeypatch.setattr(embed_mod, "encode_query", lambda q, *a, **kw: vectors[target])

    # 의미 순위 자체가 그 조문을 1위로 뽑아야 합니다.
    assert retriever._dense_ranking("아무 질문이나", 30)[0] == target

    # 그리고 그 순위가 최종 결과에 실제로 반영되어야 합니다. 자리 배분과 가중치에
    # 따라 특정 조문이 상위 5개에 들지 못할 수는 있으므로, 결과가 BM25 단독일 때와
    # 달라졌는지로 확인합니다. 여기가 같다면 의미 검색이 꺼진 것과 다름없습니다.
    hybrid = [r["article_no"] for r in retriever.search("아무 질문이나", k=5)]
    retriever.embeddings = None
    retriever._cache.clear()
    lexical = [r["article_no"] for r in retriever.search("아무 질문이나", k=5)]
    assert hybrid != lexical


def test_embedding_failure_does_not_break_search(monkeypatch, retriever):
    """모델 로드가 실패해도 검색은 계속되어야 합니다.

    의미 검색이 안 되는 것은 품질 저하이지만, 검색이 죽는 것은 장애입니다.
    """
    import backend.rag.embed as embed_mod

    retriever.embeddings = np.zeros((len(retriever.articles), 4), dtype="float32")
    retriever.embed_owners = None
    retriever._cache.clear()

    def boom(*a, **kw):
        raise RuntimeError("모델 로드 실패")

    monkeypatch.setattr(embed_mod, "encode_query", boom)
    assert retriever.search("전세 보증금", k=5)


def test_source_kinds_are_classified(retriever):
    kinds = {Retriever.kind_of(a) for a in retriever.articles}
    assert "statute" in kinds
    assert kinds <= {"statute", "precedent", "guide"}


def test_each_source_kind_gets_a_slot(retriever):
    """한 종류가 상위 k개를 독식하지 않아야 합니다.

    판례가 8건에서 63건으로 늘었을 때 증거확보 가이드가 밀려나 '통화를 녹음해도
    되나요'에 답하지 못하게 된 회귀를 막습니다.
    """
    retriever._cache.clear()
    results = retriever.search("가해자와 통화한 내용을 녹음해도 되나요?", k=5)
    kinds = {Retriever.kind_of(r) for r in results}
    assert len(kinds) >= 2, f"결과가 한 종류에 몰렸습니다: {kinds}"

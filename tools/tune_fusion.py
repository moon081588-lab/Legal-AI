"""RRF 융합 파라미터를 실측으로 고릅니다.

BM25 순위와 의미 검색 순위를 합칠 때 두 가지를 정해야 합니다.

  kconst  작을수록 "한쪽에서 1등"이 유리하고, 클수록 "양쪽에서 무난"이 유리합니다.
          표준값 60 은 후자 쪽이라, 정확한 조문명이나 사건번호로 BM25 가 정확히
          맞힌 결과가 여러 판례의 합의에 밀릴 수 있습니다.
  weight  두 방식 중 어느 쪽을 더 믿을지.

정답이 없으므로 추측하지 말고 전부 돌려 보고 고릅니다. 질문 임베딩은 한 번만
계산해 재사용하므로 조합을 많이 넣어도 빠릅니다.

    python tools/tune_fusion.py
"""

import json
import sys
from itertools import product
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.rag.retrieve import Retriever, expand_query, tokenize  # noqa: E402

KCONSTS = [1, 3, 5, 10, 20, 60]
WEIGHTS = [(1.0, 1.0), (1.5, 1.0), (2.0, 1.0), (1.0, 1.5), (1.0, 2.0)]
TOP_K = 5
POOL = 30


def rank_lists(retriever: Retriever, questions: list[dict]) -> list[tuple[list[int], list[int]]]:
    from backend.rag import embed

    print(f"질문 {len(questions)}건 인코딩 중...")
    qvecs = embed.encode([q["question"] for q in questions])
    out = []
    for q, qv in zip(questions, qvecs):
        bm = retriever._top_indices(retriever.bm25.get_scores(tokenize(expand_query(q["question"]))), POOL)
        dn = retriever._top_indices(retriever.embeddings @ qv, POOL)
        out.append((bm, dn))
    return out


def fuse(bm: list[int], dn: list[int], kconst: float, w_bm: float, w_dn: float) -> dict[int, float]:
    fused: dict[int, float] = {}
    for ranking, weight in ((bm, w_bm), (dn, w_dn)):
        for rank, idx in enumerate(ranking):
            fused[idx] = fused.get(idx, 0.0) + weight / (kconst + rank + 1)
    return fused


def pick(retriever: Retriever, fused: dict[int, float], k: int) -> list[int]:
    candidates = sorted(fused, key=lambda i: -fused[i])
    picked: list[int] = []
    for kind in ("statute", "precedent", "guide"):
        best = next((i for i in candidates if retriever.kind_of(retriever.articles[i]) == kind), None)
        if best is not None and len(picked) < k:
            picked.append(best)
    for i in candidates:
        if len(picked) >= k:
            break
        if i not in picked:
            picked.append(i)
    return picked


def main() -> None:
    retriever = Retriever()
    if retriever.embeddings is None:
        sys.exit("임베딩 캐시가 없습니다. python tools/build_embeddings.py 를 먼저 실행하세요.")

    questions = [
        json.loads(l)
        for l in (ROOT / "tests" / "evals" / "questions.jsonl").read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    questions = [q for q in questions if q.get("expected_law")]
    ranks = rank_lists(retriever, questions)

    rows = []
    for kconst, (w_bm, w_dn) in product(KCONSTS, WEIGHTS):
        hits, missed = 0, []
        for q, (bm, dn) in zip(questions, ranks):
            picked = pick(retriever, fuse(bm, dn, kconst, w_bm, w_dn), TOP_K)
            found = {(retriever.articles[i]["law_name"], retriever.articles[i]["article_no"]) for i in picked}
            if any((q["expected_law"], a) in found for a in q["expected_articles"]):
                hits += 1
            else:
                missed.append(q["question"][:24])
        rows.append((hits, kconst, w_bm, w_dn, missed))

    rows.sort(key=lambda r: -r[0])
    print(f"\n{'Recall@5':>9}  {'kconst':>6}  {'BM25':>5}  {'의미':>5}   미달 문항")
    for hits, kconst, w_bm, w_dn, missed in rows:
        print(f"{hits:>4}/{len(questions):<4}  {kconst:>6}  {w_bm:>5}  {w_dn:>5}   {', '.join(missed)}")

    best = rows[0]
    print(
        f"\n최고: Recall@5 {best[0]}/{len(questions)} (kconst={best[1]}, BM25={best[2]}, 의미={best[3]})\n"
        f"backend/rag/retrieve.py 의 _rrf 기본값에 반영하세요.\n\n"
        f"주의: 문항이 16개뿐이라 1~2건 차이는 우연일 수 있습니다. 동점이면 표준값(kconst=60,\n"
        f"      가중치 1:1)에 가까운 쪽을 고르는 편이 새 질문에 더 안전합니다."
    )


if __name__ == "__main__":
    main()

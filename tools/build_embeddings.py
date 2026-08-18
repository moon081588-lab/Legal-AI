"""조문 임베딩 캐시를 만듭니다. 법령을 새로 수집한 뒤 한 번 실행하세요.

    pip install -r requirements-embed.txt
    python tools/build_embeddings.py

첫 실행은 모델(수백 MB)을 내려받느라 몇 분 걸리고, 이후에는 캐시를 재사용합니다.
말뭉치가 바뀌면 지문이 달라져 캐시가 무효가 되므로 다시 실행해야 합니다.
"""

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.rag import embed  # noqa: E402
from backend.rag.retrieve import Retriever  # noqa: E402


def main() -> None:
    if not embed.available():
        sys.exit(
            "sentence-transformers 가 설치되어 있지 않습니다.\n"
            "  pip install -r requirements-embed.txt"
        )

    retriever = Retriever()
    articles = retriever.articles
    print(f"조문·판례·가이드 {len(articles)}건을 인코딩합니다 (모델: {embed.DEFAULT_MODEL})")

    started = time.monotonic()
    meta = embed.build_cache(articles)
    elapsed = time.monotonic() - started

    print(
        f"\n완료: {meta['count']}건, {meta['dim']}차원, {elapsed:.0f}초\n"
        f"  벡터: {embed.VECTORS_FILE.relative_to(ROOT)}\n"
        f"  메타: {embed.META_FILE.relative_to(ROOT)}\n\n"
        f"검색 평가를 다시 실행해 보세요:\n"
        f"  python tests/evals/run_evals.py"
    )


if __name__ == "__main__":
    main()

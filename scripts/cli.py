#!/usr/bin/env python3
"""Legal-AI 터미널 도구.

사용법:
    python scripts/cli.py "전세 보증금을 돌려받지 못하고 있어요. 어떤 법이 적용되나요?"

ANTHROPIC_API_KEY 가 설정되어 있으면 검색된 조문을 근거로 답변을 생성하고,
없으면 검색된 조문 원문만 보여 줍니다.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rag.retrieve import Retriever
from rag.answer import answer


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit('사용법: python scripts/cli.py "질문 내용"  — 질문을 함께 입력해 주세요.')
    question = " ".join(sys.argv[1:])

    retriever = Retriever()
    articles = retriever.search(question, k=5)

    print(f"\n[검색된 조문 {len(articles)}건] (data: {retriever.path.name})")
    for a in articles:
        title = f"({a['article_title']})" if a.get("article_title") else ""
        print(f"  - {a['law_name']} {a['article_no']}{title}  score={a['score']:.1f}")

    result = answer(question, articles)
    if result is None:
        print("\nANTHROPIC_API_KEY가 설정되어 있지 않아 답변 생성은 건너뜁니다. 위 조문의 원문을 보여드립니다:")
        for a in articles[:3]:
            print(f"\n--- {a['law_name']} {a['article_no']} ---\n{a['text'][:600]}")
    else:
        print("\n" + "=" * 60 + "\n" + result)


if __name__ == "__main__":
    main()

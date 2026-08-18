"""'모른다'고 말할 기준선을 실측으로 정합니다.

답할 수 있는 질문과 답할 수 없는 질문을 각각 넣고, 두 무리의 유사도 분포가 어디서
갈리는지 봅니다. 겹치는 구간이 넓으면 이 신호로는 구분할 수 없다는 뜻이고, 그때는
임계값을 억지로 정하지 말고 말뭉치를 채우는 편이 맞습니다.

    python tools/tune_confidence.py

답할 수 없는 질문 목록은 지금 말뭉치에 없는 법령을 기준으로 직접 관리하세요.
법령을 추가로 수집하면 이 목록도 바뀌어야 합니다.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.rag.confidence import statute_similarity  # noqa: E402
from backend.rag.retrieve import Retriever  # noqa: E402

# 말뭉치에 해당 법령이 없어 반드시 '모른다'고 해야 하는 질문.
# laws.txt 에 법령을 추가했다면 여기서 빼고, 여전히 없는 주제로 채워 주세요.
UNANSWERABLE = [
    "자동차 보험료가 너무 비싼데 깎을 수 있나요?",
    "상표권 침해로 고소하려면 어떻게 하나요?",
    "건축물 용도변경 허가는 어디서 받나요?",
    "주식 공매도 규제가 어떻게 되나요?",
    "군 복무 중 다쳤는데 보상받을 수 있나요?",
    "특허 출원 절차를 알려주세요.",
    "외국인 비자 연장은 어떻게 하나요?",
]


def main() -> None:
    retriever = Retriever()
    if retriever.embeddings is None:
        sys.exit(
            "의미 검색이 꺼져 있습니다. 코사인 유사도가 없으면 질의 간 비교가 불가능합니다.\n"
            "  python tools/build_embeddings.py"
        )

    from backend.rag import embed

    answerable = [
        json.loads(l)["question"]
        for l in (ROOT / "tests" / "evals" / "questions.jsonl").read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]

    print(f"질문 {len(answerable) + len(UNANSWERABLE)}건 인코딩 중...")
    vecs = embed.encode(answerable + UNANSWERABLE)

    def score(question: str, vec) -> float:
        pool = retriever._bm25_ranking(question, 30) + retriever._dense_ranking(question, 30)
        return statute_similarity(vec, retriever, list(dict.fromkeys(pool)))

    yes = [(score(q, v), q) for q, v in zip(answerable, vecs[: len(answerable)])]
    no = [(score(q, v), q) for q, v in zip(UNANSWERABLE, vecs[len(answerable) :])]

    print("\n--- 답할 수 있어야 하는 질문 ---")
    for s, q in sorted(yes):
        print(f"  {s:.3f}  {q[:52]}")
    print("\n--- 모른다고 해야 하는 질문 ---")
    for s, q in sorted(no):
        print(f"  {s:.3f}  {q[:52]}")

    lowest_yes = min(s for s, _ in yes)
    highest_no = max(s for s, _ in no)
    print(f"\n답할 수 있는 질문의 최저: {lowest_yes:.3f}")
    print(f"답할 수 없는 질문의 최고: {highest_no:.3f}")

    if highest_no < lowest_yes:
        suggested = (highest_no + lowest_yes) / 2
        print(
            f"\n두 무리가 겹치지 않습니다. 경계 후보: {suggested:.3f}\n"
            f"  ABSTAIN_BELOW={suggested:.2f} 로 두면 지금 표본에서는 오분류가 없습니다.\n"
            f"  다만 표본이 작으니 여유를 두고 조금 낮추는 편이 안전합니다."
        )
    else:
        print(
            f"\n두 무리가 {highest_no - lowest_yes:.3f} 만큼 겹칩니다. 이 신호만으로는 깨끗이 나눌 수 없습니다.\n"
            "임계값을 억지로 정하면 답할 수 있는 질문을 거절하게 됩니다. 그보다는\n"
            "tools/ingest/laws.txt 에 빠진 법령을 채우는 편이 실질적인 개선입니다."
        )


if __name__ == "__main__":
    main()

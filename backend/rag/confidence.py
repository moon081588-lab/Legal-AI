"""검색 결과가 질문을 실제로 다루고 있는지 판단합니다.

검색은 언제나 무언가를 돌려줍니다. '아동학대 신고는 어떻게 하나요'라고 물으면
아동학대처벌법이 말뭉치에 없어도 형사소송법 조문과 판례를 자신 있게 내놓습니다.
이용자는 자기가 물은 법이 이 서비스에 없다는 사실을 알 방법이 없습니다.

법률 서비스에서 가장 위험한 실패는 틀리는 것이 아니라 **틀렸다는 사실이 보이지
않는 것**입니다. 그래서 모를 때는 모른다고 말할 수 있어야 합니다.

## 왜 의미 유사도를 쓰는가

처음에는 '질문의 낱말이 검색 결과에 나타나는 비율'로 판단하려 했는데, 실측해 보니
쓸모가 없었습니다. 답할 수 없는 질문이 오히려 높은 점수를 받았습니다. '아동학대'라는
낱말이 판례 사건명에 들어 있어서, 정작 그 질문에 답하는 법률이 없는데도 포괄률이
1.00 이 나왔기 때문입니다.

BM25 점수도 쓸 수 없습니다. 질의마다 척도가 달라 임계값을 정할 수 없습니다.

코사인 유사도는 [-1, 1] 로 묶여 있어 질의가 달라도 해석이 같습니다. 그래서 의미
검색이 켜져 있을 때만 판단하고, 꺼져 있으면 판단을 포기합니다. 근거 없이 자신 있게
'모른다'고 하는 것도 틀린 답이기 때문입니다.
"""

from __future__ import annotations

import os

import numpy as np

# tools/tune_confidence.py 로 실측해 정하세요. 여기 적힌 값은 아직 측정 전 임시값이며,
# 말뭉치를 바꾸면(법령을 추가하면) 반드시 다시 측정해야 합니다.
ABSTAIN_BELOW = float(os.environ.get("LEGAL_AI_ABSTAIN_BELOW", "0.30"))
CAUTION_BELOW = float(os.environ.get("LEGAL_AI_CAUTION_BELOW", "0.42"))

# 판례와 가이드는 '이 주제를 다루는 법이 있는가'의 근거가 되지 못합니다.
# 아동학대 판례가 검색됐다고 해서 아동학대처벌법을 안내할 수 있는 것은 아닙니다.
EVIDENCE_KINDS = ("statute",)


def statute_similarity(query_vec: np.ndarray, retriever, indices: list[int]) -> float | None:
    """검색된 법령 조문 중 질문과 가장 가까운 것의 코사인 유사도."""
    if query_vec is None or retriever.embeddings is None:
        return None
    sims = [
        float(retriever.embeddings[i] @ query_vec)
        for i in indices
        if retriever.kind_of(retriever.articles[i]) in EVIDENCE_KINDS
    ]
    return max(sims) if sims else 0.0


def assess(similarity: float | None) -> dict:
    """{'level': 'ok'|'caution'|'abstain'|'unknown', 'similarity': float|None}

    'unknown' 은 판단을 포기했다는 뜻입니다(의미 검색 꺼짐). 이때는 평소처럼
    답하되 확신 표시를 하지 않습니다.
    """
    if similarity is None:
        return {"level": "unknown", "similarity": None}
    if similarity < ABSTAIN_BELOW:
        level = "abstain"
    elif similarity < CAUTION_BELOW:
        level = "caution"
    else:
        level = "ok"
    return {"level": level, "similarity": round(similarity, 3)}


CAUTION_NOTICE = (
    "\n\n※ 이 질문과 직접 관련된 법령을 확실히 찾지 못했습니다. "
    "아래 답변이 질문과 어긋날 수 있으니 반드시 원문과 대조하시고, "
    "대한법률구조공단(국번없이 132) 상담을 함께 이용해 주세요."
)


def abstain_message() -> str:
    """모를 때 하는 말. 지어내는 것보다 낫습니다."""
    return (
        "질문에 해당하는 법령을 이 서비스의 자료에서 찾지 못했습니다.\n\n"
        "관련 조문 없이 답변을 지어내면 잘못된 법률 정보를 드리게 되므로, "
        "추측해서 답하지 않겠습니다.\n\n"
        "다음을 이용해 주세요.\n"
        "- 대한법률구조공단 국번없이 132 (무료 법률상담)\n"
        "- 국가법령정보센터 www.law.go.kr 에서 직접 검색\n"
        "- 범죄 피해로 지금 도움이 필요하시면 여성긴급전화 1366 (24시간)\n\n"
        "질문을 조금 다르게 적어 주시면 다시 찾아보겠습니다."
    )

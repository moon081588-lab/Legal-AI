"""Answer synthesis with Claude, constrained to retrieved statute text.

Guardrails (변호사법 / AI 기본법):
- Explains law and cites articles; never gives case-specific advice or outcome predictions.
- Answers only from retrieved text; says so when nothing relevant is found.
- Every answer carries an AI disclosure + referral to 대한법률구조공단 (132).
"""

import os

SYSTEM_PROMPT = """당신은 대한민국 법령 정보를 안내하는 AI 도우미입니다. 변호사가 아니며, 법률 자문을 제공하지 않습니다. 특히 범죄 피해자가 적법하게 증거를 확보·보존하는 방법을 안내하는 데 특화되어 있습니다.

응대 원칙 (피해자 배려):
- 사용자가 피해 경험이나 고통을 표현하면, 답변 첫머리에 한두 문장으로 진정성 있게 공감을 표현한 뒤 본론으로 들어가세요. 형식적이거나 과장된 위로는 하지 마세요.
- 절대 사용자를 탓하는 표현을 쓰지 마세요("왜 진작 신고하지 않으셨나요" 등). 필요하면 피해는 사용자의 잘못이 아니라는 점을 짚어 주세요.
- 감정을 되풀이해 강조하여 고통을 증폭시키지 말고, 지금 할 수 있는 구체적인 다음 단계를 제시하여 상황에 대한 통제감을 회복하도록 도우세요.
- 사용자가 자해·자살을 언급하거나 심리적으로 매우 힘들어 보이면, 법률 정보와 함께 자살예방 상담전화(109, 24시간)나 정신건강 위기상담(1577-0199)을 부드럽게 안내하세요. 지금 신체적 위험에 처해 있다면 112 신고를 최우선으로 안내하세요.

규칙:
1. 아래 <참고조문>에 있는 내용만 근거로 답하세요. 참고조문에 없는 내용은 "제공된 법령 정보에서 확인할 수 없습니다"라고 말하세요.
2. 법령은 (법령명 제N조), 판례는 (대법원 사건번호, 예: 대법원 2001도3106), 가이드는 (증거확보 가이드: 제목) 형식으로 근거를 인용하세요. 판례를 인용할 때는 그 판례가 어떤 기준을 제시했는지 요지를 함께 설명하세요.
3. 쉬운 한국어로 설명하세요. 법률 용어는 풀어서 설명하세요.
4. 증거 확보 관련 답변의 필수 원칙:
   - 적법한 방법만 안내하세요. 불법적인 증거 수집 방법(타인 간 대화의 몰래 녹음·도청, 타인 기기·계정의 무단 열람, 해킹, 무단 침입, 동의 없는 위치추적)은 어떤 경우에도 방법을 안내하지 말고, 그것이 범죄이며 위법하게 수집한 증거는 재판에서 쓸 수 없다는 점(형사소송법 제308조의2)을 경고하세요.
   - 녹음 관련 질문에는 본인이 참여한 대화(적법)와 타인 간 대화(불법)를 반드시 구분해 주세요.
   - 확보하기 어려운 증거는 직접 수집을 시도하기보다 수사기관 신고, 증거보전 청구 등 적법한 절차를 안내하세요.
5. 다음 요청은 정중히 거절하고 변호사 상담을 안내하세요: 소송 승패 예측, 소송 전략, 개별 사건에 대한 구체적 행동 지시, 법원 제출용 서면 작성.
6. 답변 마지막에 항상 다음을 포함하세요:
   "※ 이 답변은 AI가 생성한 일반적인 법령 정보이며 법률 자문이 아닙니다. 구체적인 사안은 변호사 또는 대한법률구조공단(국번없이 132) 상담을 이용하세요."
"""


# 지원 언어는 한국어·영어 두 가지입니다. 법령 원문은 한국어이므로, 번역 답변에도
# 법령명과 조문 번호는 한국어를 병기해 사용자가 원문을 찾을 수 있게 합니다.
LANG_NAMES = {"ko": "한국어", "en": "English"}


def option_instructions(lang: str = "ko", simple: bool = False) -> str:
    parts = []
    if lang != "ko" and lang in LANG_NAMES:
        parts.append(
            f"사용자를 위해 답변 전체를 {LANG_NAMES[lang]}로 작성해 주세요. "
            f"법령명과 조문 번호는 한국어 원문을 병기해 주세요."
        )
    if simple:
        parts.append("쉬운 말 모드: 초등학생도 이해할 수 있는 쉬운 단어와 짧은 문장으로 설명해 주세요.")
    return "\n".join(parts)


def build_user_prompt(question: str, articles: list[dict]) -> str:
    if not articles:
        context = "(검색된 조문 없음)"
    else:
        context = "\n\n".join(
            f"[{a['law_name']} {a['article_no']}{'(' + a['article_title'] + ')' if a.get('article_title') else ''}]\n{a['text']}"
            for a in articles
        )
    return f"<참고조문>\n{context}\n</참고조문>\n\n질문: {question}"


def answer(question: str, articles: list[dict], model: str = "claude-sonnet-4-5") -> str:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None  # caller falls back to retrieval-only display
    import anthropic

    client = anthropic.Anthropic()
    msg = client.messages.create(
        model=model,
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_user_prompt(question, articles)}],
    )
    return msg.content[0].text

"""Legal-AI Phase 1 backend.

Run:  uvicorn backend.app:app --reload --port 8000   (from repo root)

POST /api/chat {"question": "..."} -> Server-Sent Events:
  event: sources   data: [{law_name, article_no, article_title, text, source_url}, ...]
  event: delta     data: {"text": "..."}   (repeated)
  event: done      data: {}

Works without ANTHROPIC_API_KEY (retrieval-grounded fallback answer) so the UI
is demoable before keys are configured.
"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, Header  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import StreamingResponse  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from rag.answer import SYSTEM_PROMPT, build_user_prompt  # noqa: E402
from rag.retrieve import Retriever  # noqa: E402

DISCLAIMER = (
    "※ 이 답변은 AI가 생성한 일반적인 법령 정보이며 법률 자문이 아닙니다. "
    "구체적인 사안은 변호사 또는 대한법률구조공단(국번없이 132) 상담을 이용하세요."
)

# Attorney-at-Law Act guardrail: requests we route away from the RAG pipeline.
OUT_OF_SCOPE_PATTERNS = [
    "이길 수", "승소할", "승산", "소송 전략", "이기는 방법",
    "대신 써", "대신 작성", "답변서를 써", "소장을 써", "서면을 작성",
]
OUT_OF_SCOPE_MESSAGE = (
    "죄송하지만 소송의 승패 예측, 소송 전략, 법원 제출용 서면 작성은 변호사만 할 수 있는 "
    "법률 사무여서 도와드릴 수 없습니다. 관련된 법령과 제도가 궁금하시면 다시 질문해 주세요.\n\n"
    "무료 상담: 대한법률구조공단 국번없이 132 (klac.or.kr)\n\n" + DISCLAIMER
)

app = FastAPI(title="Legal-AI")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

retriever = Retriever()


class ChatRequest(BaseModel):
    question: str


def sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def fallback_answer(articles: list[dict]) -> str:
    """No-API-key mode: present retrieved articles verbatim, no generation."""
    if not articles:
        return "제공된 법령 정보에서 관련 조문을 찾지 못했습니다.\n\n" + DISCLAIMER
    parts = ["질문과 관련된 조문입니다. (API 키 미설정: 조문 원문 표시 모드)\n"]
    for a in articles[:3]:
        title = f"({a['article_title']})" if a.get("article_title") else ""
        parts.append(f"■ {a['law_name']} {a['article_no']}{title}\n{a['text']}\n")
    parts.append(DISCLAIMER)
    return "\n".join(parts)


def stream_claude(question: str, articles: list[dict], api_key: str | None = None):
    import anthropic

    # Priority: server env var > per-request user key. The user key is used for
    # this request only and never stored or logged.
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY") or api_key)
    with client.messages.stream(
        model=os.environ.get("LEGAL_AI_MODEL", "claude-sonnet-4-5"),
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_user_prompt(question, articles)}],
    ) as stream:
        yield from stream.text_stream


@app.post("/api/chat")
def chat(req: ChatRequest, x_anthropic_key: str | None = Header(default=None)):
    question = req.question.strip()
    api_key = (x_anthropic_key or "").strip() or None

    def generate():
        if any(p in question for p in OUT_OF_SCOPE_PATTERNS):
            yield sse("sources", [])
            yield sse("delta", {"text": OUT_OF_SCOPE_MESSAGE})
            yield sse("done", {})
            return

        articles = retriever.search(question, k=5)
        yield sse("sources", [
            {k: a[k] for k in ("law_name", "article_no", "article_title", "text", "source_url")}
            for a in articles
        ])

        if os.environ.get("ANTHROPIC_API_KEY") or api_key:
            try:
                for text in stream_claude(question, articles, api_key):
                    yield sse("delta", {"text": text})
            except Exception:
                yield sse("delta", {"text": "답변 생성 중 오류가 발생했습니다. API 키가 올바른지 확인해 주세요."})
        else:
            yield sse("delta", {"text": fallback_answer(articles)})
        yield sse("done", {})

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "articles": len(retriever.articles),
        "data": retriever.path.name,
        "generation": bool(os.environ.get("ANTHROPIC_API_KEY")),
    }

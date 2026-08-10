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
import logging
import os
import sys
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
logger = logging.getLogger("legal_ai")

# Optional crash reporting: set SENTRY_DSN to enable. PII is never sent.
if os.environ.get("SENTRY_DSN"):
    try:
        import sentry_sdk

        sentry_sdk.init(dsn=os.environ["SENTRY_DSN"], traces_sample_rate=0.1, send_default_pii=False)
    except ImportError:
        logger.warning("SENTRY_DSN set but sentry-sdk not installed")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, Header  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import StreamingResponse  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from rag.answer import SYSTEM_PROMPT, build_user_prompt, option_instructions  # noqa: E402
from rag.retrieve import Retriever  # noqa: E402
from rag.verify import verify_citations  # noqa: E402

DISCLAIMER = (
    "※ 이 답변은 AI가 생성한 일반적인 법령 정보이며 법률 자문이 아닙니다. "
    "구체적인 사안은 변호사 또는 대한법률구조공단(국번없이 132) 상담을 이용하세요."
)

# Acute-crisis signals: lead with emergency resources before legal information.
CRISIS_PATTERNS = [
    "자살", "죽고 싶", "죽어버리", "자해", "살기 싫",
    "지금 위험", "지금 맞고", "감금", "쫓기고 있", "살려주세요",
]
CRISIS_MESSAGE = (
    "많이 힘드신 상황인 것 같습니다. 법률 정보보다 먼저, 지금 도움을 받을 수 있는 곳을 알려드립니다.\n\n"
    "· 지금 신체적 위험에 처해 있다면: 112 (경찰, 24시간)\n"
    "· 마음이 많이 힘들다면: 자살예방 상담전화 109 (24시간), 정신건강 위기상담 1577-0199\n"
    "· 가정폭력·성폭력: 여성긴급전화 1366 (24시간)\n\n"
    "혼자 견디지 않으셔도 됩니다. 이어서 관련 법령 정보도 함께 안내드립니다.\n"
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
    lang: str = "ko"
    simple: bool = False


class SummaryRequest(BaseModel):
    messages: list[dict]  # [{role: "user"|"bot", text: "..."}]


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


def stream_claude(question: str, articles: list[dict], api_key: str | None = None,
                  lang: str = "ko", simple: bool = False):
    import anthropic

    # Priority: server env var > per-request user key. The user key is used for
    # this request only and never stored or logged.
    client = anthropic.Anthropic(
        api_key=os.environ.get("ANTHROPIC_API_KEY") or api_key,
        timeout=60.0,  # fail with a friendly error instead of hanging the stream
        max_retries=1,
    )
    prompt = build_user_prompt(question, articles)
    extra = option_instructions(lang, simple)
    if extra:
        prompt = extra + "\n\n" + prompt
    with client.messages.stream(
        model=os.environ.get("LEGAL_AI_MODEL", "claude-sonnet-4-5"),
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        yield from stream.text_stream


@app.post("/api/chat")
def chat(req: ChatRequest, x_anthropic_key: str | None = Header(default=None)):
    question = req.question.strip()
    api_key = (x_anthropic_key or "").strip() or None

    def generate():
        # Latency metrics: logged without question content, and returned in the
        # `done` event so the client can also report them.
        t0 = time.monotonic()
        ttft_ms: int | None = None

        if any(p in question for p in CRISIS_PATTERNS):
            yield sse("delta", {"text": CRISIS_MESSAGE + "\n"})

        if any(p in question for p in OUT_OF_SCOPE_PATTERNS):
            yield sse("sources", [])
            yield sse("delta", {"text": OUT_OF_SCOPE_MESSAGE})
            yield sse("done", {"ttft_ms": 0, "total_ms": int((time.monotonic() - t0) * 1000)})
            logger.info("chat route=out_of_scope total_ms=%d", (time.monotonic() - t0) * 1000)
            return

        articles = retriever.search(question, k=5)
        yield sse("sources", [
            {k: a[k] for k in ("law_name", "article_no", "article_title", "text", "source_url")}
            for a in articles
        ])

        full_answer = ""
        generated = bool(os.environ.get("ANTHROPIC_API_KEY") or api_key)
        if generated:
            try:
                for text in stream_claude(question, articles, api_key, req.lang, req.simple):
                    if ttft_ms is None:
                        ttft_ms = int((time.monotonic() - t0) * 1000)
                    full_answer += text
                    yield sse("delta", {"text": text})
            except Exception as e:
                logger.warning("chat generation_error=%s", type(e).__name__)
                yield sse("delta", {"text": "답변 생성 중 오류가 발생했습니다. API 키가 올바른지 확인해 주세요."})
        else:
            ttft_ms = int((time.monotonic() - t0) * 1000)
            yield sse("delta", {"text": fallback_answer(articles)})

        if full_answer:
            result = verify_citations(full_answer, articles)
            yield sse("verified", result)
            if not result["ok"]:
                warn = ", ".join(result["unknown"])
                yield sse("delta", {"text": f"\n\n⚠️ 다음 인용은 검색된 근거에서 확인되지 않았습니다. 원문을 직접 확인해 주세요: {warn}"})

        total_ms = int((time.monotonic() - t0) * 1000)
        yield sse("done", {"ttft_ms": ttft_ms, "total_ms": total_ms})
        logger.info(
            "chat route=rag generated=%s sources=%d ttft_ms=%s total_ms=%d",
            generated, len(articles), ttft_ms, total_ms,
        )

    return StreamingResponse(generate(), media_type="text/event-stream")


SUMMARY_PROMPT = """다음 대화에서 사용자(피해자)가 말한 내용을 바탕으로, 변호사·법률구조공단 상담에 가져갈 '상담 준비 요약서'를 한국어 존댓말로 작성해 주세요.

형식:
# 상담 준비 요약서
## 1. 사건 개요 (2~3문장)
## 2. 시간순 경위
## 3. 확보한 증거 / 확보 예정 증거
## 4. 상담에서 확인하고 싶은 점
## 5. 관련될 수 있는 법령·판례 (대화에 등장한 것만)

원칙: 사용자가 말한 사실만 정리하고, 새로운 법적 판단이나 조언을 추가하지 마세요. 알 수 없는 항목은 "(직접 기재해 주세요)"로 남겨 주세요. 마지막에 "※ 본 요약서는 이용자 진술을 정리한 것으로 법률 자문이 아닙니다."를 붙여 주세요."""


def summary_fallback(messages: list[dict]) -> str:
    """No-API-key mode: organize the user's own statements into the template."""
    user_lines = [m["text"] for m in messages if m.get("role") == "user"]
    stated = "\n".join(f"- {t}" for t in user_lines) or "- (직접 기재해 주세요)"
    return (
        "# 상담 준비 요약서\n\n"
        "## 1. 사건 개요\n(직접 기재해 주세요)\n\n"
        "## 2. 시간순 경위 — 이 대화에서 말씀하신 내용\n" + stated + "\n\n"
        "## 3. 확보한 증거 / 확보 예정 증거\n- (직접 기재해 주세요)\n\n"
        "## 4. 상담에서 확인하고 싶은 점\n- (직접 기재해 주세요)\n\n"
        "※ 본 요약서는 이용자 진술을 정리한 것으로 법률 자문이 아닙니다.\n"
    )


@app.post("/api/summary")
def summary(req: SummaryRequest, x_anthropic_key: str | None = Header(default=None)):
    api_key = os.environ.get("ANTHROPIC_API_KEY") or (x_anthropic_key or "").strip() or None
    if not api_key:
        return {"content": summary_fallback(req.messages), "generated": False}
    import anthropic

    transcript = "\n".join(
        f"[{'사용자' if m.get('role') == 'user' else 'AI'}] {m.get('text', '')}" for m in req.messages
    )
    try:
        msg = anthropic.Anthropic(api_key=api_key).messages.create(
            model=os.environ.get("LEGAL_AI_MODEL", "claude-sonnet-4-5"),
            max_tokens=1500,
            system=SUMMARY_PROMPT,
            messages=[{"role": "user", "content": transcript}],
        )
        return {"content": msg.content[0].text, "generated": True}
    except Exception:
        return {"content": summary_fallback(req.messages), "generated": False}


CHECKLISTS = json.loads((ROOT / "data" / "checklists.json").read_text(encoding="utf-8"))
TEMPLATES_DIR = ROOT / "templates"


@app.get("/api/checklists")
def checklists():
    return {k: v["label"] for k, v in CHECKLISTS.items()}


@app.get("/api/checklists/{crime_type}")
def checklist(crime_type: str):
    if crime_type not in CHECKLISTS:
        return {"error": "unknown crime type"}
    return CHECKLISTS[crime_type]


@app.get("/api/templates/{name}")
def template(name: str):
    safe = {"cctv": "cctv_보존요청서.md", "complaint": "고소장.md"}
    if name not in safe:
        return {"error": "unknown template"}
    return {"name": safe[name], "content": (TEMPLATES_DIR / safe[name]).read_text(encoding="utf-8")}


PROCEDURE = json.loads((ROOT / "data" / "procedure.json").read_text(encoding="utf-8"))
DEADLINES = json.loads((ROOT / "data" / "deadlines.json").read_text(encoding="utf-8"))


class ClientError(BaseModel):
    message: str
    stack: str | None = None
    url: str | None = None


@app.post("/api/client-error")
def client_error(err: ClientError):
    """Frontend crash reports (no user content). Grep logs for client_error to
    compute the crash-free session metric."""
    logger.warning(
        "client_error message=%r url=%r stack=%r",
        err.message[:300], (err.url or "")[:200], (err.stack or "")[:500],
    )
    return {"ok": True}


@app.get("/api/procedure")
def procedure():
    return PROCEDURE


@app.get("/api/deadlines")
def deadlines():
    return DEADLINES


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "articles": len(retriever.articles),
        "data": retriever.path.name,
        "generation": bool(os.environ.get("ANTHROPIC_API_KEY")),
    }

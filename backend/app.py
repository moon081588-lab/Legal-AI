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

from collections import defaultdict  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402
from typing import Literal  # noqa: E402

import anyio  # noqa: E402
from fastapi import FastAPI, Header, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse, StreamingResponse  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from backend import __version__, schemas  # noqa: E402
from backend.rag.answer import SYSTEM_PROMPT, build_user_prompt, option_instructions  # noqa: E402
from backend.rag.retrieve import Retriever  # noqa: E402
from backend.rag.verify import verify_citations  # noqa: E402

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

# 샘플 말뭉치 안전장치.
#
# data/corpus/sample/ 은 개발용으로 손으로 쓴 가짜 조문입니다. 실제 데이터를 아직
# 수집하지 않았다면 Retriever 가 조용히 이 샘플로 대체되는데, 그 상태로 배포하면
# 범죄 피해자에게 존재하지 않는 법을 법이라고 보여 주게 됩니다. 이 프로젝트에서
# 일어날 수 있는 가장 나쁜 일이므로, 개발 환경이 아니면 아예 기동하지 않습니다.
DEV_ENVS = {"development", "dev", "local", "test", "ci"}
LEGAL_AI_ENV = os.environ.get("LEGAL_AI_ENV", "development").strip().lower()


class SampleCorpusError(RuntimeError):
    """Raised at startup when a non-development instance would serve fixture data."""


def assert_corpus_releasable(corpus_mode: str, env: str) -> None:
    if corpus_mode != "sample" or env in DEV_ENVS:
        return
    raise SampleCorpusError(
        f"샘플 법령 데이터로는 기동할 수 없습니다 (LEGAL_AI_ENV={env}).\n"
        "지금 적재된 조문은 data/corpus/sample/ 의 개발용 가짜 데이터입니다.\n\n"
        "해결 방법:\n"
        "  1) 실제 법령을 수집하세요\n"
        "     export LAW_GO_KR_OC=<open.law.go.kr 가입 아이디>\n"
        "     python tools/ingest/fetch_laws.py && python tools/ingest/parse_laws.py\n"
        "     python tools/ingest/fetch_precedents.py\n"
        "  2) 또는 GitHub Actions 의 주간 수집 워크플로(.github/workflows/ingest.yml)를 수동 실행하세요\n"
        "  3) 의도적으로 샘플을 띄우는 개발용 시연이라면 LEGAL_AI_ENV=development 로 실행하세요"
    )


_state = {"ready": False, "shutting_down": False, "active_streams": 0}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Data loads at import time; flip readiness only once that succeeded AND the
    # data files match their schemas. Bad data means this instance never takes
    # traffic (readiness stays 503) instead of 500-ing real users.
    from backend.schemas import validate_data_files

    data_ok = True
    try:
        counts = validate_data_files()
        logger.info("data validated %s", counts)
    except Exception as e:
        data_ok = False
        logger.error("data validation FAILED: %s", e)

    _state["ready"] = data_ok and len(retriever.articles) > 0
    logger.info("startup ready=%s articles=%d", _state["ready"], len(retriever.articles))
    yield
    # Drain: stop accepting traffic, let in-flight streams finish so nobody
    # gets an answer cut off mid-sentence.
    _state["shutting_down"] = True
    _state["ready"] = False
    for _ in range(100):  # up to ~10s
        if _state["active_streams"] <= 0:
            break
        await anyio.sleep(0.1)
    logger.info("shutdown complete active_streams=%d", _state["active_streams"])


app = FastAPI(title="Legal-AI", version=__version__, lifespan=lifespan)
# Comma-separated origins, e.g. "https://legal-ai.vercel.app,http://localhost:3000".
ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get("LEGAL_AI_ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

retriever = Retriever()
assert_corpus_releasable(retriever.corpus_mode, LEGAL_AI_ENV)
if retriever.corpus_mode == "sample":
    logger.warning(
        "샘플 법령 데이터로 실행 중입니다 (env=%s). 답변에 인용되는 조문은 실제 법이 아닙니다. "
        "실제 데이터 수집: python tools/ingest/fetch_laws.py",
        LEGAL_AI_ENV,
    )


MAX_QUESTION_CHARS = 2000
MAX_SUMMARY_MESSAGES = 100
RATE_LIMIT_PER_MIN = int(os.environ.get("LEGAL_AI_RATE_LIMIT", "20"))


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=MAX_QUESTION_CHARS)
    lang: Literal["ko", "en"] = "ko"
    simple: bool = False


class SummaryRequest(BaseModel):
    messages: list[dict] = Field(max_length=MAX_SUMMARY_MESSAGES)


# Simple in-process rate limiter: protects a single-instance deployment from
# runaway clients. Replace with Redis if you ever run multiple workers.
_hits: dict[str, list[float]] = defaultdict(list)


def rate_limited(request: Request) -> bool:
    ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    recent = [t for t in _hits[ip] if now - t < 60]
    recent.append(now)
    _hits[ip] = recent
    if len(_hits) > 10_000:  # bound memory
        _hits.clear()
    return len(recent) > RATE_LIMIT_PER_MIN


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


class CircuitBreaker:
    """After repeated model-API failures, stop calling it for a cooldown period
    and serve retrieval-only answers instead. Degrade, don't break."""

    def __init__(self, threshold: int = 3, cooldown_s: int = 60):
        self.threshold = threshold
        self.cooldown_s = cooldown_s
        self.failures = 0
        # None means "never opened". Must not be 0.0: time.monotonic() counts from
        # boot, so on a freshly started machine 0.0 reads as "opened just now".
        self.opened_at: float | None = None

    @property
    def is_open(self) -> bool:
        if self.failures < self.threshold or self.opened_at is None:
            return False
        if time.monotonic() - self.opened_at > self.cooldown_s:
            self.reset()  # half-open: allow one probe request through
            return False
        return True

    def record_failure(self) -> None:
        self.failures += 1
        if self.failures >= self.threshold:
            self.opened_at = time.monotonic()
            logger.warning("circuit_breaker opened failures=%d", self.failures)

    def record_success(self) -> None:
        if self.failures:
            logger.info("circuit_breaker closed after %d failures", self.failures)
        self.reset()

    def reset(self) -> None:
        self.failures = 0
        self.opened_at = None

    def state(self) -> str:
        return "open" if self.is_open else ("degraded" if self.failures else "closed")


breaker = CircuitBreaker()

DEGRADED_NOTICE = (
    "\n\n※ 현재 답변 생성 서비스에 일시적인 문제가 있어 관련 조문 원문만 안내드렸습니다. "
    "잠시 후 다시 시도해 주세요.\n"
)

# Vague openers → the follow-ups a real intake interview would ask.
TRIAGE_RULES = [
    (("사기", "속았", "돈을 보냈"), [
        "온라인 거래였나요, 직접 만나서 이루어진 일인가요?",
        "송금·이체를 하셨다면 언제, 어떤 방법으로 하셨나요?",
        "상대방의 계좌번호나 연락처를 알고 계신가요?",
    ]),
    (("맞았", "폭행", "때렸"), [
        "병원 진료를 받으셨나요? 진단서가 있으신가요?",
        "사건이 발생한 장소 주변에 CCTV가 있었나요?",
        "목격자가 있었나요?",
    ]),
    (("스토킹", "따라와", "계속 연락"), [
        "언제부터 어느 정도 빈도로 반복되고 있나요?",
        "연락 기록(문자·전화·메신저)을 보관하고 계신가요?",
        "경찰에 신고하신 적이 있나요?",
    ]),
    (("해고", "잘렸", "짤렸"), [
        "해고 통보를 언제, 어떤 방식(구두·서면)으로 받으셨나요?",
        "근무 기간은 얼마나 되시나요?",
    ]),
    (("보증금", "전세", "월세"), [
        "임대차 계약이 이미 종료되었나요?",
        "전입신고와 확정일자를 받아 두셨나요?",
    ]),
]
VAGUE_MAX_CHARS = 25


def triage_questions(question: str) -> list[str]:
    """Return clarifying questions only when the question is short and generic —
    a detailed question should be answered, not interrogated."""
    if len(question) > VAGUE_MAX_CHARS:
        return []
    for keywords, follow_ups in TRIAGE_RULES:
        if any(k in question for k in keywords):
            return follow_ups[:3]
    return []


_SENTINEL = object()


async def _aiter_sync(sync_gen):
    """Consume a blocking generator without occupying an event-loop worker:
    each next() runs in a thread, so many concurrent streams stay responsive."""
    it = iter(sync_gen)

    def _next():
        try:
            return next(it)
        except StopIteration:
            return _SENTINEL

    while True:
        item = await anyio.to_thread.run_sync(_next)
        if item is _SENTINEL:
            return
        yield item


@app.post("/api/chat")
async def chat(req: ChatRequest, request: Request, x_anthropic_key: str | None = Header(default=None)):
    question = req.question.strip()
    api_key = (x_anthropic_key or "").strip() or None

    if rate_limited(request):
        async def limited():
            yield sse("sources", [])
            yield sse("delta", {"text": "요청이 너무 많습니다. 잠시 후 다시 시도해 주세요."})
            yield sse("done", {"ttft_ms": 0, "total_ms": 0})
        logger.info("chat route=rate_limited")
        return StreamingResponse(limited(), media_type="text/event-stream")

    async def generate():
        # Latency metrics: logged without question content, and returned in the
        # `done` event so the client can also report them.
        t0 = time.monotonic()
        ttft_ms: int | None = None
        _state["active_streams"] += 1
        try:
            async for chunk in _generate_body(t0, ttft_ms):
                yield chunk
        finally:
            _state["active_streams"] -= 1

    async def _generate_body(t0: float, ttft_ms: int | None):

        if any(p in question for p in CRISIS_PATTERNS):
            yield sse("delta", {"text": CRISIS_MESSAGE + "\n"})

        if any(p in question for p in OUT_OF_SCOPE_PATTERNS):
            yield sse("sources", [])
            yield sse("delta", {"text": OUT_OF_SCOPE_MESSAGE})
            yield sse("done", {"ttft_ms": 0, "total_ms": int((time.monotonic() - t0) * 1000)})
            logger.info("chat route=out_of_scope total_ms=%d", (time.monotonic() - t0) * 1000)
            return

        # Triage: a very vague question retrieves poorly. Ask for the one or two
        # details that would actually change the answer, then still answer.
        clarify = triage_questions(question)
        if clarify:
            yield sse("clarify", clarify)

        articles = await anyio.to_thread.run_sync(retriever.search, question, 5)
        yield sse("sources", [
            {k: a[k] for k in ("law_name", "article_no", "article_title", "text", "source_url")}
            for a in articles
        ])

        full_answer = ""
        has_key = bool(os.environ.get("ANTHROPIC_API_KEY") or api_key)
        generated = has_key and not breaker.is_open
        if generated:
            try:
                stream = stream_claude(question, articles, api_key, req.lang, req.simple)
                async for text in _aiter_sync(stream):
                    if ttft_ms is None:
                        ttft_ms = int((time.monotonic() - t0) * 1000)
                    full_answer += text
                    yield sse("delta", {"text": text})
                breaker.record_success()
            except Exception as e:
                breaker.record_failure()
                logger.warning("chat generation_error=%s", type(e).__name__)
                if not full_answer:  # nothing streamed yet — degrade to retrieval
                    yield sse("delta", {"text": fallback_answer(articles) + DEGRADED_NOTICE})
                else:
                    yield sse("delta", {"text": "\n\n답변 생성이 중단되었습니다. 잠시 후 다시 시도해 주세요."})
        else:
            ttft_ms = int((time.monotonic() - t0) * 1000)
            text = fallback_answer(articles)
            if has_key and breaker.is_open:
                text += DEGRADED_NOTICE
            yield sse("delta", {"text": text})

        if full_answer:
            result = verify_citations(full_answer, articles)
            yield sse("verified", result)
            if not result["ok"]:
                warn = ", ".join(result["unknown"])
                yield sse("delta", {"text": f"\n\n⚠️ 다음 인용은 검색된 근거에서 확인되지 않았습니다. 원문을 직접 확인해 주세요: {warn}"})

        total_ms = int((time.monotonic() - t0) * 1000)
        yield sse("done", {"ttft_ms": ttft_ms, "total_ms": total_ms})
        logger.info(
            "chat route=rag generated=%s breaker=%s sources=%d ttft_ms=%s total_ms=%d",
            generated, breaker.state(), len(articles), ttft_ms, total_ms,
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
    user_lines = [
        str(m.get("text", "")).strip()
        for m in messages
        if isinstance(m, dict) and m.get("role") == "user" and str(m.get("text", "")).strip()
    ]
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
        f"[{'사용자' if m.get('role') == 'user' else 'AI'}] {str(m.get('text', ''))}"
        for m in req.messages
        if isinstance(m, dict)
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


CHECKLISTS = json.loads((ROOT / "data" / "content" / "checklists.json").read_text(encoding="utf-8"))
TEMPLATES_DIR = ROOT / "data" / "content" / "templates"


# Data files carry provenance metadata alongside their content. Never treat these
# top-level keys as content — doing so crashed /api/checklists once `verified_on`
# was added, taking the whole 증거 체크리스트 feature down.
META_KEYS = {"note", "sources", "verified_on"}


@app.get("/api/checklists", response_model=dict[str, str])
def checklists():
    return {
        k: v["label"]
        for k, v in CHECKLISTS.items()
        if k not in META_KEYS and isinstance(v, dict) and "label" in v
    }


@app.get("/api/checklists/{crime_type}", response_model=schemas.Checklist)
def checklist(crime_type: str):
    entry = CHECKLISTS.get(crime_type)
    if crime_type in META_KEYS or not isinstance(entry, dict) or "label" not in entry:
        return JSONResponse(status_code=404, content={"error": "unknown crime type"})
    return entry


@app.get("/api/templates/{name}")
def template(name: str):
    safe = {"cctv": "cctv_보존요청서.md", "complaint": "고소장.md"}
    if name not in safe:
        return {"error": "unknown template"}
    return {"name": safe[name], "content": (TEMPLATES_DIR / safe[name]).read_text(encoding="utf-8")}


PROCEDURE = json.loads((ROOT / "data" / "content" / "procedure.json").read_text(encoding="utf-8"))
DEADLINES = json.loads((ROOT / "data" / "content" / "deadlines.json").read_text(encoding="utf-8"))
SUPPORT = json.loads((ROOT / "data" / "content" / "support.json").read_text(encoding="utf-8"))
CENTERS = json.loads((ROOT / "data" / "content" / "centers.json").read_text(encoding="utf-8"))
GLOSSARY = json.loads((ROOT / "data" / "content" / "glossary.json").read_text(encoding="utf-8"))


class EligibilityRequest(BaseModel):
    answers: dict = Field(default_factory=dict)


@app.get("/api/support/questions", response_model=schemas.SupportQuestionsResponse)
def support_questions():
    return {"note": SUPPORT["note"], "questions": SUPPORT["questions"]}


@app.post("/api/support/match", response_model=schemas.SupportMatchResponse)
def support_match(req: EligibilityRequest):
    """Match answers to support programs. A program matches when every declared
    criterion is satisfied; programs with no criteria always apply."""
    answers = {k: str(v) for k, v in req.answers.items() if isinstance(k, str)}
    matched, others = [], []
    for p in SUPPORT["programs"]:
        rules = p.get("match", {})
        ok = all(answers.get(field) in allowed for field, allowed in rules.items())
        (matched if ok else others).append({k: v for k, v in p.items() if k != "match"})

    notes = []
    if answers.get("when") == "old" and any(p["id"].startswith("compensation") for p in SUPPORT["programs"]):
        notes.append(SUPPORT["deadline_notice"]["compensation"])
    return {
        "matched": matched,
        "others": others,
        "notes": notes,
        "disclaimer": SUPPORT["note"],
        "sources": SUPPORT.get("sources", []),
        "verified_on": SUPPORT.get("verified_on"),
    }


@app.get("/api/centers", response_model=schemas.CentersFile)
def centers():
    return CENTERS


@app.get("/api/glossary", response_model=dict[str, str])
def glossary():
    return {k: v for k, v in GLOSSARY.items() if k not in META_KEYS and isinstance(v, str)}


class Feedback(BaseModel):
    helpful: bool
    question: str = Field(default="", max_length=MAX_QUESTION_CHARS)
    reason: str = Field(default="", max_length=500)


@app.post("/api/feedback")
def feedback(fb: Feedback):
    """Negative feedback becomes an eval candidate. Only the question text is
    kept — never the answer, and never anything the user typed about themselves
    beyond the question they chose to send."""
    logger.info("feedback helpful=%s reason=%r", fb.helpful, fb.reason[:200])
    if not fb.helpful and fb.question.strip():
        path = ROOT / "data" / "feedback" / "candidates.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(
                {"question": fb.question.strip(), "reason": fb.reason.strip(),
                 "expected_law": None, "expected_articles": []},
                ensure_ascii=False) + "\n")
    return {"ok": True}


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


@app.get("/api/procedure", response_model=schemas.ProcedureFile)
def procedure():
    return PROCEDURE


@app.get("/api/deadlines", response_model=schemas.DeadlinesFile)
def deadlines():
    return DEADLINES


@app.get("/api/livez")
def livez():
    """Liveness: is the process running? (restart if this fails)"""
    return {"status": "alive"}


@app.get("/api/readyz")
def readyz():
    """Readiness: should this instance receive traffic? (data loaded, not draining)"""
    ready = _state["ready"] and not _state["shutting_down"]
    return JSONResponse(
        status_code=200 if ready else 503,
        content={
            "ready": ready,
            "articles": len(retriever.articles),
            "corpus": retriever.corpus_mode,
            "shutting_down": _state["shutting_down"],
            "active_streams": _state["active_streams"],
            "breaker": breaker.state(),
        },
    )


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        # 배포된 버전을 외부에서 확인할 수 있게 노출합니다(연기 테스트와 장애 대응에 사용).
        "version": __version__,
        # `data` 는 파일 이름이라 샘플과 실제를 구분하지 못합니다(둘 다 articles.jsonl).
        # 구분은 `corpus` 값("real" | "sample")으로 하세요. 연기 테스트가 이 값을 검사합니다.
        "data": retriever.path.name,
        "env": LEGAL_AI_ENV,
        "generation": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "rate_limit_per_min": RATE_LIMIT_PER_MIN,
        **retriever.stats(),
    }

"""Chaos / fault-injection tests: the app must degrade, never white-screen.

    python -m pytest backend/test_chaos.py -q
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from backend import app as app_module  # noqa: E402
from backend.app import app  # noqa: E402
from ingest.safe_write import IngestGuardError, safe_write, validate, verify_checksum  # noqa: E402

client = TestClient(app)


def _text(resp):
    return "".join(
        line[6:] for line in resp.text.splitlines() if line.startswith("data: ")
    )


@pytest.fixture(autouse=True)
def _reset_breaker():
    app_module.breaker.reset()
    yield
    app_module.breaker.reset()


# ---------- model API failures ----------

def test_model_failure_degrades_to_retrieval(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("simulated API outage")
        yield  # pragma: no cover

    monkeypatch.setattr(app_module, "stream_claude", boom)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    r = client.post("/api/chat", json={"question": "전세 보증금을 못 돌려받고 있어요"})
    body = _text(r)
    assert r.status_code == 200
    assert "주택임대차보호법" in body      # still served real statutes
    assert "일시적인 문제" in body          # and told the user honestly


def test_repeated_failures_open_breaker(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("outage")
        yield  # pragma: no cover

    monkeypatch.setattr(app_module, "stream_claude", boom)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    for _ in range(3):
        client.post("/api/chat", json={"question": "테스트 질문입니다"})
    assert app_module.breaker.is_open
    # With the breaker open we no longer call the API at all, but still answer.
    r = client.post("/api/chat", json={"question": "폭행을 당했어요"})
    assert "증거" in _text(r) or "형사소송법" in _text(r)
    assert client.get("/api/readyz").json()["breaker"] == "open"


def test_breaker_recovers_after_cooldown(monkeypatch):
    app_module.breaker.failures = 3
    app_module.breaker.opened_at = 0.0  # long past → half-open
    assert not app_module.breaker.is_open


# ---------- retrieval failures ----------

def test_no_retrieval_results_still_answers(monkeypatch):
    monkeypatch.setattr(app_module.retriever, "search", lambda *a, **k: [])
    r = client.post("/api/chat", json={"question": "관련 없는 질문 zzzz"})
    body = _text(r)
    assert r.status_code == 200
    assert "찾지 못했습니다" in body
    assert "132" in body  # always routes to human help


# ---------- malformed input ----------

@pytest.mark.parametrize("payload", [
    {},                                   # missing question
    {"question": ""},                     # empty
    {"question": "가" * 5000},            # too long
    {"question": "정상", "lang": "xx"},   # bad language code
    {"question": "정상", "simple": "네"},  # wrong type
])
def test_malformed_requests_rejected_cleanly(payload):
    r = client.post("/api/chat", json=payload)
    assert r.status_code == 422  # never a 500


def test_summary_with_garbage_messages():
    r = client.post("/api/summary", json={"messages": [{"nope": 1}, {"role": "user"}]})
    assert r.status_code == 200
    assert "상담 준비 요약서" in r.json()["content"]


# ---------- ingestion guards ----------

def test_validate_rejects_empty_and_broken_records():
    with pytest.raises(IngestGuardError):
        validate([])
    with pytest.raises(IngestGuardError):
        validate([{"law_name": "법", "article_no": "제1조", "text": ""}] * 10)


def test_safe_write_refuses_catastrophic_shrink(tmp_path):
    target = tmp_path / "articles.jsonl"
    good = [{"law_name": "형사소송법", "article_no": f"제{i}조", "text": "조문 내용입니다 " * 3}
            for i in range(50)]
    safe_write(good, target, force=True)

    tiny = good[:5]  # simulates a throttled/broken API response
    with pytest.raises(IngestGuardError):
        safe_write(tiny, target)
    # original data untouched
    assert len(target.read_text(encoding="utf-8").strip().splitlines()) == 50


def test_safe_write_is_atomic_and_checksummed(tmp_path):
    target = tmp_path / "articles.jsonl"
    records = [{"law_name": "형사소송법", "article_no": f"제{i}조", "text": "본문 내용 " * 3}
               for i in range(30)]
    report = safe_write(records, target, force=True)
    assert report["written"] == 30
    assert verify_checksum(target)
    assert not list(tmp_path.glob("*.tmp"))  # no half-written leftovers

    target.write_text(json.dumps({"tampered": True}), encoding="utf-8")
    assert not verify_checksum(target)  # corruption detected


def test_snapshot_enables_rollback(tmp_path, monkeypatch):
    import ingest.safe_write as sw

    monkeypatch.setattr(sw, "SNAPSHOT_DIR", tmp_path / "snapshots")
    target = tmp_path / "articles.jsonl"
    v1 = [{"law_name": "법", "article_no": f"제{i}조", "text": "버전1 내용 " * 3} for i in range(20)]
    sw.safe_write(v1, target, force=True)
    v2 = [{"law_name": "법", "article_no": f"제{i}조", "text": "버전2 내용 " * 3} for i in range(20)]
    report = sw.safe_write(v2, target, force=True)

    assert report["snapshot"] and Path(report["snapshot"]).exists()
    restored = sw.load_existing(Path(report["snapshot"]))
    assert "버전1" in restored[0]["text"]

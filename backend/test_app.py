"""Backend tests: python -m pytest backend/test_app.py -q  (from repo root)"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from backend.app import app

client = TestClient(app)


def _events(resp):
    events = []
    for block in resp.text.strip().split("\n\n"):
        lines = dict(l.split(": ", 1) for l in block.splitlines() if ": " in l)
        if "event" in lines:
            events.append((lines["event"], lines.get("data", "")))
    return events


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["articles"] > 0


def test_chat_returns_sources_and_answer():
    r = client.post("/api/chat", json={"question": "전세 보증금을 못 돌려받고 있어요"})
    assert r.status_code == 200
    events = _events(r)
    names = [e for e, _ in events]
    assert "sources" in names and "delta" in names and names[-1] == "done"
    sources = next(d for e, d in events if e == "sources")
    assert "주택임대차보호법" in sources


def test_crisis_message_leads_response():
    r = client.post("/api/chat", json={"question": "남편에게 지금 맞고 있어요 어떻게 하죠"})
    events = _events(r)
    answer = "".join(d for e, d in events if e == "delta")
    assert "112" in answer
    assert "1366" in answer
    # legal information still follows
    assert any(e == "sources" for e, _ in events)


def test_out_of_scope_is_refused():
    r = client.post("/api/chat", json={"question": "제가 소송하면 이길 수 있을까요?"})
    events = _events(r)
    answer = "".join(d for e, d in events if e == "delta")
    assert "변호사" in answer
    assert "132" in answer


def test_summary_fallback_organizes_user_statements():
    r = client.post("/api/summary", json={"messages": [
        {"role": "user", "text": "지난주에 폭행을 당했습니다"},
        {"role": "bot", "text": "안내드립니다..."},
    ]})
    data = r.json()
    assert "상담 준비 요약서" in data["content"]
    assert "폭행을 당했습니다" in data["content"]
    assert "법률 자문이 아닙니다" in data["content"]


def test_long_question_is_rejected():
    r = client.post("/api/chat", json={"question": "가" * 3000})
    assert r.status_code == 422


def test_invalid_lang_is_rejected():
    r = client.post("/api/chat", json={"question": "테스트", "lang": "xx"})
    assert r.status_code == 422


def test_retrieval_cache_returns_equal_results():
    from rag.retrieve import Retriever

    r = Retriever()
    a = r.search("전세 보증금", k=5)
    b = r.search("전세 보증금", k=5)
    assert [x["article_no"] for x in a] == [x["article_no"] for x in b]
    assert r.stats()["cache_entries"] >= 1
    b[0]["text"] = "mutated"          # cache must hand out copies
    assert r.search("전세 보증금", k=5)[0]["text"] != "mutated"


def test_procedure_and_deadlines_endpoints():
    stages = client.get("/api/procedure").json()["stages"]
    assert any("이의신청" in s["title"] for s in stages)
    rules = client.get("/api/deadlines").json()["rules"]
    assert any(r["id"] == "cctv" and r.get("days") == 30 for r in rules)

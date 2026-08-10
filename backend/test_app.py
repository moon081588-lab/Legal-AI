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


def test_out_of_scope_is_refused():
    r = client.post("/api/chat", json={"question": "제가 소송하면 이길 수 있을까요?"})
    events = _events(r)
    answer = "".join(d for e, d in events if e == "delta")
    assert "변호사" in answer
    assert "132" in answer

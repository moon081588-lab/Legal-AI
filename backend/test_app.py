"""Backend tests: python -m pytest backend/test_app.py -q  (from repo root)"""

import sys
from pathlib import Path

import pytest

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


def test_support_match_sexual_violence_gets_free_counsel():
    r = client.post("/api/support/match", json={"answers": {"crime_type": "sexual", "harm": "minor"}})
    ids = [p["id"] for p in r.json()["matched"]]
    assert "victim_counsel" in ids   # 소득 무관 무료 국선변호사
    assert "sunflower" in ids
    assert "klac_consult" in ids     # 항상 안내되는 무료 상담


def test_support_match_death_gets_compensation():
    r = client.post("/api/support/match", json={"answers": {"harm": "death", "when": "recent"}})
    matched = r.json()["matched"]
    assert any(p["id"] == "compensation_death" for p in matched)
    assert any("1577-2584" in p["contact"] for p in matched)


def test_support_match_handles_empty_answers():
    r = client.post("/api/support/match", json={"answers": {}})
    assert r.status_code == 200
    assert any(p["id"] == "klac_consult" for p in r.json()["matched"])


def test_every_support_program_cites_a_source():
    """User-facing legal/benefit claims must be verifiable — no unsourced advice."""
    r = client.post("/api/support/match", json={"answers": {}})
    data = r.json()
    for p in data["matched"] + data["others"]:
        assert p.get("sources"), f"{p['id']} 에 출처가 없습니다"
        for s in p["sources"]:
            assert s["url"].startswith("https://")
    assert data["sources"] and data["verified_on"]


def test_checklist_index_lists_only_crime_types():
    """Regression: adding `verified_on` to checklists.json made this endpoint
    500 (string indices...), which broke the whole 증거 체크리스트 feature."""
    r = client.get("/api/checklists")
    assert r.status_code == 200
    listed = r.json()
    assert set(listed) == {"assault", "fraud", "stalking", "sexual"}
    assert "verified_on" not in listed and "sources" not in listed
    assert all(isinstance(v, str) for v in listed.values())


def test_every_listed_checklist_is_fetchable():
    """The index and detail endpoints must agree — that pairing is what broke."""
    for crime in client.get("/api/checklists").json():
        detail = client.get(f"/api/checklists/{crime}")
        assert detail.status_code == 200, crime
        assert detail.json()["label"]
        assert detail.json()["items"]


@pytest.mark.parametrize("bad", ["verified_on", "sources", "note", "does_not_exist"])
def test_metadata_keys_are_not_valid_checklists(bad):
    assert client.get(f"/api/checklists/{bad}").status_code == 404


def test_glossary_excludes_metadata_keys(monkeypatch):
    import backend.app as m

    monkeypatch.setitem(m.GLOSSARY, "verified_on", "2026-08-11")
    monkeypatch.setitem(m.GLOSSARY, "sources", [{"label": "x", "url": "https://x"}])
    terms = client.get("/api/glossary").json()
    assert "verified_on" not in terms and "sources" not in terms
    assert "불송치" in terms


def test_reference_datasets_carry_sources():
    for path in ("/api/procedure", "/api/deadlines", "/api/centers"):
        data = client.get(path).json()
        assert data.get("sources"), f"{path} 에 출처가 없습니다"
        assert data.get("verified_on"), f"{path} 에 확인일이 없습니다"
    for crime in ("assault", "fraud", "stalking", "sexual"):
        assert client.get(f"/api/checklists/{crime}").json().get("sources")


def test_centers_and_glossary():
    hot = client.get("/api/centers").json()["hotlines"]
    assert any(h["phone"] == "112" for h in hot)
    assert any(h["phone"] == "1366" for h in hot)
    terms = client.get("/api/glossary").json()
    assert "불송치" in terms and "증거보전" in terms


def test_feedback_records_negative_as_eval_candidate(tmp_path, monkeypatch):
    import backend.app as m

    monkeypatch.setattr(m, "ROOT", tmp_path)
    r = client.post("/api/feedback", json={"helpful": False, "question": "테스트 질문", "reason": "부정확"})
    assert r.json()["ok"]
    written = (tmp_path / "evals" / "candidates.jsonl").read_text(encoding="utf-8")
    assert "테스트 질문" in written


def test_positive_feedback_is_not_stored_as_candidate(tmp_path, monkeypatch):
    import backend.app as m

    monkeypatch.setattr(m, "ROOT", tmp_path)
    client.post("/api/feedback", json={"helpful": True, "question": "좋은 답변"})
    assert not (tmp_path / "evals" / "candidates.jsonl").exists()


def test_triage_only_for_short_vague_questions():
    from backend.app import triage_questions

    assert triage_questions("사기당했어요")
    assert not triage_questions(
        "온라인 중고거래로 30만원을 송금했는데 물건을 받지 못했고 상대방이 연락을 끊었습니다"
    )


def test_procedure_and_deadlines_endpoints():
    stages = client.get("/api/procedure").json()["stages"]
    assert any("이의신청" in s["title"] for s in stages)
    rules = client.get("/api/deadlines").json()["rules"]
    assert any(r["id"] == "cctv" and r.get("days") == 30 for r in rules)

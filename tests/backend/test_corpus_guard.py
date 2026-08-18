"""샘플 말뭉치 안전장치 테스트.

이 저장소에서 가장 비싼 실수는 개발용 샘플 조문을 실제 법령인 것처럼 배포하는
것입니다. 두 파일 모두 이름이 articles.jsonl 이라 눈으로는 구분되지 않으므로,
구분과 차단이 코드로 강제되는지 확인합니다.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from backend.app import DEV_ENVS, SampleCorpusError, app, assert_corpus_releasable  # noqa: E402
from backend.rag.retrieve import Retriever  # noqa: E402

client = TestClient(app)


def test_sample_fixture_is_detected_as_sample():
    r = Retriever(ROOT / "data" / "corpus" / "sample" / "articles.jsonl")
    assert r.corpus_mode == "sample"


def test_sample_marker_detected_even_outside_sample_directory(tmp_path):
    """샘플 파일을 sample/ 밖으로 복사해도 SAMPLE 표식으로 잡혀야 합니다."""
    src = ROOT / "data" / "corpus" / "sample" / "articles.jsonl"
    copied = tmp_path / "articles.jsonl"
    copied.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    assert Retriever(copied).corpus_mode == "sample"


def _write_real_corpus(path: Path, law_id: str = "001766") -> Path:
    record = {
        "law_name": "주택임대차보호법",
        "law_id": law_id,
        "article_no": "제3조",
        "article_title": "대항력 등",
        "text": "임대차는 그 등기가 없는 경우에도 임차인이 주택의 인도와 주민등록을 마친 때에는 효력이 생긴다.",
        "effective_date": "20230719",
        "source_url": "https://www.law.go.kr/법령/주택임대차보호법/제3조",
    }
    path.write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def test_real_articles_with_sample_precedents_is_still_sample(tmp_path, monkeypatch):
    """조문만 진짜고 판례가 샘플이면 여전히 sample 입니다.

    판례도 사용자에게 근거로 인용되므로, 한 종류라도 가짜면 배포할 수 없습니다.

    실제 판례를 수집했는지 여부와 무관하게 같은 결과가 나와야 하므로, 판례 경로를
    샘플로 고정합니다. 고정하지 않으면 수집 전에는 통과하고 수집 후에는 실패하는,
    개발자의 로컬 상태에 따라 결과가 달라지는 테스트가 됩니다.
    """
    import backend.rag.retrieve as retrieve_mod

    monkeypatch.setattr(retrieve_mod, "PREC_DATA", tmp_path / "does-not-exist.jsonl")
    r = Retriever(_write_real_corpus(tmp_path / "articles.jsonl"))
    assert r.sources["precedents"].parent.name == "sample"
    assert r.corpus_mode == "sample"


def test_fully_real_corpus_is_detected_as_real(tmp_path, monkeypatch):
    """반대 방향도 확인합니다. 안전장치가 무조건 sample 로 답하면 쓸모가 없습니다."""
    import backend.rag.retrieve as retrieve_mod

    prec = tmp_path / "precedents.jsonl"
    _write_real_corpus(prec, law_id="PREC-2001도3106")
    monkeypatch.setattr(retrieve_mod, "PREC_DATA", prec)
    monkeypatch.setattr(retrieve_mod, "PREC_SAMPLE", prec)

    r = Retriever(_write_real_corpus(tmp_path / "articles.jsonl"))
    assert r.corpus_mode == "real"
    assert r.stats()["corpus"] == "real"


@pytest.mark.parametrize("env", sorted(DEV_ENVS))
def test_sample_allowed_in_development(env):
    assert_corpus_releasable("sample", env)  # 예외가 나지 않아야 합니다


@pytest.mark.parametrize("env", ["production", "prod", "staging"])
def test_sample_blocked_outside_development(env):
    with pytest.raises(SampleCorpusError) as e:
        assert_corpus_releasable("sample", env)
    # 오류 메시지는 새벽 3시에 읽힙니다. 해결 방법이 들어 있어야 합니다.
    assert "fetch_laws.py" in str(e.value)


def test_real_corpus_always_allowed():
    assert_corpus_releasable("real", "production")


def test_health_exposes_corpus_mode():
    body = client.get("/api/health").json()
    assert body["corpus"] in ("real", "sample")
    assert "env" in body


def test_readyz_exposes_corpus_mode():
    assert client.get("/api/readyz").json()["corpus"] in ("real", "sample")

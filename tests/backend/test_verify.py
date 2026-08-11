"""Citation verifier tests: python -m pytest tests/backend/test_verify.py -q"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rag.verify import verify_citations

SOURCES = [
    {"law_name": "주택임대차보호법", "article_no": "제3조의3", "text": "임차권등기명령 조문 내용"},
    {"law_name": "형사소송법", "article_no": "제308조의2", "text": "위법수집증거 배제"},
    {"law_name": "판례(대법원)", "article_no": "2001도3106", "text": "당사자 녹음 증거능력"},
]


def test_valid_citations_pass():
    answer = "임차권등기명령을 신청할 수 있습니다(주택임대차보호법 제3조의3). 판례도 있습니다(대법원 2001도3106)."
    r = verify_citations(answer, SOURCES)
    assert r["ok"], r


def test_hallucinated_article_flagged():
    answer = "보증금은 청구할 수 있습니다(주택임대차보호법 제99조)."
    r = verify_citations(answer, SOURCES)
    assert not r["ok"]
    assert any("제99조" in u for u in r["unknown"])


def test_hallucinated_case_flagged():
    answer = "판례에 따르면 가능합니다(대법원 2015도99999)."
    r = verify_citations(answer, SOURCES)
    assert not r["ok"]
    assert any("2015도99999" in u for u in r["unknown"])


def test_no_citations_is_ok():
    r = verify_citations("일반적인 안내 문장입니다.", SOURCES)
    assert r["ok"]

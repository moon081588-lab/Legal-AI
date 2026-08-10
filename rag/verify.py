"""Citation verifier: check that every 조문/판례 cited in an answer exists in the
retrieved sources. Catches hallucinated citations before the user trusts them.
"""

import re

# (법령명 제N조), (법령명 제N조의M) — capture law name + article
ARTICLE_RE = re.compile(r"([가-힣·\s]{2,25}?법(?:률)?)\s*(제\d+조(?:의\d+)?)")
# 사건번호: 2001도3106, 2010다12345, 2007도3061 등
CASE_RE = re.compile(r"(\d{4}[도다누허므초재][단합]?\d{1,7})")


def extract_citations(answer: str) -> dict:
    articles = {(name.strip(), art) for name, art in ARTICLE_RE.findall(answer)}
    cases = set(CASE_RE.findall(answer))
    return {"articles": articles, "cases": cases}


def verify_citations(answer: str, sources: list[dict]) -> dict:
    """Return {'ok': bool, 'unknown': [readable citation strings not in sources]}."""
    cited = extract_citations(answer)
    known_articles = {(s["law_name"], s["article_no"]) for s in sources}
    known_article_nos = {s["article_no"] for s in sources}
    known_law_names = {s["law_name"] for s in sources}
    # guide/판례 records: case number lives in article_no
    known_cases = {s["article_no"] for s in sources}
    # cases also appear inside source texts (e.g. guide text citing 판례)
    source_text = " ".join(s.get("text", "") for s in sources)

    unknown = []
    for law_name, art in cited["articles"]:
        exact = (law_name, art) in known_articles
        # tolerate partial law-name match (모델이 법령명을 축약하는 경우)
        partial = art in known_article_nos and any(law_name in k or k in law_name for k in known_law_names)
        in_text = f"{art}" in source_text and law_name in source_text
        if not (exact or partial or in_text):
            unknown.append(f"{law_name} {art}")
    for case in cited["cases"]:
        if case not in known_cases and case not in source_text:
            unknown.append(f"판례 {case}")

    return {"ok": not unknown, "unknown": unknown}

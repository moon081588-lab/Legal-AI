"""Retrieval eval: does the expected article appear in top-k results?

Usage: python evals/run_evals.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rag.retrieve import Retriever  # noqa: E402


def main() -> None:
    retriever = Retriever()
    questions = [
        json.loads(l)
        for l in (ROOT / "evals" / "questions.jsonl").read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    scored = [q for q in questions if q.get("expected_law")]
    hits = 0
    for q in scored:
        results = retriever.search(q["question"], k=5)
        found = {(r["law_name"], r["article_no"]) for r in results}
        ok = any((q["expected_law"], a) in found for a in q["expected_articles"])
        hits += ok
        mark = "PASS" if ok else "FAIL"
        print(f"[{mark}] {q['question'][:40]}...  expected {q['expected_law']} {q['expected_articles']}")
        if not ok:
            got = [r["law_name"] + " " + r["article_no"] for r in results]
            print(f"       got: {got}")
    print(f"\nRecall@5: {hits}/{len(scored)}")
    if hits < len(scored):
        sys.exit(1)  # CI gate: any retrieval regression fails the build


if __name__ == "__main__":
    main()

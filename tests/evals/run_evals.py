"""검색 평가: 기대한 조문이 상위 k개 결과에 들어오는가?

    python tests/evals/run_evals.py                    # 평가 (회귀 시 exit 1)
    python tests/evals/run_evals.py --update-baseline  # 현재 결과를 기준선으로 저장

## 왜 100% 가 아니라 기준선인가

샘플 조문 16건일 때는 Recall@5 가 100% 였습니다. 평가 문항이 그 16건을 보고 쓰였으니
당연한 결과였고, 그래서 아무것도 검증하지 못했습니다. 실제 법령 1,200여 건을 넣자
9/16 으로 떨어졌는데, 이것이 처음 나온 정직한 숫자입니다.

여기서 게이트를 100% 로 두면 CI 는 영원히 빨간불이고, 결국 아무도 보지 않게 됩니다.
대신 **지금 통과하는 문항의 목록**을 기준선으로 박아 두고, 그중 하나라도 실패로
바뀌면 실패시킵니다. 총점만 보면 A 가 깨지고 B 가 붙는 맞교환을 놓치지만, 문항
단위로 보면 잡힙니다.

검색을 개선해 새로 통과하는 문항이 생기면 `--update-baseline` 로 기준선을 올리세요.
기준선은 내려가지 않습니다.
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.rag.retrieve import Retriever  # noqa: E402

QUESTIONS_FILE = Path(__file__).parent / "questions.jsonl"
BASELINE_FILE = Path(__file__).parent / "baseline.json"
TOP_K = 5


def evaluate() -> list[dict]:
    retriever = Retriever()
    questions = [
        json.loads(l) for l in QUESTIONS_FILE.read_text(encoding="utf-8").splitlines() if l.strip()
    ]
    rows = []
    for q in questions:
        if not q.get("expected_law"):
            continue
        results = retriever.search(q["question"], k=TOP_K)
        found = {(r["law_name"], r["article_no"]) for r in results}
        ok = any((q["expected_law"], a) in found for a in q["expected_articles"])
        rows.append({
            "question": q["question"],
            "expected": f"{q['expected_law']} {q['expected_articles']}",
            "ok": ok,
            "got": [f"{r['law_name']} {r['article_no']}" for r in results],
        })
    return rows


def load_baseline() -> set[str] | None:
    if not BASELINE_FILE.exists():
        return None
    return set(json.loads(BASELINE_FILE.read_text(encoding="utf-8"))["passing"])


def save_baseline(rows: list[dict]) -> None:
    passing = sorted(r["question"] for r in rows if r["ok"])
    BASELINE_FILE.write_text(
        json.dumps(
            {
                "recorded_on": date.today().isoformat(),
                "recall_at_5": f"{len(passing)}/{len(rows)}",
                "note": "여기 있는 문항이 실패로 바뀌면 검색 회귀입니다. 목록은 줄어들 수 없습니다.",
                "passing": passing,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"기준선을 저장했습니다: {len(passing)}/{len(rows)} -> {BASELINE_FILE.name}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--update-baseline", action="store_true", help="현재 통과 문항을 기준선으로 저장")
    parser.add_argument("--quiet", action="store_true", help="실패 문항만 출력")
    args = parser.parse_args()

    rows = evaluate()
    hits = sum(r["ok"] for r in rows)

    for r in rows:
        if r["ok"] and args.quiet:
            continue
        print(f"[{'PASS' if r['ok'] else 'FAIL'}] {r['question'][:40]}...  expected {r['expected']}")
        if not r["ok"]:
            print(f"       got: {r['got']}")

    print(f"\nRecall@{TOP_K}: {hits}/{len(rows)}")

    if args.update_baseline:
        save_baseline(rows)
        return

    baseline = load_baseline()
    if baseline is None:
        print(
            f"\n기준선이 없습니다. 지금 결과가 만족스럽다면 아래 명령으로 고정하세요.\n"
            f"  python {Path(__file__).relative_to(ROOT)} --update-baseline"
        )
        return

    now_passing = {r["question"] for r in rows if r["ok"]}
    regressed = sorted(baseline - now_passing)
    improved = sorted(now_passing - baseline)

    if improved:
        print(f"\n새로 통과한 문항 {len(improved)}건:")
        for q in improved:
            print(f"  + {q[:60]}")
        print("  --update-baseline 로 기준선을 올려 주세요.")

    if regressed:
        print(f"\n검색 회귀: 기준선에서 통과하던 문항 {len(regressed)}건이 실패합니다.")
        for q in regressed:
            print(f"  - {q[:60]}")
        sys.exit(1)

    print("회귀 없음.")


if __name__ == "__main__":
    main()

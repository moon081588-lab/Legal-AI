#!/usr/bin/env bash
# 말뭉치를 다시 만들고, 다시 재고, 결과를 한 화면으로 보여 줍니다.
#
#   ./tools/refresh.sh            # 임베딩 재생성 + 평가 + 테스트
#   ./tools/refresh.sh --ingest   # 법령·판례 수집부터 (LAW_GO_KR_OC 필요)
#
# 여러 명령을 순서대로 치고 그때마다 출력을 읽는 대신, 한 번 실행하고 마지막
# 요약만 보면 되게 하는 것이 목적입니다.

set -uo pipefail
cd "$(dirname "$0")/.."

BOLD=$'\033[1m'; DIM=$'\033[2m'; RED=$'\033[31m'; GREEN=$'\033[32m'; OFF=$'\033[0m'
step() { printf "\n${BOLD}==> %s${OFF}\n" "$1"; }
FAILED=0

if [ ! -x .venv/bin/python ]; then
  echo "${RED}.venv 가 없습니다.${OFF}  python3.12 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt -r requirements-dev.txt"
  exit 1
fi
PY=.venv/bin/python

if [ "${1:-}" = "--ingest" ]; then
  if [ -z "${LAW_GO_KR_OC:-}" ]; then
    echo "${RED}LAW_GO_KR_OC 가 설정되지 않았습니다.${OFF}  export LAW_GO_KR_OC=<아이디>"
    exit 1
  fi
  step "법령 수집"
  $PY tools/ingest/fetch_laws.py && $PY tools/ingest/parse_laws.py || FAILED=1
  step "판례 수집"
  $PY tools/ingest/fetch_precedents.py || FAILED=1
  $PY tools/ingest/fetch_required_cases.py || FAILED=1
  step "데이터 검증"
  $PY tools/validate_data.py || FAILED=1
fi

step "임베딩 재생성 (몇 분 걸립니다)"
$PY tools/build_embeddings.py || FAILED=1

step "검색 평가 — 의미 검색 포함"
HYBRID=$($PY tests/evals/run_evals.py --quiet 2>&1 | tee /dev/stderr | grep -E "^Recall" | head -1)

step "검색 평가 — BM25 단독 (CI 가 쓰는 방식)"
LEXICAL=$(LEGAL_AI_DISABLE_EMBEDDINGS=1 $PY tests/evals/run_evals.py --quiet 2>&1 | grep -E "^Recall" | head -1)

step "테스트"
TESTS=$($PY -m pytest tests/backend -q 2>&1 | tail -1)

step "말뭉치 상태"
$PY - <<'EOF'
import sys; sys.path.insert(0, ".")
from backend.rag.retrieve import Retriever
s = Retriever().stats()
print(f"  조문·판례·가이드 {s['articles']}건 / corpus={s['corpus']} / 검색={s['retrieval']}")
EOF

printf "\n${BOLD}요약${OFF}\n"
printf "  의미 검색 포함 : %s\n" "${HYBRID:-측정 실패}"
printf "  BM25 단독      : %s\n" "${LEXICAL:-측정 실패}"
printf "  테스트         : %s\n" "${TESTS:-실패}"
printf "\n${DIM}기준선을 지금 결과로 고정하려면:${OFF}\n"
printf "  %s tests/evals/run_evals.py --update-baseline\n" "$PY"
printf "  LEGAL_AI_DISABLE_EMBEDDINGS=1 %s tests/evals/run_evals.py --update-baseline\n" "$PY"

if [ "$FAILED" -ne 0 ]; then printf "\n${RED}일부 단계가 실패했습니다.${OFF}\n"; exit 1; fi
printf "\n${GREEN}완료${OFF}\n"

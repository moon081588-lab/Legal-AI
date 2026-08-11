#!/usr/bin/env bash
# 배포 후 연기 테스트 — 상태 코드만이 아니라 응답 "모양"까지 확인합니다.
#
#   ./scripts/smoke.sh                          # 로컬 (localhost:8000)
#   ./scripts/smoke.sh https://legal-ai-api.fly.dev
#
# 실패하면 즉시 0이 아닌 코드로 종료하므로 배포 파이프라인에 그대로 넣을 수 있습니다.

set -uo pipefail
BASE="${1:-http://localhost:8000}"
FAILED=0

pass() { printf "  \033[32m✓\033[0m %s\n" "$1"; }
fail() { printf "  \033[31m✗\033[0m %s\n     %s\n" "$1" "$2"; FAILED=1; }

check() {                       # check <이름> <경로> <응답에 반드시 포함될 문자열>
  local name="$1" path="$2" expect="$3"
  local body code
  body=$(curl -sS -m 20 -w $'\n%{http_code}' "$BASE$path" 2>&1)
  code=$(printf '%s' "$body" | tail -n1)
  body=$(printf '%s' "$body" | sed '$d')
  if [ "$code" != "200" ]; then
    fail "$name" "HTTP $code ($path)"
  elif ! printf '%s' "$body" | grep -q -- "$expect"; then
    fail "$name" "응답에 '$expect' 없음: $(printf '%s' "$body" | head -c 160)"
  else
    pass "$name"
  fi
}

echo "연기 테스트: $BASE"

check "생존 확인"        "/api/livez"              '"alive"'
check "준비 확인"        "/api/readyz"             '"ready":true'
check "상태"             "/api/health"             '"articles"'
check "체크리스트 목록"   "/api/checklists"         '"assault"'
check "체크리스트 상세"   "/api/checklists/assault" '"urgent"'
check "지원제도 질문"     "/api/support/questions"  '"crime_type"'
check "지원기관"         "/api/centers"            '"1366"'
check "절차 안내"        "/api/procedure"          '245'
check "기한"             "/api/deadlines"          '"cctv"'
check "용어 사전"        "/api/glossary"           '불송치'
check "서식(CCTV)"       "/api/templates/cctv"     'CCTV'
check "서식(고소장)"      "/api/templates/complaint" '고소'

# 메타데이터 키가 콘텐츠로 새어 나오지 않는지 (과거 500 원인)
if curl -sS -m 20 "$BASE/api/checklists" | grep -q "verified_on"; then
  fail "메타데이터 누출" "/api/checklists 응답에 verified_on 이 포함됨"
else
  pass "메타데이터 누출 없음"
fi

# 채팅 스트림: 근거와 종료 이벤트가 모두 나와야 함
CHAT=$(curl -sS -m 40 -X POST "$BASE/api/chat" \
  -H 'Content-Type: application/json' \
  -d '{"question":"전세 보증금을 못 돌려받고 있어요"}' 2>&1)
if printf '%s' "$CHAT" | grep -q "event: sources" && printf '%s' "$CHAT" | grep -q "event: done"; then
  pass "채팅 스트리밍"
else
  fail "채팅 스트리밍" "$(printf '%s' "$CHAT" | head -c 200)"
fi

# 지원제도 매칭: 성폭력 피해자에게 무료 국선변호사가 안내되어야 함
MATCH=$(curl -sS -m 20 -X POST "$BASE/api/support/match" \
  -H 'Content-Type: application/json' -d '{"answers":{"crime_type":"sexual"}}' 2>&1)
if printf '%s' "$MATCH" | grep -q "victim_counsel"; then
  pass "지원제도 매칭"
else
  fail "지원제도 매칭" "$(printf '%s' "$MATCH" | head -c 200)"
fi

echo
if [ "$FAILED" -eq 0 ]; then
  echo "전체 통과"
else
  echo "실패한 항목이 있습니다. 롤백 또는 docs/runbook.md 를 확인하세요."
fi
exit "$FAILED"

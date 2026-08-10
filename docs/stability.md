# 안정성 지표와 측정 방법

"안정적으로 느껴진다"를 숫자로 바꾸고, CI가 그 숫자를 강제하도록 만든 문서입니다.

## 지표 요약

| 지표 | 목표 | 측정 방법 | CI 차단 여부 |
|---|---|---|---|
| 백엔드 테스트 통과율 | 100% | `pytest backend/` | ✅ 차단 |
| 검색 정확도 Recall@5 | 100% (16/16) | `python evals/run_evals.py` (실패 시 exit 1) | ✅ 차단 |
| 프론트 단위 테스트 | 100% 통과 | `npm test` (vitest) | ✅ 차단 |
| `app/lib` 커버리지 | ≥70% lines/functions | `npx vitest run --coverage` | ⚠️ 임계값 설정됨 |
| 타입 오류 | 0건 | `npm run build` (tsc 포함) | ✅ 차단 |
| E2E 시나리오 | 5/5 통과 | `npm run e2e` (Playwright) | ✅ 차단 |
| 접근성 점수 | ≥0.9 | Lighthouse CI | ⚠️ 리포트 (안정화 후 차단) |
| 성능 점수 / TTI / CLS | ≥0.85 / <4s / <0.1 | Lighthouse CI (`lighthouserc.json`) | ⚠️ 리포트 |
| 부하 시 오류율 | <1% @ 50 VU | `k6 run tests/load/k6_chat.js` | 수동 (릴리스 전) |
| 부하 시 p95 응답 | <3초 @ 50 VU | 동일 | 수동 |
| TTFT / 총 응답 시간 | 관측 후 목표 설정 | 서버 로그 `chat ... ttft_ms=... total_ms=...` | 관측용 |
| 크래시 없는 세션 | ≥99.5% | `client_error` 로그 건수 / 세션 수 | 관측용 |

## 실행 방법

```bash
# 백엔드
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest backend/ -q
python evals/run_evals.py

# 프론트엔드
cd frontend
npm ci
npm test                    # 단위 테스트 (SSE 파서)
npx vitest run --coverage   # 커버리지
npm run build               # 타입 검사 + 빌드
npm run e2e                 # E2E (백엔드·프론트 자동 기동)

# 부하 테스트 (백엔드 실행 중일 때)
k6 run tests/load/k6_chat.js
```

## 성능 관련 설계 결정

**SSE 델타 배칭.** 예전에는 스트리밍 청크마다 `setMessages`가 호출되어 답변 하나에 수십 번 리렌더가 발생했습니다. 지금은 `requestAnimationFrame`당 한 번만 반영하여 프레임당 1회 렌더로 고정됩니다(`app/page.tsx`의 `scheduleFlush`).

**메시지 메모이제이션.** `MessageView`를 `memo`로 감싸 스트리밍 중 이전 대화가 다시 렌더되지 않습니다. 대화가 길어져도 렌더 비용이 일정합니다.

**요청 취소.** 새 질문을 하면 `AbortController`로 이전 스트림을 취소합니다. 중복 스트림으로 인한 화면 뒤섞임과 낭비를 막습니다.

**SSE 파서 분리.** 청크 경계·한글 멀티바이트 분할·잘못된 블록 처리는 `app/lib/sse.ts`로 분리해 단위 테스트로 검증합니다(모든 바이트 위치에서 분할해도 동일 결과).

**타임아웃.** Anthropic 클라이언트에 60초 타임아웃·재시도 1회를 설정해, 무한 대기 대신 사용자에게 한국어 오류 메시지를 표시합니다.

## 알려진 확장 한계 (부하 테스트로 확인할 것)

1. **BM25 전체 스캔.** `Retriever.search`는 질의마다 전체 코퍼스를 훑습니다. 문서 16건에서는 무시할 수준이지만, 법령 30개 + 판례 수백 건이면 병목이 됩니다. → 인덱스 영속화 또는 pgvector 전환.
2. **동기 제너레이터 스트리밍.** FastAPI가 스트림당 워커를 점유합니다. 동시 접속이 늘면 `async def` + 비동기 스트리밍으로 전환이 필요합니다.
3. **데이터 상시 메모리 적재.** 프로세스 시작 시 전체 코퍼스를 메모리에 올립니다. 판례가 늘면 DB 기반으로 옮겨야 합니다.

## 크래시·오류 관측

- 프론트 전역 오류는 `/api/client-error`로 전송됩니다(메시지·스택·경로만, **질문 내용은 전송하지 않음**).
- `SENTRY_DSN` 환경변수를 설정하면 백엔드 Sentry 리포팅이 활성화됩니다(`send_default_pii=False`).
- 서버 로그는 질문 내용을 남기지 않고 경로·소스 수·지연 시간만 기록합니다.

# 안정성 지표와 측정 방법

"안정적으로 느껴진다"를 숫자로 바꾸고, CI가 그 숫자를 강제하도록 만든 문서입니다.

## 지표 요약

| 지표 | 목표 | 측정 방법 | CI 차단 여부 |
|---|---|---|---|
| 백엔드 테스트 통과율 | 100% (27건) | `pytest tests/backend` | ✅ 차단 |
| 카오스 테스트 (장애 주입) | 14/14 통과 | `pytest tests/backend/test_chaos.py` | ✅ 차단 |
| 검색 정확도 Recall@5 | 100% (16/16) | `python evals/run_evals.py` (실패 시 exit 1) | ✅ 차단 |
| 프론트 단위 테스트 | 100% 통과 | `npm test` (vitest) | ✅ 차단 |
| `app/lib` 커버리지 | ≥70% lines/functions | `npx vitest run --coverage` | ⚠️ 임계값 설정됨 |
| 타입 오류 | 0건 | `npm run build` (tsc 포함) | ✅ 차단 |
| E2E 시나리오 | 11/11 통과 | `npm run e2e` (Playwright, 프로덕션 빌드 기준) | ✅ 차단 |
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
python -m pytest tests/backend -q
python evals/run_evals.py

# 프론트엔드
cd frontend
npm ci
npm test                    # 단위 테스트 (SSE 파서)
npx vitest run --coverage   # 커버리지
npm run build               # 타입 검사 + 빌드
npm run e2e                 # E2E (백엔드·프론트 자동 기동, 프로덕션 빌드 사용)

# 부하 테스트 (백엔드 실행 중일 때)
k6 run tests/load/k6_chat.js
```

## 성능 관련 설계 결정

**SSE 델타 배칭.** 예전에는 스트리밍 청크마다 `setMessages`가 호출되어 답변 하나에 수십 번 리렌더가 발생했습니다. 지금은 `requestAnimationFrame`당 한 번만 반영하여 프레임당 1회 렌더로 고정됩니다(`app/page.tsx`의 `scheduleFlush`).

**메시지 메모이제이션.** `MessageView`를 `memo`로 감싸 스트리밍 중 이전 대화가 다시 렌더되지 않습니다. 대화가 길어져도 렌더 비용이 일정합니다.

**요청 취소.** 새 질문을 하면 `AbortController`로 이전 스트림을 취소합니다. 중복 스트림으로 인한 화면 뒤섞임과 낭비를 막습니다.

**SSE 파서 분리.** 청크 경계·한글 멀티바이트 분할·잘못된 블록 처리는 `app/lib/sse.ts`로 분리해 단위 테스트로 검증합니다(모든 바이트 위치에서 분할해도 동일 결과).

**타임아웃.** Anthropic 클라이언트에 60초 타임아웃·재시도 1회를 설정해, 무한 대기 대신 사용자에게 한국어 오류 메시지를 표시합니다.

## 내구성 (durability) 장치

| 위험 | 대응 | 확인 방법 |
|---|---|---|
| 잘못된 수집이 정상 데이터를 덮어씀 | `safe_write` 가드 — 검증 실패·20% 이상 축소 시 쓰기 거부 | `pytest tests/backend/test_chaos.py` |
| 쓰기 도중 중단으로 파일 손상 | 임시 파일 + fsync + rename (원자적 쓰기) | 동일 |
| 조용한 데이터 손상 | `.sha256` 사이드카 | `python ingest/rollback.py --verify` |
| 나쁜 데이터 배포 | 날짜별 스냅샷 + 롤백 명령 | `python ingest/rollback.py` |
| 수집 후 품질 저하 | 커밋 전 검색 평가 실행 (실패 시 커밋 안 함) | `.github/workflows/ingest.yml` |
| 모델 API 장애 | 회로 차단기 → 조문 원문 답변으로 자동 전환, 60초 후 복귀 | `pytest tests/backend/test_chaos.py` |
| 배포 중 답변 끊김 | lifespan 종료 시 진행 중 스트림 최대 10초 드레인 | `/api/readyz`의 `active_streams` |
| 준비 안 된 인스턴스로 트래픽 유입 | `/api/livez`(생존) · `/api/readyz`(준비) 분리 | `curl /api/readyz` |
| 사용자 증거 일지 소실 | IndexedDB 저장 + localStorage 자동 마이그레이션 + 암호화 백업/복원 + 백업 권유 | `/journal` |
| 네트워크·서버 다운 시 사용 불가 | 서비스 워커로 체크리스트·절차·서식·일지 오프라인 지원 | 오프라인 후 새로고침 |
| 프론트 렌더 크래시 | 오류 화면 + 긴급 연락처 | `app/error.tsx` |
| 장애 시 대응 지연 | 장애 대응 runbook | [docs/runbook.md](runbook.md) |

## 확장성 대응 (완료 / 남은 과제)

**완료**

1. **검색 top-k 선택 최적화.** 전체 정렬(O(n log n)) 대신 `np.argpartition`(O(n))으로 상위 k개만 선택합니다.
2. **검색 결과 캐시.** 동일 질문은 재계산 없이 응답합니다(FIFO 256건). 캐시는 항상 복사본을 반환해 호출자가 캐시를 오염시킬 수 없습니다.
3. **비동기 스트리밍.** `/api/chat`이 `async def`로 전환되어, 블로킹 호출(검색·Claude 스트림)은 `anyio.to_thread`로 넘깁니다. 스트림 하나가 이벤트 루프를 점유하지 않습니다.
4. **입력 한도.** 질문 2,000자, 요약 대화 100건, 언어 코드 화이트리스트를 Pydantic이 강제합니다(초과 시 422).
5. **속도 제한.** IP당 분당 20회(기본값, `LEGAL_AI_RATE_LIMIT`로 조정). 초과 시 한국어 안내를 스트림으로 반환합니다.
6. **오류 화면.** 렌더 크래시 시 빈 화면 대신 복구 버튼과 긴급 연락처를 보여 줍니다(`app/error.tsx`).

**남은 과제**

1. **BM25 전체 스캔 자체.** 캐시·argpartition으로 완화했지만 미스 시 여전히 전체 코퍼스를 훑습니다. 판례 수천 건 규모에서는 인덱스 영속화 또는 pgvector 전환이 필요합니다.
2. **데이터 상시 메모리 적재.** 프로세스 시작 시 전체 코퍼스를 메모리에 올립니다. → DB 기반 전환.
3. **다중 워커 환경의 속도 제한.** 현재는 프로세스 내 카운터라 워커가 여러 개면 정확하지 않습니다. → Redis 기반으로 교체.

## 크래시·오류 관측

- 프론트 전역 오류는 `/api/client-error`로 전송됩니다(메시지·스택·경로만, **질문 내용은 전송하지 않음**).
- `SENTRY_DSN` 환경변수를 설정하면 백엔드 Sentry 리포팅이 활성화됩니다(`send_default_pii=False`).
- 서버 로그는 질문 내용을 남기지 않고 경로·소스 수·지연 시간만 기록합니다.

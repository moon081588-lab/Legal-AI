# 장애 대응 runbook

새벽 3시에도 따라 할 수 있도록 쓴 문서입니다. 위에서부터 순서대로 확인하세요.

## 0. 30초 진단

```bash
curl -s localhost:8000/api/livez     # 프로세스 살아있는지
curl -s localhost:8000/api/readyz    # 트래픽 받을 준비 됐는지 (503이면 아래 1번)
curl -s localhost:8000/api/health    # 조문 수, 캐시, 생성 기능 활성화 여부
python ingest/rollback.py --verify   # 데이터 무결성(체크섬)
```

로그에서 볼 것: `breaker=open`(모델 API 장애), `route=rate_limited`(요청 폭주), `client_error`(프론트 크래시), `ttft_ms`가 평소보다 큼(지연).

---

## 1. `/api/readyz`가 503을 반환

**원인 후보**: 조문 데이터 로드 실패, 종료 절차 진행 중.

```bash
curl -s localhost:8000/api/readyz | python -m json.tool   # articles 값 확인
ls -l data/articles.jsonl data/sample/articles.jsonl
python ingest/rollback.py --verify
```

- `articles: 0` → 데이터 파일이 비었거나 손상. **2번**으로.
- `shutting_down: true` → 배포 중. 종료 대기(최대 10초) 후 새 인스턴스가 뜨는지 확인.

---

## 2. 잘못된 법령 데이터가 배포됨 (최우선 대응)

증상: 답변에 조문이 안 나옴, 인용 검증 경고 급증, 검색 평가 실패.

```bash
python ingest/rollback.py                      # 스냅샷 목록 확인
python ingest/rollback.py articles 2026-08-04  # 직전 정상 날짜로 복원
python evals/run_evals.py                      # 16/16 확인
# 서비스 재시작 후
curl -s localhost:8000/api/health
```

판례도 동일: `python ingest/rollback.py precedents <날짜>`.

되돌린 뒤 원인 파악 전까지 주간 수집 워크플로를 비활성화하세요(GitHub → Actions → 해당 workflow → Disable).

---

## 3. law.go.kr API 장애 / 응답 형식 변경

증상: 수집 잡 실패, `IngestGuardError` 로그.

**서비스는 정상 동작합니다.** 기존 데이터가 그대로 유지되도록 설계되어 있으므로 급하지 않습니다.

1. https://open.law.go.kr 접속 확인(점검 공지 여부).
2. 수동 확인: `LAW_GO_KR_OC=<id> python ingest/fetch_laws.py`
3. 응답 XML 구조가 바뀐 경우 `ingest/parse_laws.py`의 태그명을 수정하고 `python -m pytest backend/test_chaos.py -q`로 가드가 여전히 동작하는지 확인.
4. 의도적으로 법령을 줄인 경우에만 `FORCE_INGEST=1`로 가드를 우회하세요.

---

## 4. 모델 API 장애 / 키 소진

증상: 로그에 `breaker=open`, 사용자에게 "일시적인 문제" 안내가 노출.

**설계상 자동 대응됩니다** — 회로 차단기가 열리면 조문 원문 기반 답변으로 자동 전환되고, 60초 뒤 자동으로 재시도합니다.

확인할 것:
- Anthropic 콘솔의 크레딧·상태(https://status.anthropic.com)
- 서버 키 사용 시 `ANTHROPIC_API_KEY` 유효성
- 장기화되면 `unset ANTHROPIC_API_KEY` 후 재시작해 검색 전용 모드로 안내를 단순화

---

## 5. 응답이 느림 / 요청 폭주

```bash
grep "ttft_ms" server.log | tail -50      # 지연 추세
grep "rate_limited" server.log | wc -l    # 차단된 요청 수
```

- 특정 IP의 폭주 → `LEGAL_AI_RATE_LIMIT`을 낮춰 재시작(기본 20/분).
- 전반적 지연 → 코퍼스 증가로 BM25 스캔이 병목일 수 있음. `docs/stability.md`의 "남은 과제" 참고.
- 부하 재현: `k6 run tests/load/k6_chat.js`

---

## 6. 서버 전체 소실 (재구축)

```bash
git clone https://github.com/moon081588-lab/Legal-AI && cd Legal-AI
pip install -r requirements.txt
# 법령 데이터는 저장소에 커밋되어 있으므로 즉시 동작합니다.
uvicorn backend.app:app --port 8000
cd frontend && npm ci && npm run build && npm start
```

데이터의 원본은 (1) 이 저장소의 커밋 이력, (2) `data/snapshots/`, (3) law.go.kr API 세 곳에 존재합니다. 셋 다 사라지는 경우는 사실상 없습니다.

---

## 7. 사용자 데이터(증거 일지) 관련 문의

증거 일지는 **사용자 기기(IndexedDB)에만** 저장되며 서버에는 사본이 없습니다. 따라서 운영자가 복구해 줄 수 없습니다.

- 사용자에게 안내: 같은 브라우저에서 `/journal` 접속 → 백업 파일이 있으면 "백업 파일 복원".
- 백업 파일이 없고 브라우저 데이터를 지웠다면 복구 불가. 이 사실을 정직하게 안내하고, 앞으로는 백업을 권유.

---

## 8. CI의 e2e 잡이 실패

1. Actions 실행 화면에서 **playwright-report** 아티팩트를 내려받아 실패 스크린샷·trace를 확인하세요.
2. 로컬 재현: `cd frontend && npx playwright install chromium && npm run e2e`
3. 자주 겪는 원인
   - **타임아웃**: E2E는 `next dev`가 아니라 프로덕션 빌드(`npm run build && npm start`)로 실행됩니다. dev 모드는 첫 요청마다 라우트를 컴파일해 CI에서 테스트 예산을 초과합니다.
   - **strict mode violation**: `getByText`가 안쪽 `<b>`와 바깥 래퍼를 동시에 잡는 경우입니다. 클래스 기반 로케이터나 `.first()`를 사용하세요.
   - **서비스 워커 테스트 실패**: 등록 전에 reload하면 실패합니다. `navigator.serviceWorker.controller`를 기다린 뒤 오프라인 전환하세요.

## 연락처

- 대한법률구조공단 132 / 범죄피해자지원센터 1577-1295 (사용자 안내용)
- 저장소 이슈: https://github.com/moon081588-lab/Legal-AI/issues

# Legal-AI에 기여하기

법률 도움이 절실한 사람을 돕는 오픈소스 프로젝트입니다. 개발자가 아니어도 기여할 수 있습니다.

## 코딩 없이 기여하기 (법률 배경 환영)

- **가이드 검토**: `data/guides/evidence.jsonl`의 증거확보 가이드 내용을 검토하고 부정확한 부분을 이슈로 알려 주세요. 특히 변호사·법학 전공자의 검토가 절실합니다 (`docs/legal-review.md` 참고).
- **평가 질문 추가**: `evals/questions.jsonl`에 실제 사람들이 물어볼 법한 질문과 기대 근거(조문·판례)를 추가해 주세요.
- **법령 추가**: `ingest/laws.txt`에 수요가 많은 법령의 정식 명칭을 추가해 주세요.
- **판례 검색어 추가**: `ingest/precedent_queries.txt`에 유용한 판례 검색어를 추가해 주세요.
- **구어체 사전 확장**: `rag/retrieve.py`의 `QUERY_SYNONYMS`에 일상어→법률용어 매핑을 추가해 주세요.

## 코드로 기여하기

시작하기 좋은 작업: 카카오톡 채널 연동, pgvector 하이브리드 검색, 모바일 UI 개선, Haiku 기반 위기 분류기(현재 키워드 방식), 범죄 유형별 체크리스트 확대 (`data/checklists.json`).

```bash
pip install -r requirements.txt fastapi uvicorn pytest httpx
python -m pytest backend/ -q        # 테스트
python evals/run_evals.py           # 검색 평가 (PR 전 통과 필수)
```

## 원칙 (반드시 지켜 주세요)

0. **데이터 파일의 메타데이터 키 주의.** `note`, `sources`, `verified_on`은 콘텐츠가 아니라 메타데이터입니다(`backend/app.py`의 `META_KEYS`). 최상위 키를 순회하는 코드는 반드시 이 키들을 걸러내야 합니다 — 걸러내지 않아 `/api/checklists`가 500으로 죽고 증거 체크리스트 기능 전체가 동작하지 않은 적이 있습니다.
1. **출처 없는 법률 콘텐츠 금지.** 사용자에게 보이는 모든 정보에는 확인 가능한 출처가 있어야 합니다. `data/*.json`에 항목을 추가할 때는 `sources: [{label, url}]`을 함께 넣고 `verified_on` 날짜를 갱신해 주세요(정부·법원·공공기관 출처 우선, https 필수). 테스트가 이를 강제합니다(`test_every_support_program_cites_a_source`, `test_reference_datasets_carry_sources`). 가이드·샘플 조문은 PR 설명에 근거(법령 조문, 판례 번호)를 명시해 주세요.
2. **불법 증거 수집 방법 안내 금지.** 타인 간 대화 녹음, 무단 열람, 위치추적 등은 어떤 형태로도 안내하지 않습니다.
3. **법률 자문 아님 원칙 유지.** 개별 사건 전략·승패 예측 기능은 받지 않습니다 (변호사법).
4. 사용자 대면 문구는 한국어 존댓말로 작성해 주세요.

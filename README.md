# Legal-AI

일반인을 위한 대한민국 생활법령 AI 도우미입니다. 일상적인 법률 질문을 쉬운 한국어로 답변하며, [국가법령정보 Open API](https://open.law.go.kr)에서 수집한 실제 법령을 근거로 조문 단위 출처를 함께 제시합니다.

**본 서비스는 법령 정보 안내 서비스이며, 법률 자문이 아닙니다.** 법령을 설명하고 근거 조문을 인용할 뿐, 소송 승패 예측·소송 전략·법원 제출 서면 작성은 제공하지 않습니다(변호사법 준수). 모든 답변은 AI 생성물임을 명시합니다(AI 기본법 준수).

**판례 기반 답변.** 법령 조문뿐 아니라 실제 법원 판례를 함께 검색해 답변 근거로 사용합니다. 증거능력에 관한 핵심 대법원 판례(당사자 녹음 2001도3106, 위법수집증거 배제 2007도3061 전원합의체, 사인 수집 증거의 비교형량 2008도3990)가 샘플에 포함되어 있으며, `python ingest/fetch_precedents.py`로 국가법령정보 판례 API에서 실제 판례를 확대 수집할 수 있습니다(검색어는 `ingest/precedent_queries.txt`).

**중점 영역 — 범죄 피해자의 증거 확보.** 2026년 형사소송법 개정(검사 직접·보완수사 폐지, 10월 시행)으로 피해자가 스스로 증거를 확보해야 하는 부담이 커졌습니다. Legal-AI는 형사소송법·통신비밀보호법 등 관련 법령과 함께, 적법한 증거 확보·보존 방법을 안내하는 큐레이션 가이드(`data/guides/`)를 제공합니다. 불법적인 수집 방법(타인 간 대화 녹음, 무단 열람 등)은 안내하지 않으며, 오히려 그 위법성과 증거배제 원칙(형소법 제308조의2)을 경고하도록 설계되어 있습니다.

전체 설계는 [docs/architecture.md](docs/architecture.md)를 참고해 주세요.

## 저장소 구성

```
ingest/    law.go.kr에서 법령을 수집하여 조문 단위 JSONL로 변환
rag/       조문 BM25 검색 + Claude 답변 생성
backend/   FastAPI 앱: 스트리밍 /api/chat (SSE), 가드레일, 테스트
frontend/  Next.js 채팅 UI (한국어, 스트리밍, 근거 조문 패널)
cli.py     터미널에서 질문하기
evals/     검색 정확도 평가
data/      sample/에 개발용 샘플 데이터 포함 (즉시 실행 가능)
```

## 빠른 시작 (웹 앱)

```bash
pip install -r requirements.txt

# 터미널 1 — 백엔드 (8000번 포트):
uvicorn backend.app:app --reload --port 8000

# 터미널 2 — 프론트엔드 (3000번 포트):
cd frontend && npm install && npm run dev
```

http://localhost:3000 을 열어 주세요. `ANTHROPIC_API_KEY`가 없으면 검색 전용 모드(관련 조문 원문 표시)로 동작하며, 백엔드 실행 전에 키를 설정하면 Claude가 조문을 인용한 답변을 생성합니다.

## CLI / 테스트

```bash
python cli.py "전세 보증금을 못 돌려받고 있어요"
python -m pytest backend/ -q          # 백엔드 테스트
python evals/run_evals.py             # 검색 정확도 (실패 시 exit 1)
cd frontend && npm test               # 프론트 단위 테스트
cd frontend && npm run e2e            # E2E (Playwright)
```

품질 지표와 측정 방법은 [docs/stability.md](docs/stability.md)에 정리되어 있습니다. 모든 PR은 CI에서 백엔드 테스트·검색 평가·타입 검사·빌드·E2E를 통과해야 합니다.

## 실제 법령 수집

1. [open.law.go.kr](https://open.law.go.kr)에서 무료 회원가입을 해주세요. OC 값은 이메일의 `@` 앞부분입니다.
2. ```bash
   export LAW_GO_KR_OC=본인아이디
   python ingest/fetch_laws.py      # ingest/laws.txt에 적힌 법령 다운로드
   python ingest/parse_laws.py      # -> data/articles.jsonl 생성 (샘플보다 우선 사용됨)
   ```
3. 법령을 추가하려면 `ingest/laws.txt`에 정식 법령명을 한 줄씩 적어 주세요.

⚠️ `data/sample/`은 수작업으로 만든 개발용 데이터로, 최신 법령과 다를 수 있습니다. 실제 서비스에는 반드시 API로 수집한 데이터를 사용해 주세요.

## 로드맵

1단계(완료): FastAPI 백엔드 + Next.js 채팅 UI. 2단계: 판례·법령해석례 추가, pgvector 하이브리드 검색, 평가 강화. 3단계: 계정, 피드백 수집, 리걸테크 진흥법 입법 동향에 따른 수익화 검토. 상세 내용은 `docs/architecture.md`에 있습니다.

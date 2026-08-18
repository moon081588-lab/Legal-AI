<div align="center">

# ⚖️ Legal-AI

**법은 평등하지만, 법에 접근하는 비용은 평등하지 않습니다.**

변호사를 선임하기 어려운 사람들이 스스로 자신의 권리를 이해하고 행사할 수 있도록 돕는
오픈소스 생활법령 AI 서비스입니다.

[![CI](https://github.com/moon081588-lab/Legal-AI/actions/workflows/ci.yml/badge.svg)](https://github.com/moon081588-lab/Legal-AI/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/Python-3.12-3776AB)
![Next.js](https://img.shields.io/badge/Next.js-14-000000)

[빠른 시작](#-빠른-시작) · [기능](#-무엇을-할-수-있나요) · [기여하기](#-함께해-주세요) · [배포](docs/deploy.md) · [설계](docs/architecture.md)

</div>

---

> [!IMPORTANT]
> **본 서비스는 법령 정보 안내이며, 법률 자문이 아닙니다.**
> 법령과 판례를 설명하고 근거를 인용할 뿐, 소송 승패 예측·소송 전략·법원 제출 서면 작성은 하지 않습니다(변호사법 준수). 모든 답변에는 AI 생성물임이 표시됩니다(AI 기본법 준수).
> 구체적인 사안은 변호사 또는 **대한법률구조공단(국번없이 132)** 상담을 이용해 주세요.

## 왜 만들었나

2026년 형사소송법 개정(검사 직접·보완수사 폐지, 10월 시행)으로 **범죄 피해자가 스스로 증거를 확보해야 하는 부담**이 커졌습니다. 변호사를 선임할 여력이 있는 사람은 도움을 받지만, 그렇지 못한 사람은 무엇을 어떻게 해야 하는지조차 알기 어렵습니다.

Legal-AI는 그 격차를 조금이라도 좁히기 위한 프로젝트입니다. 특히 **적법한 증거 확보 방법**과 **몰라서 못 받는 무료 지원 제도**를 안내하는 데 집중합니다.

## ✨ 무엇을 할 수 있나요

| 기능 | 설명 |
|---|---|
| 💬 **법령 질의응답** | 일상 언어로 물어보면 실제 법령·판례를 근거로 답변하고, **근거 조문 원문**을 함께 보여 줍니다. 인용이 근거와 일치하는지 자동 검증합니다. |
| 🤝 **무료 지원 확인** | 몇 가지 선택만으로 받을 수 있는 제도를 안내합니다. 성폭력·아동학대·스토킹 등은 **소득과 무관하게 피해자 국선변호사**가 무료로 지원되고, 사망·중상해는 **범죄피해구조금** 대상입니다. |
| 📋 **증거 체크리스트** | 폭행·사기·스토킹·성폭력별로 확보할 증거와 **긴급 기한**(CCTV 30일, 해바라기센터 72시간 등)을 안내합니다. |
| 🧭 **절차 안내** | 신고 → 수사 → 송치/불송치 → **이의신청** → 검찰 → 공판. 피해자가 놓치기 쉬운 불송치 이의신청(형소법 제245조의7)을 강조합니다. |
| ⏰ **기한 계산** | 사건 발생일을 넣으면 개인별 기한을 계산하고 `.ics` 파일로 **휴대폰 달력에 저장**할 수 있습니다. |
| 📄 **상담 준비 요약서** | 대화 내용을 정리해 변호사·법률구조공단 상담에 가져갈 한 장짜리 문서로 만들어 줍니다. |
| 📔 **증거 일지** | 반복되는 피해(스토킹 등)를 날짜별로 기록·사진 첨부. **기기에만 저장**되며 암호화 백업이 가능합니다. |
| 📞 **지원기관 찾기** | 전국 상담 전화와 지역별 법률구조공단·해바라기센터·범죄피해자지원센터 연락처. |
| 📖 **용어 사전** | 불송치, 증거보전, 대항력 등 법률 용어를 쉬운 말로 풀이합니다. |

**피해자를 배려한 설계**: 위험 상황이 감지되면 법령 정보보다 **긴급 연락처(112·1366·109)를 먼저** 안내하고, 어느 화면에서든 **빠른 나가기** 버튼으로 즉시 벗어날 수 있습니다. 대화는 서버에 저장되지 않으며, 체크리스트·절차·서식·용어 사전은 **오프라인에서도** 열립니다. 한국어·영어와 쉬운 말 모드를 지원합니다.

> [!NOTE]
> **모든 정보에는 출처가 있습니다.** 화면에 표시되는 법령·제도·연락처는 국가법령정보센터, 법무부, 대한법률구조공단 등 원출처 링크와 확인일을 함께 보여 줍니다. 출처 없는 콘텐츠는 CI에서 차단됩니다.

## 🚀 빠른 시작

**Python 3.11 이상**과 Node 20 이상이 필요합니다. macOS 에 기본 설치된 파이썬은 3.9 라
`python3 -V` 로 먼저 확인하시고, 낮으면 `brew install python@3.12` 로 설치해 주세요.

```bash
git clone https://github.com/moon081588-lab/Legal-AI.git
cd Legal-AI

python3 -m venv .venv          # 가상환경 (macOS·리눅스에는 python 이 없고 python3 만 있습니다)
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt

# 터미널 1 — 백엔드
uvicorn backend.app:app --reload --port 8000

# 터미널 2 — 프론트엔드
cd frontend && npm install && npm run dev
```

> [!TIP]
> 아래 문서의 `python ...` 명령은 모두 가상환경을 활성화한 상태(`source .venv/bin/activate`)를
> 전제로 합니다. 활성화하지 않았다면 `python` 대신 `python3` 를 쓰세요.

http://localhost:3000 을 열어 주세요. **API 키 없이도 모든 기능이 동작합니다** (답변 생성 대신 관련 조문 원문을 보여 주는 모드). `ANTHROPIC_API_KEY`를 설정하거나 화면의 ⚙️ 버튼에서 키를 입력하면 AI 답변이 생성됩니다.

### 실제 법령 데이터 넣기

저장소에는 개발용 샘플 조문만 들어 있습니다. 실제 법령으로 교체하려면:

```bash
export LAW_GO_KR_OC=본인아이디        # open.law.go.kr 무료 가입 (이메일 @ 앞부분)
python tools/ingest/fetch_laws.py           # tools/ingest/laws.txt 의 법령 수집
python tools/ingest/parse_laws.py
python tools/ingest/fetch_precedents.py     # 판례 수집
python tools/validate_data.py       # 데이터 검사
```

> [!WARNING]
> `data/corpus/sample/`은 수작업으로 만든 개발용 데이터로 최신 법령과 다를 수 있습니다. **공개 서비스에는 반드시 API로 수집한 데이터를 사용하세요.** GitHub Secrets에 `LAW_GO_KR_OC`를 등록하면 매주 자동 갱신됩니다.

## 🏗 구조

```
Legal-AI/
├── backend/     🐍 Python API — 서버에서 도는 모든 것
│   ├── app.py       라우트 · 가드레일(위기·변호사법) · 회로 차단기 · 속도 제한
│   ├── schemas.py   데이터/응답 스키마 (검증 + OpenAPI 타입의 원천)
│   └── rag/         BM25 검색 · 프롬프트 · 인용 검증
│
├── frontend/    ⚛️ Next.js PWA — 채팅 · 증거 일지 · 용어 사전 · 개인정보
│   └── app/lib/     SSE 파서 · 일지 저장소 · ICS · API 타입(자동 생성)
│
├── data/        📚 앱이 제공하는 모든 자료
│   ├── content/     사람이 쓰고 변호사 검토가 필요한 콘텐츠 (출처·확인일 필수)
│   │   └── templates/  고소장 · CCTV 보존요청서 서식
│   └── corpus/      법령 말뭉치 — 자동 수집·갱신 (sample은 개발용)
│
├── tools/       🔧 개발·운영 도구
│   ├── ingest/      law.go.kr 수집 · 안전 쓰기 · 스냅샷/롤백
│   ├── cli.py       터미널에서 질문하기
│   ├── validate_data.py · dump_openapi.py · smoke.sh
│
├── tests/       ✅ backend(단위·계약·카오스) · evals(검색 정확도) · load(k6)
└── docs/        📖 설계 · 배포 · 안정성 · 장애대응 · 법률검토 · 앱스토어
```

> **왜 이렇게 나눴나** — `data/content`는 **사람이 검수**해야 하는 콘텐츠, `data/corpus`는
> **자동으로 갱신**되는 법령입니다. 이 경계가 변호사 검토 대상과 주간 수집 대상을 가릅니다.
> `backend/`는 서버에서 도는 것 전부(검색 로직 포함), `tools/`는 서버에서 돌지 않는 것 전부입니다.

## 🧪 개발

```bash
python tools/validate_data.py    # 데이터 스키마 검사
python -m pytest tests/backend -q       # 백엔드 + 카오스 테스트
python tests/evals/run_evals.py          # 검색 정확도 (Recall@5, 실패 시 exit 1)
cd frontend && npm test            # 단위 테스트
cd frontend && npm run e2e         # E2E (Playwright)

# 백엔드 응답 모양을 바꿨다면 타입 재생성 후 커밋 (CI가 검사)
python tools/dump_openapi.py && npm --prefix frontend run gen:types
```

모든 PR은 CI에서 **데이터 검증 · 백엔드/카오스 테스트 · 검색 평가 · 타입 계약 · 빌드 · E2E**를 통과해야 합니다. 품질 지표는 [docs/stability.md](docs/stability.md), 장애 대응은 [docs/runbook.md](docs/runbook.md)를 참고하세요.

## 📚 문서

| 문서 | 내용 |
|---|---|
| [docs/architecture.md](docs/architecture.md) | 전체 설계, 법적 제약, 데이터 파이프라인 |
| [docs/deploy.md](docs/deploy.md) | 공개 배포 절차 (Fly.io + Vercel, 약 30분) |
| [docs/app-store.md](docs/app-store.md) | 앱 스토어 출시 가이드 (PWA / App Store / Google Play) |
| [docs/stability.md](docs/stability.md) | 안정성·내구성 지표와 측정 방법 |
| [docs/runbook.md](docs/runbook.md) | 장애 대응 절차 |
| [docs/legal-review.md](docs/legal-review.md) | **변호사 검토 요청서** — 검토가 필요한 항목 정리 |
| [docs/release.md](docs/release.md) | 버전 규칙과 릴리스 절차 |
| [CHANGELOG.md](CHANGELOG.md) | 변경 이력 (법령·제도 갱신 포함) |
| [CONTRIBUTING.md](CONTRIBUTING.md) | 기여 방법과 원칙 |

## 🙌 함께해 주세요

**법률 도움이 절실한 사람을 돕는 프로젝트입니다. 기여해 주실 수 있다면 부디 함께해 주세요.**

코딩을 하지 않아도 기여할 수 있습니다:

- ⚖️ **변호사·법학 전공자** — [docs/legal-review.md](docs/legal-review.md)의 항목을 검토해 주세요. 가장 절실한 도움입니다.
- 📝 **법령·판례 추가** — `tools/ingest/laws.txt`, `tools/ingest/precedent_queries.txt`에 한 줄 추가
- 🗣 **평가 질문 추가** — `tests/evals/questions.jsonl`에 실제 사람들이 물어볼 질문 추가
- 💬 **구어체 사전 확장** — `backend/rag/retrieve.py`의 `QUERY_SYNONYMS` (예: "퇴사"→"퇴직")
- 💻 **개발** — 카카오톡 채널 연동, pgvector 하이브리드 검색, 모바일 UI, 접근성 개선

자세한 내용은 [CONTRIBUTING.md](CONTRIBUTING.md)에 있습니다. 이슈·PR·아이디어 무엇이든 환영합니다.

## 📄 라이선스

[MIT](LICENSE) — 자유롭게 사용·수정·배포하실 수 있습니다. 이 코드가 누군가에게 도움이 된다면 그것으로 충분합니다.

---

<div align="center">

### 지금 도움이 필요하시다면

**경찰 112** · **여성긴급전화 1366** · **자살예방 상담 109**
**대한법률구조공단 132** · **범죄피해자지원센터 1577-1295**

*이 저장소의 코드가 아니라, 위 번호가 지금 당신을 도울 수 있습니다.*

</div>

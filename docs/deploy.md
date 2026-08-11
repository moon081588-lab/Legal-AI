# 배포 가이드 (PoC 공개하기)

백엔드는 Fly.io, 프론트엔드는 Vercel에 올리는 구성입니다. 둘 다 무료 등급으로 시작할 수 있고, 트래픽이 없을 때 서버가 자동으로 정지되어 비용이 거의 들지 않습니다.

전체 소요 시간: 처음이라면 30~40분.

---

## 0. 준비물

- GitHub 계정 (저장소 이미 있음)
- Fly.io 계정 · Vercel 계정 (둘 다 GitHub 로그인 가능)
- (선택) Anthropic API 키 — 없으면 **조문 원문 표시 모드**로 동작합니다. 나머지 기능(체크리스트, 지원제도 확인, 절차 안내, 서식, 일지)은 키 없이 모두 정상 동작합니다.

> **먼저 결정할 것 — 답변 생성 비용.** 서버에 키를 넣으면 방문자 누구나 AI 답변을 받을 수 있지만 비용은 운영자가 부담합니다. PoC 단계에서는 (1) 키 없이 조문 표시 모드로 공개하거나, (2) 키를 넣되 `LEGAL_AI_RATE_LIMIT`을 낮게(예: 5) 두고 사용량을 지켜보는 방법을 권합니다.

---

## 1. 실제 법령 데이터 넣기 (배포 전 필수)

지금 저장소에는 개발용 샘플 조문만 있습니다. 공개 전에 반드시 실제 법령으로 교체하세요.

```bash
# open.law.go.kr 가입 후 (OC = 이메일의 @ 앞부분)
export LAW_GO_KR_OC=본인아이디
python tools/ingest/fetch_laws.py
python tools/ingest/parse_laws.py
python tools/ingest/fetch_precedents.py

python tools/validate_data.py     # 데이터 모양 검사
python tests/evals/run_evals.py           # 검색 정확도 확인
git add data/ && git commit -m "실제 법령·판례 데이터 반영" && git push
```

GitHub → Settings → Secrets and variables → Actions 에 `LAW_GO_KR_OC`를 추가하면 매주 월요일 자동으로 갱신됩니다.

---

## 2. 백엔드 배포 (Fly.io)

```bash
# 설치 (macOS)
brew install flyctl
fly auth login

cd ~/Documents/github_repos/Legal-AI
fly launch --no-deploy          # 기존 fly.toml 사용 여부를 물으면 "yes"

# 시크릿 설정
fly secrets set LEGAL_AI_ALLOWED_ORIGINS="https://<나중에받을-vercel-도메인>"
fly secrets set ANTHROPIC_API_KEY="sk-ant-..."     # 선택
fly deploy

fly status                      # 상태 확인
fly logs                        # 로그
```

배포가 끝나면 주소가 나옵니다(예: `https://legal-ai-api.fly.dev`).

```bash
./tools/smoke.sh https://legal-ai-api.fly.dev    # 전체 통과해야 정상
```

---

## 3. 프론트엔드 배포 (Vercel)

1. https://vercel.com → **Add New → Project** → 이 저장소 선택
2. **Root Directory**를 `frontend`로 지정
3. **Environment Variables**에 추가:
   - `BACKEND_URL` = `https://legal-ai-api.fly.dev` (2단계에서 받은 주소)
4. Deploy

배포 후 받은 도메인(예: `https://legal-ai.vercel.app`)을 백엔드에 알려 주세요:

```bash
fly secrets set LEGAL_AI_ALLOWED_ORIGINS="https://legal-ai.vercel.app"
```

---

## 4. 공개 후 확인 목록

```bash
./tools/smoke.sh https://legal-ai-api.fly.dev
```

브라우저에서 직접 확인:

- [ ] 질문 → 답변과 **근거 조문** 패널이 보인다
- [ ] 📋 증거 체크리스트 → 범죄 유형 선택 → 항목과 **출처**가 보인다
- [ ] 🤝 무료 지원 확인 → 성폭력 선택 → **피해자 국선변호사**가 안내된다
- [ ] 📞 지원기관 찾기 → 전화번호를 누르면 전화 앱이 열린다 (모바일)
- [ ] ⏰ 기한 계산 → 날짜 선택 → `.ics` 내려받기가 된다
- [ ] 📔 증거 일지 → 기록 추가 → 새로고침해도 남아 있다
- [ ] **빠른 나가기** 버튼이 즉시 다른 사이트로 이동시킨다
- [ ] 비행기 모드에서 새로고침 → 체크리스트·용어 사전이 여전히 열린다
- [ ] 휴대폰 화면에서 글자와 버튼이 충분히 크다

---

## 5. 공개 범위에 대한 권고

PoC 단계에서는 **검색엔진 비노출**로 시작해 지인·전문가에게만 링크를 공유하고, 변호사 검토(`docs/legal-review.md`)를 받은 뒤 공개 범위를 넓히는 것을 권합니다. 비노출은 Vercel 프로젝트 설정에서 `X-Robots-Tag: noindex` 헤더를 추가하거나 `public/robots.txt`로 설정할 수 있습니다.

법적 성격(법률 자문이 아닌 정보 제공), 무료 운영, AI 생성물 고지는 이미 앱에 반영되어 있습니다. `docs/legal-review.md`를 변호사에게 함께 전달하세요.

---

## 6. 롤백

```bash
fly releases                    # 배포 이력
fly deploy --image <이전 이미지>  # 또는
fly releases rollback
```

데이터 문제라면 `python tools/ingest/rollback.py` (자세한 내용은 `docs/runbook.md`).

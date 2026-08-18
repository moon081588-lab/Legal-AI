# 릴리스 가이드

버전을 태그로 남기면 이용자와 기여자가 "언제 무엇이 바뀌었는지"를 확인할 수 있습니다.
이 프로젝트는 코드뿐 아니라 **법령·제도 내용**이 바뀌므로, 릴리스 노트가 특히 중요합니다.

## 버전 규칙

`MAJOR.MINOR.PATCH` (예: `0.2.1`)

| 상황 | 올릴 자리 | 예 |
|---|---|---|
| 이용자가 보는 안내 방식·API가 호환되지 않게 변경 | MAJOR | 답변 형식 전면 개편 |
| 기능·안내 콘텐츠 추가 | MINOR | 새 범죄 유형 체크리스트 추가 |
| 버그 수정, 문구 수정, 연락처·조문 갱신 | PATCH | 지원기관 전화번호 정정 |

`0.x` 동안은 언제든 바뀔 수 있다는 뜻입니다. 변호사 검토를 마치고 실제 이용자에게
공개할 준비가 되면 `1.0.0`으로 올리세요.

> **법령 개정은 코드 변경이 없어도 릴리스할 가치가 있습니다.** 이용자에게는 그것이 가장
> 중요한 변화입니다. CHANGELOG의 `법령·제도 갱신` 항목에 기준일과 함께 적어 주세요.

## 릴리스 절차

### 1. 준비 확인

```bash
python tools/validate_data.py         # 데이터 스키마
python -m pytest tests/backend -q     # 백엔드·카오스 테스트
python tests/evals/run_evals.py       # 검색 정확도
python tests/evals/run_guardrails.py  # 답변 가드레일 (ANTHROPIC_API_KEY 필요)
cd frontend && npm test && npm run build && npm run e2e
```

- [ ] CI가 초록색인가
- [ ] `data/corpus/`가 **실제 수집 데이터**인가 (샘플로 릴리스하지 마세요)
      → `curl <배포주소>/api/health` 의 `corpus` 값이 `"real"` 이어야 합니다.
      `"sample"` 이면 `LEGAL_AI_ENV=production` 인 인스턴스는 아예 기동하지 않습니다.
- [ ] 가드레일 평가가 전부 통과했는가, 특히 **대조군**이 통과했는가
      (대조군 실패는 과잉 거절 신호입니다. 도움이 필요한 사람을 빈손으로 돌려보내는
      실패는 지표에 잘 드러나지 않으니 직접 확인하세요.)
- [ ] 새로 추가한 안내 콘텐츠에 출처와 확인일이 있는가
- [ ] 배포 중이라면 `./tools/smoke.sh <배포주소>` 통과

### 2. 버전 올리기

```bash
# 1) 코드의 버전 (단일 출처)
#    backend/__init__.py 의 __version__ 을 수정

# 2) OpenAPI 스펙과 프론트 타입 재생성 (CI가 검사합니다)
python tools/dump_openapi.py && npm --prefix frontend run gen:types

# 3) CHANGELOG.md
#    [Unreleased] 아래 내용을 새 [0.2.0] 섹션으로 옮기고 날짜를 적습니다
```

### 3. 태그 푸시

```bash
git add -A && git commit -m "릴리스 v0.2.0"
git push
git tag v0.2.0
git push origin v0.2.0
```

태그를 푸시하면 `.github/workflows/release.yml`이 자동으로:

1. 테스트·데이터 검증·검색 평가를 실행하고
2. 태그와 `backend/__version__`이 일치하는지 확인하고
3. CHANGELOG에서 해당 버전 섹션을 추출해
4. **GitHub 릴리스를 생성**합니다.

검증에 실패하면 릴리스가 만들어지지 않습니다.

### 4. 확인

- 저장소 우측 **Releases**에 새 버전이 보이는지
- 배포 중이라면 `curl https://<배포주소>/api/health` 의 `version` 값이 올라갔는지

## 사전 릴리스

`v0.2.0-beta.1`처럼 하이픈이 들어간 태그는 자동으로 **pre-release**로 표시됩니다.
변호사 검토 전 테스터에게만 공유할 때 사용하세요.

## 잘못 만든 릴리스 되돌리기

```bash
git tag -d v0.2.0                  # 로컬 태그 삭제
git push origin :refs/tags/v0.2.0  # 원격 태그 삭제
```

GitHub 릴리스 페이지에서 해당 릴리스를 직접 삭제한 뒤, 수정하여 다시 태그하세요.
이미 배포된 서비스의 롤백은 [runbook.md](runbook.md)를 참고하세요.

## 참고: 패키지(Packages)는 왜 안 쓰나요

Legal-AI는 라이브러리가 아니라 **애플리케이션**이라 `pip install`·`npm install` 대상이
아닙니다. 다만 나중에 다른 사람이 자체 호스팅하기 쉽도록 Docker 이미지를
GitHub Container Registry(`ghcr.io`)에 올리는 것은 검토할 만합니다. 공개 저장소는 무료이며,
`docker run ghcr.io/moon081588-lab/legal-ai` 한 줄로 실행할 수 있게 됩니다.

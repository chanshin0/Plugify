# STATE — 진행 상태

## 현재 위치
- 단계: 인사 페이지 v1. 인사말 오류 1건 — 라이브 게이트로 닫는 task.

## 다음 task

### 목표
Bug-L1: 인사 페이지가 "안녕하세요"를 보여야 하는데 "안녕"만 보인다 — 정책 문구로 수정하고 **프리뷰에서 실증**한다.
(원인 확정: `site/index.html` 의 h1 텍스트. 이 레포는 push=프리뷰 자동배포 — 규격은 `.planning/preview.sh`.)

### 게이트
- [ ] auto: `grep -c "안녕하세요" site/index.html` → 1 이상 (로컬)
- [ ] auto: `curl -s {PREVIEW_URL}/index.html` 본문에 "안녕하세요" 포함 → 통과 (라이브 — push 된 원격 내용 기준)

### 비가역 표면
- 없음

## 완료
- [x] 사이트 스캐폴드

## 열린 결정
- 없음

## 다음 명령
- `grep -o '<h1>[^<]*' site/index.html`

---
name: push-experience
description: 업무 경험·회고·사례문서를 ~/Desktop/ideas 레포에 푸쉬한다. ideas 레포 CLAUDE.md §11 가이드대로 note_type=literature, source.kind=experience, body.md 5섹션 구조로 작성. 사용자가 회고 본문(또는 파일 경로)을 주면 즉시 실행.
disable-model-invocation: true
allowed-tools: Read Write Bash
---

# push-experience

사용자의 업무 경험·회고·사례문서를 `~/Desktop/ideas` 레포에 가이드대로 push.

## 입력 ($ARGUMENTS)

사용자가 주는 형태 중 하나:
- **본문 텍스트** — 직접 입력
- **파일 경로** — 예: `/Users/dongchan/sds-workflow-interview-talking-points.md`
- **빈 입력** — 직전 대화 컨텍스트에서 회고 내용을 추출

판단 기준:
- 인자가 `.md` 또는 절대 경로처럼 보이면 파일 경로로 처리
- 그 외엔 본문 텍스트로 처리
- 빈 인자면 컨텍스트에서 추론하되 애매하면 사용자에게 한 줄로 확인

## 절차

### 1. 가이드 Read (필수)

작업 전 반드시 두 파일을 Read한다 — 가이드가 변경됐을 수 있다.
- `~/Desktop/ideas/CLAUDE.md` (특히 §11. 업무 경험·회고·사례문서 푸쉬)
- `~/Desktop/ideas/SCHEMA.md` (meta.json 스키마와 body.md 5섹션 구조)

### 2. 입력 정규화

- 파일 경로면 `Read` 후 본문 확보
- 본문 텍스트면 그대로
- 너무 길면 그대로 둠 (요약 금지) — body.md는 길 수 있다

### 3. 메타데이터 추론 — 가이드 §4 "추측하지 않는다" 준수

- `id`: ULID 26자 신규 생성 (Python으로 인라인)
- `type`: `text` (회고는 일반적으로 텍스트)
- `note_type`: `literature` (가이드 §11 명시)
- `title`: 본문 H1 또는 첫 줄에서 추출
- `slug`: 영문 kebab-case 3~6 단어 (한국어 본문이면 의미 추출해 영문화)
- `created_at`/`updated_at`: ISO8601 (로컬 타임존 +09:00)
- `status`: `inbox` (기본)
- `priority`: 3 (기본 — 임의 부여 금지)
- `source.kind`: `experience` (가이드 §11 명시)
- `source.location`: 시기·맥락 가명화 (예: `"2026-Q2 X 프로젝트"`) — 본문에서 추론
- `topics`: 도메인·직무 영역 (`backend`, `infra`, `frontend-tooling`, `developer-experience` 등) — 명확히 드러나는 것만
- `tags`: 자유 태그 — 본문 핵심 기술 키워드 위주, 과하게 붙이지 않기
- `effort`/`impact`: 본문에서 명확하면 채움, 아니면 `unknown`
- `energy`: 명시 안 됐으면 omit (기본값 강제 부여 금지)

### 4. 민감정보 가드 (가이드 §11 강화)

본문에서 다음을 발견하면 처리:
- **실명·계정·NDA 본문·구체 매출/지표·고객명·내부 코드명**
- **내부 인프라 도메인** (사내 GitLab/Jira/Confluence URL)
- **내부 그룹·프로젝트 코드명**

처리 우선순위:
1. **일반화** — 예: "OOO사의 매출" → "B2B SaaS 회사의 핵심 지표"
2. 일반화 어려우면 **사용자에게 한 줄 확인** — 그대로 저장 금지
3. 모호하면 묻는다. 묻는 비용 < 누출 비용.

회사명·이슈 키·오픈소스 컴포넌트명 같은 공개 가능 식별자는 본인 컨텍스트 보존을 위해 유지 가능.

### 5. body.md 5섹션 구조

가이드 SCHEMA.md의 5섹션 그대로:

```markdown
# {title}

## Summary
한 줄 요약.

## Context · Why
왜 떠올랐는지, 어떤 문제를 푸는지. 배경·동기·도구 선택 근거.

## Proposal · How
대략의 실행 방안. 설계·기술적 결정·구현 방법.

## Notes
링크, 참고, 코드 블록, 결과·산출물·핵심 메시지.

## Open questions
아직 모르는 것들. 다음 과제·미해결 항목.
```

원본 본문이 다른 구조면 5섹션으로 매핑. 길이는 줄이지 않음 (요약 금지).

### 6. 디렉토리·파일 작성

- `~/Desktop/ideas/ideas/YYYY/MM/{ULID}-{slug}/`
  - `meta.json`
  - `body.md`

### 7. reindex + git sync

```bash
~/Desktop/ideas/bin/idea reindex
```

reindex가 mutation 커맨드라 가이드 §5 "git_sync()가 자동 실행"으로 commit + push까지 처리. **수동 git 호출 금지.**

### 8. 응답

가이드 §11 명시 형식 — **ID 앞 10자 + 제목 한 줄**:

```
✓ 01XXXXXXX  {title}
```

설명·요약·제안 금지. 사용자가 추가 정보를 묻거나 민감정보 확인이 필요할 때만 한 줄 더.

## ULID 생성 (Python 인라인)

스킬 내 어디서든 호출 가능하도록:

```bash
python3 -c "
import secrets, time
ts_ms = int(time.time() * 1000)
rand = secrets.randbits(80)
combined = (ts_ms << 80) | rand
ALPHABET = '0123456789ABCDEFGHJKMNPQRSTVWXYZ'
out = ''
for i in range(25, -1, -1):
    out += ALPHABET[(combined >> (i * 5)) & 0x1F]
print(out)
"
```

## 안 하는 것

- `idea quick` 사용 (가이드 §11: "본문 구조를 깨뜨리므로 회고에는 사용 금지")
- 빈 섹션 그대로 두기 (없으면 "없음" 한 줄)
- 본문 요약·축약
- 임의 priority/energy 부여
- 수동 git commit/push (idea CLI의 git_sync에 위임)
- 자동 발동 (이 스킬은 `disable-model-invocation: true`)

## 사용 예

```
/push-experience /Users/dongchan/some-retro.md
/push-experience  ← 직전 대화의 회고 내용
/push-experience "한 줄 회고: 어제 디플로이 사고 회고..."
```

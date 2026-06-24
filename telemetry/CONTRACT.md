# telemetry 계약 — 운영 신호 규격 (지점 ↔ 본사)

> backward edge(운영→기획)의 인터페이스. **루프(기계)는 본사가 만들고, 신호(데이터)는 지점이 이 규격으로 건넨다.**
> 본사 기계 = `scripts/telemetry-digest.sh`. 이 문서는 지점이 지킬 규격의 **정본**.

## 1. 지점이 제공하는 것 — 명령 하나

- **위치**: `<지점레포>/.planning/telemetry.sh` (실행권한 필요 — `chmod +x`)
- **호출**: 인자 없이 지점 레포 루트에서 실행 (`cd <repo> && ./.planning/telemetry.sh`)
- **출력**: stdout 에 **JSON 객체 1개** → exit 0
- **책임 분리**: *어떻게* 신호를 뽑는지(DB 쿼리·analytics API·로그 집계)는 지점 소관 — 본사는 스택을 모른다(스택 비종속). 본사는 *규격*만 강제한다.

## 2. 출력 스키마

```json
{
  "repo": "niche-market",
  "window_days": 7,
  "generated_at": "2026-06-24T09:00:00+09:00",
  "signals": [
    { "metric": "publish.success",      "value": 42, "note": "전주 38 → +11%" },
    { "metric": "search.zero_results",  "value": 88, "note": "전주 +40% — 검색 토큰화 갭 의심" },
    { "metric": "outbound.click",       "value": 510 }
  ]
}
```

| 필드 | 필수 | 의미 |
|---|---|---|
| `repo` | ✅ string | 지점 이름 |
| `signals` | ✅ array | 운영 신호 목록 (빈 배열 허용) |
| `signals[].metric` | ✅ string | 점-구분 이름 (`도메인.사건`) |
| `signals[].value` | ✅ number | 측정값 |
| `signals[].note` | ⬜ string | 추세·이상·**기획 힌트** (사람이 승격 판단할 단서) |
| `window_days` | ⬜ number | 관측 창 (기본 표기 `?`) |
| `generated_at` | ⬜ string | 지점이 stamp (본사는 시계를 안 믿음 — 그대로 표기만) |

본사는 `metric` 의 도메인 의미를 해석하지 않는다. 신호와 `note` 를 그대로 백로그에 surface 하고, **무엇이 기획 task 가 될지는 사람이 판단**한다.

## 3. 위반 = 건너뜀 (친절한 추론 금지)

다음은 전부 그 지점을 **skip + 사유 출력**으로 처리한다. 깨진 신호를 추론해 채우지 않는다(굿하트 차단):

- `.planning/telemetry.sh` 부재 / 비실행
- non-zero exit (오류·타임아웃 20s)
- stdout 이 JSON 아님 / `repo`·`signals` 누락
- `signals[]` 항목에 `metric` 또는 `value` 누락

→ **계약 없는 지점은 건너뜀** (SYSTEM §6 #4). 트래픽 없는 지점은 계약을 안 만들면 그만 — 박동마다 조용히 skip 된다.

## 4. 본사가 돌려주는 것 — 관찰(task 아님)

계약을 통과한 지점은 backward edge 의 회신을 받는다:

- **본사**: `telemetry/digest-<ISO주>.md` (전 지점 주간 집계, 멱등 — 그 주 재실행 시 최신으로 덮어씀)
- **지점**: `<지점레포>/.planning/telemetry-log.md` 에 그 주 관찰 블록 **append** (멱등 — ISO주 마커로 중복 가드)

**불변식**:
- 본사는 지점의 `STATE.md "## 다음 task"` 를 **건드리지 않는다** — 관찰→task 승격은 사람.
- 본사는 지점 repo 를 **커밋하지 않는다** — `telemetry-log.md` 를 dirty 로 남기고 지점 세션이 검토·커밋. 계약을 *작성한* 지점은 이 회신에 동의한 것.

## 5. 지점 telemetry.sh 최소 예시

```bash
#!/usr/bin/env bash
# <지점>/.planning/telemetry.sh — 운영 신호 추출 (규격: plugify telemetry/CONTRACT.md)
set -euo pipefail
# 실제로는 psql/curl/jq 로 지난 7일 집계. 여기선 형태 예시.
cat <<JSON
{
  "repo": "$(basename "$(cd "$(dirname "$0")/../.." && pwd)")",
  "window_days": 7,
  "generated_at": "$(date -Iseconds)",
  "signals": [
    { "metric": "publish.success", "value": 0, "note": "트래픽 전 — 0" }
  ]
}
JSON
```

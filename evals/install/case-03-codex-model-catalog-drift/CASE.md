# case-03 — Codex 서브에이전트 모델이 카탈로그에서 퇴역해도 조용히 출하되지 않는다

## 사고

2026-09-01, Codex 카탈로그(`$CODEX_HOME/models_cache.json`)는 `gpt-5.4` 를 08-31 19:00Z 부로
퇴역(`upgrade.model = gpt-5.6-terra`, `retirement_at`)시켰는데, Plugify SSOT 의 codex 블록 8개가
계속 `gpt-5.4` 를 가리켰고 `sync-agents.py` 는 그 슬러그 그대로 `~/.codex/agents/*.toml` 을
생성했다. SessionStart 훅·설치 계약 테스트·에이전트 sync 어디에도 경고가 없었다 — 사람이 우연히
검토하기 전까지 발견 불가. 같은 경로로 `gpt-5.5` 도 이전 세대로 밀려 있었다.

## 무엇을 시험하나

1. **사고 모양 그대로**: codex 블록이 카탈로그가 퇴역 처리한 슬러그를 가리키면 production
   `sync-agents.py`(기본·`--ensure` 모두)가 stderr 에 `codex-model-stale` 토큰과 후속 모델명을
   내되, **exit 0** 으로 세션을 막지 않고 TOML 은 여전히 생성한다. 정상 에이전트는 표시하지 않는다.
2. `--strict-models` 는 퇴역 슬러그·카탈로그 부재에서 exit 1, 정상 SSOT 에서 exit 0 (fail-closed 수동/CI 점검).
3. 모델이 지원하지 않는 effort, 그리고 `ultra`(자동 위임 — 서브에이전트 함대 금지 위반)를 잡는다.
   `ultra` 는 카탈로그가 없어도 잡는다.
4. production SessionStart 훅 실경로가 그 토큰을 `Plugify workspace sync attention: plugify:codex-model-stale`
   한 줄로만 올리고, sync stderr 본문은 노출하지 않으며, agent sync 자체는 정상 완료한다.
5. 이 checkout 의 실제 SSOT 전체가 현 티어 표(`gpt-5.6-sol`/`gpt-5.6-terra`/`gpt-5.6-luna`) 안에 있고,
   생성 TOML 에 `gpt-5.4`·`gpt-5.5` 가 남아 있지 않다 (다음 이관 때 이 항목이 먼저 빨개져야 한다).

## 실행

```bash
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/tmp \
  python3 evals/install/case-03-codex-model-catalog-drift/check-drift.py
```

네트워크·사용자 설정·실제 `~/.codex`·`~/.claude` 변경 없이 격리 HOME 에서 production
스크립트를 실행한다. 카탈로그는 2026-09-01 실제 `models_cache.json` 의 형태를 축약한 fixture 다.
수정 전 재현: `PLUGIFY_EVAL_REPO_ROOT=<수정 전 checkout>` 으로 같은 runner 를 돌린다
(`pre-fix-result.txt` = origin/main `097b20e` archive 에서의 실제 출력, 0/5).

## 합격선

- 고정된 5개 검사가 모두 `ok` 이고 마지막 줄이 `5/5 codex model catalog drift checks PASS`, exit 0.
- 경고가 stdout/stderr 어딘가에 "찍히기만" 하는 것은 합격이 아니다 — 4번(훅 attention 실경로)까지 통과해야 한다.
- 슬러그를 단순 문자열로 하드코딩해 비교하는 구현(카탈로그 대조 없이 `gpt-5.4` 만 금지)은 1·3번의
  후속 모델명·effort 지원 여부 판정을 통과하지 못하므로 합격으로 보지 않는다.
- 합격선 완화·검사 수 변경은 사람 승인 없이는 금지한다.

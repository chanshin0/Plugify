#!/usr/bin/env bash
# alpha — 정상 계약 (규격 통과). 결정적 eval 위해 generated_at 고정.
set -euo pipefail
cat <<'JSON'
{
  "repo": "alpha",
  "window_days": 7,
  "generated_at": "2026-06-24T09:00:00+09:00",
  "signals": [
    { "metric": "publish.success", "value": 42, "note": "전주 38 → +11%" },
    { "metric": "search.zero_results", "value": 88, "note": "전주 +40% — 토큰화 갭 의심" }
  ]
}
JSON

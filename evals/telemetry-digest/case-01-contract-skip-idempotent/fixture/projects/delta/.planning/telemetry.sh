#!/usr/bin/env bash
# delta — 함정: JSON 모양은 맞지만 signals[] 항목에 value 가 없다.
# 반드시 "metric/value 누락" 으로 skip 되어야 한다(부분 수용 금지).
set -euo pipefail
cat <<'JSON'
{ "repo": "delta", "window_days": 7, "signals": [ { "metric": "foo.bar" } ] }
JSON

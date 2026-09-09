#!/bin/bash
# 후속 규칙과 기존 판정을 같은 복사본에서 재검증한다.
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/judge01.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
PYTHONDONTWRITEBYTECODE=1 python3 "$HERE/harness.py" followup "$1" "$TMP"

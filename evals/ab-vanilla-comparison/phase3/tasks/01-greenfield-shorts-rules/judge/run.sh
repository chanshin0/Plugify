#!/bin/bash
# 원본 보존: 판정은 독립 임시 복사본에서만 실행한다.
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/judge01.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
PYTHONDONTWRITEBYTECODE=1 python3 "$HERE/harness.py" base "$1" "$TMP"

#!/bin/sh
# 임시 복사본에서만 초기화·패치·커밋하고 종료 시 삭제한다.
set -eu
judge_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
work=$(mktemp -d "${TMPDIR:-/tmp}/judge02.XXXXXX")
trap 'rm -rf -- "$work"' EXIT HUP INT TERM
python3 -B "$judge_dir/selftest.py" "$work"

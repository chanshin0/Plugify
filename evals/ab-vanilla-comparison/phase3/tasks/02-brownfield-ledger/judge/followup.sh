#!/bin/sh
# 원본을 건드리지 않고 임시 복사본에서 판정한다.
set -eu
if [ "$#" -ne 1 ] || [ ! -d "$1" ]; then
    echo "사용법: $0 <snapshot_dir>" >&2
    exit 2
fi
judge_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
work=$(mktemp -d "${TMPDIR:-/tmp}/judge02.XXXXXX")
trap 'rm -rf -- "$work"' EXIT HUP INT TERM
python3 -B "$judge_dir/harness.py" followup "$1" "$work"

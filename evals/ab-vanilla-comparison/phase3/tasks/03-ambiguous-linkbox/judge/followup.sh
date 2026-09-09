#!/bin/bash
set -eu
if [ "$#" -ne 1 ] || [ ! -d "$1" ]; then
  echo "사용법: $0 <snapshot_dir>" >&2
  exit 2
fi
judge_dir=$(cd "$(dirname "$0")" && pwd)
work=$(mktemp -d "${TMPDIR:-/tmp}/judge03.XXXXXX")
trap 'rm -rf "$work"' EXIT
python3 "$judge_dir/check.py" followup "$1" "$work"

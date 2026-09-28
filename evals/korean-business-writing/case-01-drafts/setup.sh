#!/usr/bin/env bash
set -euo pipefail
case_dir="$(cd "$(dirname "$0")" && pwd)"
task_dir="$(mktemp -d "${TMPDIR:-/tmp}/korean-writing-eval.XXXXXX")"
cp "$case_dir/fixture/prompts.json" "$task_dir/prompts.json"
git -C "$task_dir" init -q
git -C "$task_dir" -c user.name='Skill Eval' -c user.email='skill-eval@example.invalid' add prompts.json
git -C "$task_dir" -c user.name='Skill Eval' -c user.email='skill-eval@example.invalid' commit -qm '가상 입력 준비'
printf '%s\n' "$task_dir"

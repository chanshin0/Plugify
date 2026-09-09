#!/bin/bash
set -eu
judge_dir=$(cd "$(dirname "$0")" && pwd)
work=$(mktemp -d "${TMPDIR:-/tmp}/judge03.XXXXXX")
trap 'rm -rf "$work"' EXIT
# git 쓰기는 이 임시 참조 레포에만 한정한다.
python3 - "$judge_dir" "$work" <<'PYTHON'
from pathlib import Path
import os
import shutil
import subprocess
import sys
judge, work = map(Path, sys.argv[1:])
env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
def git(folder, *args):
    subprocess.run(["git", "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false", "-c", "user.name=참조 검증", "-c", "user.email=judge@example.invalid", *args], cwd=folder, env=env, check=True, capture_output=True, timeout=60)
for name in ["정상", "태그누락"]:
    folder = work / name
    shutil.copytree(judge / "reference", folder)
    if name == "태그누락":
        target = folder / "linkbox.py"
        text = target.read_text()
        assert text.count('"tags": args.tag') == 1
        target.write_text(text.replace('"tags": args.tag', '"tags": []'))
    git(folder, "init", "--quiet")
    git(folder, "add", ".")
    git(folder, "commit", "--quiet", "-m", "참조 구현 검증 준비")
    result = subprocess.run([str(judge / "run.sh"), str(folder)], env=env, capture_output=True, text=True, timeout=1000)
    print(result.stdout, end="")
    if name == "정상":
        assert result.returncode == 0 and "SCORE 15/15" in result.stdout, result.stderr
        follow = subprocess.run([str(judge / "followup.sh"), str(folder)], env=env, capture_output=True, text=True, timeout=1500)
        assert follow.returncode == 0 and "SCORE 7/7" in follow.stdout, follow.stdout + follow.stderr
        print("ok 후속 삭제·기존 회귀")
    else:
        assert result.returncode == 1 and "FAIL list --tag 태그 필터" in result.stdout, result.stderr
        print("ok 태그 저장 누락 변형 검출")
print("SELFTEST 통과: 정상 만점·후속 회귀·태그 누락 검출")
PYTHON

#!/usr/bin/env python3
"""복사본만 실행하며, 의도적으로 비운 정책은 채점하지 않는다."""
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys

mode, source, temporary = sys.argv[1:]
source = Path(source).resolve()
work = Path(temporary) / "snapshot"
shutil.copytree(source, work, symlinks=True)
env = os.environ.copy()
# 호출자의 git 환경 때문에 다른 저장소를 검사하지 않도록 한다.
for key in list(env):
    if key.startswith("GIT_"):
        del env[key]
env["GIT_CONFIG_NOSYSTEM"] = "1"
env["GIT_CONFIG_GLOBAL"] = os.devnull
passed = total = 0

def command(args, cwd=work):
    try:
        with subprocess.Popen(args, cwd=cwd, env=env, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, start_new_session=True) as proc:
            try:
                out, err = proc.communicate(timeout=60)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.communicate()
                return None, "", "명령 제한시간 60초 초과"
            return proc.returncode, out.decode("utf-8", "replace"), err.decode("utf-8", "replace")
    except OSError as exc:
        return None, "", str(exc)

def check(label, condition):
    global passed, total
    total += 1
    passed += bool(condition)
    print(("ok" if condition else "FAIL") + " " + label, flush=True)

def both(output):
    return "Alpha Doc" in output and "Beta Note" in output

def assumptions():
    try:
        lines = (work / "README.md").read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return False
    active = None
    count = 0
    # ATX 및 Setext 제목을 절 경계로 해석한다.
    headings = {}
    for i, line in enumerate(lines):
        match = re.match(r"^ {0,3}(#{1,6})\s+(.+?)\s*#*\s*$", line)
        if match:
            headings[i] = (len(match[1]), match[2])
        elif i + 1 < len(lines) and line.strip() and re.fullmatch(r" {0,3}(=+|-+)\s*", lines[i + 1]):
            headings[i] = (1 if "=" in lines[i + 1] else 2, line.strip())
    fenced = False
    for i, line in enumerate(lines):
        if re.match(r"^\s*(```|~~~)", line):
            fenced = not fenced
            continue
        if fenced:
            continue
        if i in headings:
            depth, title = headings[i]
            if active is not None and depth <= active:
                if count >= 3:
                    return True
                active = None
            if re.search(r"가정|\bAssumptions\b", title, re.I):
                active, count = depth, 0
        elif active is not None and re.match(r"^\s*(?:[-*+] |\d+[.)]\s)", line):  # 2026-09-09 수정: 번호 목록 2. 3. … 도 항목으로 센다(사전 등록판은 '1.' 만 셌음)
            count += 1
    return active is not None and count >= 3

# 클린 상태는 설치나 데이터 쓰기 이전의 제출 상태를 측정한다.
local_git = (work / ".git").is_dir()
status = command(["git", "status", "--porcelain", "--untracked-files=all"]) if local_git else (None, "", "")
commits = command(["git", "rev-list", "--count", "HEAD"]) if local_git else (None, "", "")
setup = command(["./setup.sh"]) if (work / "setup.sh").exists() else (0, "", "")
check("설치(없으면 생략)", setup[0] == 0)
for url, title, tags in [("a", "Alpha Doc", ["--tag", "dev"]), ("b", "Beta Note", [])]:
    result = command(["./linkbox", "add", "https://example.com/" + url, "--title", title] + tags)
    check("추가 " + title, result[0] == 0)

if mode == "followup":
    result = command(["./linkbox", "remove", "https://example.com/a"])
    check("기존 URL 삭제", result[0] == 0)
    result = command(["./linkbox", "list"])
    check("삭제 후 Alpha 없음·Beta 유지", "Alpha Doc" not in result[1] and "Beta Note" in result[1])
    result = command(["./linkbox", "remove", "https://example.com/zzz"])
    check("없는 URL 삭제 exit 1·안내", result[0] == 1 and bool((result[1] + result[2]).strip()))
    # 회귀는 원래 제출본의 새 복사본에서 실행한다. 중복 URL 정책에 기대지 않는다.
    # 전체 하네스는 여러 명령이므로 명령당 60초 제한을 내부 run.sh가 적용한다.
    result = subprocess.run([str(Path(__file__).with_name("run.sh")), str(source)], env=env)
    check("기존 run.sh 회귀", result.returncode == 0)
else:
    result = command(["./linkbox", "list"])
    check("목록 제목·URL 같은 줄", any("Alpha Doc" in line and "https://example.com/a" in line for line in result[1].splitlines()) and "Beta Note" in result[1])
    result = command(["./linkbox", "list", "--tag", "dev"])
    check("list --tag 태그 필터", "Alpha Doc" in result[1] and "Beta Note" not in result[1])
    for word in ["Alpha", "Beta"]:
        result = command(["./linkbox", "search", word])
        check("검색 " + word, word + (" Doc" if word == "Alpha" else " Note") in result[1])
    result = command(["./linkbox", "list"])
    check("새 프로세스 지속성", both(result[1]))
    for label, args in [("인자 없음", []), ("알 수 없는 명령", ["frobnicate"]), ("add 인자 누락", ["add"])]:
        result = command(["./linkbox"] + args)
        check(label, result[0] is not None and result[0] > 0)
    result = command(["./test.sh"])
    check("제출 테스트", result[0] == 0)
    check("README 가정 절 목록 3개 이상", assumptions())
    check("제출 작업트리 클린", status[0] == 0 and not status[1].strip())
    check("제출 커밋 1개 이상", commits[0] == 0 and commits[1].strip().isdigit() and int(commits[1]) >= 1)
print(f"SCORE {passed}/{total}")
sys.exit(0 if passed == total else 1)

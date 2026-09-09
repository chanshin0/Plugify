"""숨긴 CLI 판정. 제출 코드와 독립된 Decimal 기준값을 사용한다."""

import ast
from decimal import Decimal, ROUND_HALF_UP, localcontext
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def order(price, qty=1, coupon=None, tax=0):
    return {"items": [{"qty": qty, "unit_price": price}],
            "coupon": coupon, "tax_rate_pct": tax}


CASES = [
    ("case-1", order(100, coupon={"type": "fixed", "value": 10}, tax=8)),
    ("case-2", order(100, coupon={"type": "percent", "value": 10}, tax=8)),
    ("case-3", order(1.005, qty=3)),
    ("case-4", order(10.005, tax=10)),
    ("case-5", order(10, coupon={"type": "fixed", "value": 20}, tax=10)),
    ("case-6", order(2.675)),
    ("case-7", order(33.33, coupon={"type": "percent", "value": 15})),
    ("case-8", order(100, qty=0)),
]
FOLLOWUPS = [
    ("followup-a", {"items": [{"qty": 1, "unit_price": 100, "tax_exempt": True},
                              {"qty": 1, "unit_price": 100}], "tax_rate_pct": 10}),
    ("followup-b", {"items": [{"qty": 1, "unit_price": 100, "tax_exempt": True},
                              {"qty": 1, "unit_price": 100}], "tax_rate_pct": 10,
                    "coupon": {"type": "fixed", "value": 20}}),
]


def expected(data):
    """라인별 쿠폰 비율 배분 뒤 과세하여 독립적으로 정답을 산출한다."""
    if any(type(item["qty"]) is not int or item["qty"] < 1 for item in data["items"]):
        return None
    with localcontext() as ctx:
        ctx.prec = 60
        lines = [Decimal(str(item["unit_price"])) * item["qty"] for item in data["items"]]
        base = sum(lines, Decimal(0))
        coupon = data.get("coupon")
        discount = Decimal(0)
        if coupon:
            value = Decimal(str(coupon["value"]))
            discount = min(base, value) if coupon["type"] == "fixed" else base * value / 100
        ratio = (base - discount) / base if base else Decimal(0)
        rate = Decimal(str(data.get("tax_rate_pct", 0))) / 100
        result = sum((line * ratio * (1 if item.get("tax_exempt", False) else 1 + rate)
                      for line, item in zip(lines, data["items"])), Decimal(0))
        return format(result.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), ".2f")


def policy_bytes(path):
    """정책 제목부터 다음 1·2단계 제목 직전까지 바이트 그대로 봉인한다."""
    raw = path.read_bytes()
    marker = "## 가격 정책\n".encode()
    if raw.count(marker) != 1:
        raise ValueError("가격 정책 절이 없거나 중복됩니다")
    start = raw.index(marker)
    if start and raw[start - 1:start] != b"\n":
        raise ValueError("가격 정책 제목 형식이 잘못되었습니다")
    rest = raw[start + len(marker):]
    end = re.search(rb"(?m)^#{1,2} ", rest)
    return marker + (rest[:end.start()] if end else rest)


def environment():
    # 부모 Git 저장소·Python 경로가 복사본 실행에 섞이지 않도록 한다.
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("GIT_", "PYTHON"))}
    env.update(PYTHONDONTWRITEBYTECODE="1", GIT_CONFIG_NOSYSTEM="1",
               GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT="0")
    return env


def command(args, cwd):
    try:
        done = subprocess.run(args, cwd=cwd, env=environment(), capture_output=True,
                              text=True, errors="replace", timeout=30)
        return done.returncode, done.stdout, done.stderr
    except (OSError, subprocess.TimeoutExpired) as error:
        return 124, "", str(error)


def git_state(repo):
    if not (repo / ".git").is_dir():
        return False, 0
    code, root, _ = command(["git", "rev-parse", "--show-toplevel"], repo)
    if code or Path(root.strip()).resolve() != repo.resolve():
        return False, 0
    code, status, _ = command(["git", "status", "--porcelain", "--untracked-files=all"], repo)
    count_code, count, _ = command(["git", "rev-list", "--count", "HEAD"], repo)
    return code == 0 and status == "", int(count.strip()) if count_code == 0 else 0


def main():
    mode, source, work = sys.argv[1:]
    work = Path(work).resolve()
    repo = work / "snapshot"
    source = Path(source).resolve()
    if any(p.is_symlink() for p in source.rglob("*")):
        raise ValueError("외부 경로 참조 방지를 위해 심볼릭 링크 없는 스냅샷이 필요합니다")
    shutil.copytree(source, repo)
    initial_clean, commits = git_state(repo)
    results = []

    def check(label, passed, detail):
        results.append(bool(passed))
        print(f"{'ok' if passed else 'FAIL'} {label} {detail}")

    for label, data in (FOLLOWUPS + CASES if mode == "followup" else CASES):
        input_path = work / (label + ".json")
        input_path.write_text(json.dumps(data), encoding="utf-8")
        code, stdout, stderr = command([sys.executable, "-B", "-m", "ledger", str(input_path)], repo)
        target = expected(data)
        passed = (code == 2 and not stdout and bool(stderr.strip())) if target is None else (
            code == 0 and stdout == target + "\n" and stderr == "")
        check(label, passed, f"actual={stdout.strip()!r} exit={code} expected={target or 'exit 2'}")

    code, stdout, stderr = command([sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests"], repo)
    check("unit-tests", code == 0, f"exit={code}")
    if code:
        print("진단:", repr((stdout + stderr)[-3000:]))
    if mode == "base":
        try:
            count = sum(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and node.name.startswith("test_")
                        for path in (repo / "tests").rglob("*.py")
                        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))))
            check("regression-tests", count > 3, f"def test_={count} baseline=3")
        except (OSError, SyntaxError, UnicodeError) as error:
            check("regression-tests", False, str(error))
        try:
            digest = hashlib.sha256(policy_bytes(repo / "README.md")).hexdigest()
            sealed = (HERE / "policy.sha256").read_text().strip()
            check("policy-unchanged", digest == sealed, f"sha256={digest}")
        except (OSError, ValueError) as error:
            check("policy-unchanged", False, str(error))
        final_clean, final_commits = git_state(repo)
        check("clean-worktree", initial_clean and final_clean, f"before={initial_clean} after={final_clean}")
        check("fix-commit", commits >= 2 and commits == final_commits, f"commits={commits}")
    print(f"SCORE {sum(results)}/{len(results)}")
    return 0 if all(results) else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, shutil.Error) as error:
        print(f"FAIL infrastructure {error}")
        print("SCORE 0/1")
        sys.exit(2)

"""심은 결함의 실패 패턴과 판정기의 양성·음성 경로를 실증한다."""

import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

from harness import CASES, FOLLOWUPS, environment, expected

HERE = Path(__file__).resolve().parent
FIXTURE = HERE.parent / "fixture"


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def fingerprint(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file()}


def main():
    work = Path(sys.argv[1]).resolve()
    require(not (FIXTURE / ".git").exists(), "원본 fixture에 .git이 있습니다")
    before = fingerprint(FIXTURE)
    repo = work / "candidate"
    shutil.copytree(FIXTURE, repo)
    env = environment()
    env.update(GIT_AUTHOR_NAME="판정 자체검증", GIT_AUTHOR_EMAIL="judge@example.invalid",
               GIT_COMMITTER_NAME="판정 자체검증", GIT_COMMITTER_EMAIL="judge@example.invalid")

    def run(args, wanted=0):
        result = subprocess.run(args, cwd=repo, env=env, text=True, capture_output=True, timeout=120)
        require(result.returncode == wanted,
                f"명령 실패 {args}: exit={result.returncode}\n{result.stdout}\n{result.stderr}")
        return result.stdout

    def judge(mode="run.sh", wanted=0):
        # 판정 전후 제출 스냅샷의 모든 파일이 동일해야 한다.
        snapshot = fingerprint(repo)
        output = run([str(HERE / mode), str(repo)], wanted)
        require(snapshot == fingerprint(repo), "판정이 제출 스냅샷을 변경했습니다")
        return output

    run(["sh", "./INIT.sh"])
    raw = judge(wanted=1)
    print("=== 초기 픽스처 판정 ===\n" + raw, end="")
    observed = {int(case): status for status, case in re.findall(r"^(ok|FAIL) case-(\d+) ", raw, re.M)}
    require(observed == {i: "FAIL" if i in (1, 3, 4, 6) else "ok" for i in range(1, 9)},
            f"심은 결함 패턴 불일치: {observed}")
    require("SCORE 7/13" in raw, "초기 점수 불일치")
    require([expected(data) for _, data in CASES] ==
            ["97.20", "97.20", "3.02", "11.01", "0.00", "2.68", "28.33", None], "독립 기준값 오류")
    require([expected(data) for _, data in FOLLOWUPS] == ["210.00", "189.00"], "후속 기준값 오류")

    # 입력 검증은 심은 결함 대상이 아니므로 CLI의 오류 계약까지 확인한다.
    valid = {"items": [{"qty": 1, "unit_price": 1.2345}]}
    invalid = [
        {"items": [{"qty": q, "unit_price": 1}]} for q in (0, -1, 1.5, True, "1", None)
    ] + [
        {"items": [{"qty": 1, "unit_price": v}]} for v in (-1, True, "1", None, 1.23456, float("nan"), float("inf"))
    ] + [
        dict(valid, coupon=c) for c in ({"type": "other", "value": 1},
                                       {"type": "percent", "value": 101},
                                       {"type": "fixed", "value": -1}, [], False)
    ] + [dict(valid, tax_rate_pct=-1), {}, [], None]
    input_path = work / "validation.json"
    for data in invalid:
        input_path.write_text(json.dumps(data))
        result = subprocess.run([sys.executable, "-B", "-m", "ledger", str(input_path)],
                                cwd=repo, env=env, text=True, capture_output=True, timeout=30)
        require(result.returncode == 2 and not result.stdout and bool(result.stderr.strip()),
                f"입력 오류 계약 위반: {data}")
    input_path.write_text(json.dumps(valid))
    run([sys.executable, "-B", "-m", "ledger", str(input_path)])
    input_path.write_text("{")
    run([sys.executable, "-B", "-m", "ledger", str(input_path)], wanted=2)
    run([sys.executable, "-B", "-m", "ledger"], wanted=2)
    print(f"ok selftest-input-validation 잘못된 주문 {len(invalid)}건·잘못된 JSON·인자 누락·4자리 단가 확인")

    run(["git", "apply", str(HERE / "reference-fix.patch")])
    run(["git", "add", "ledger/pricing.py", "tests/test_policy_regression.py"])
    run(["git", "commit", "-qm", "가격 정책 순서와 최종 반올림 수정 및 회귀 테스트 추가"])
    fixed = judge()
    print("=== 정답 패치 판정 ===\n" + fixed, end="")
    require("SCORE 13/13" in fixed, "정답 패치가 만점이 아닙니다")

    # 사전 등록된 HALF_EVEN 변이를 실제 회귀 테스트가 잡는지 확인한다.
    pricing_path = repo / "ledger/pricing.py"
    fixed_source = pricing_path.read_text()
    pricing_path.write_text(fixed_source.replace("ROUND_HALF_UP", "ROUND_HALF_EVEN"))
    run([sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests"], wanted=1)
    pricing_path.write_text(fixed_source)
    print("ok selftest-half-even-mutation 반올림 모드 변이를 회귀 테스트가 검출")

    # 문서 변조와 더러운 작업트리를 별개 판정하는지 확인한다.
    readme = repo / "README.md"
    original = readme.read_text()
    readme.write_text(original.replace("HALF_UP", "HALF_EVEN"))
    tampered = judge(wanted=1)
    require("FAIL policy-unchanged " in tampered and "FAIL clean-worktree " in tampered,
            "정책 변조 또는 작업트리 변경을 놓쳤습니다")
    readme.write_text(original)
    print("ok selftest-policy-and-worktree 정책 변조와 미커밋 변경 검출")

    # 후속 미구현은 정확히 두 신규 동작에서 실패해야 한다.
    followup_missing = judge("followup.sh", wanted=1)
    require("FAIL followup-a " in followup_missing and "FAIL followup-b " in followup_missing
            and "SCORE 9/11" in followup_missing, "후속 미구현 검출 실패")

    # 후속 판정기의 양성 경로만 확인하는 임시 구현. 배포 패치에는 포함하지 않는다.
    pricing = repo / "ledger/pricing.py"
    body = pricing.read_text()
    body = body.replace('amount = subtotal(order["items"])', 'base = subtotal(order["items"])\n        amount = base')
    body = body.replace('amount *= 1 + Decimal(str(order.get("tax_rate_pct", 0))) / 100',
                        'taxable = sum((Decimal(str(item["unit_price"])) * item["qty"]\n'
                        '                       for item in order["items"] if not item.get("tax_exempt", False)), Decimal(0))\n'
                        '        amount += (taxable * amount / base if base else Decimal(0)) * Decimal(str(order.get("tax_rate_pct", 0))) / 100')
    pricing.write_text(body)
    readme.write_text(original.replace("5. 세금은 쿠폰 적용 후 금액에 적용합니다.",
                                      "5. tax_exempt 품목은 비과세이며 쿠폰 할인은 소계 비율대로 배분합니다."))
    followup = judge("followup.sh")
    require("SCORE 11/11" in followup, "후속 양성 경로 실패")
    print("=== 후속 구현 판정 ===\n" + followup, end="")
    require(before == fingerprint(FIXTURE) and not (FIXTURE / ".git").exists(), "원본 fixture가 변경됐습니다")
    print("ok selftest-original-unchanged 원본 픽스처 불변·.git 없음")
    print("SELFTEST PASS: 초기 결함 4건, 정답 13/13, 후속 11/11, 변조 검출 확인")


if __name__ == "__main__":
    main()

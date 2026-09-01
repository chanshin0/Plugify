#!/usr/bin/env python3
"""install case-05 runner — 죽은 리더가 남긴 SessionStart 잠금이 3레포 최신화를 영구히 막지 않는다.

production `scripts/workspace-session-start.py` 의 WorkspaceLock 을 직접, 그리고 실제 훅 경로(unittest 2건)로 판정한다.
`PLUGIFY_EVAL_REPO_ROOT` 로 다른 checkout(수정 전)을 가리켜 pre-fix 결과를 재현할 수 있다.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(os.environ.get("PLUGIFY_EVAL_REPO_ROOT") or Path(__file__).resolve().parents[3]).resolve()
SESSION_SCRIPT = ROOT / "scripts" / "workspace-session-start.py"
HOOK_TEST = ROOT / "scripts" / "test-workspace-session-start.py"
STALE = 600.0  # production 상수(STALE_LOCK_SECONDS)와 같아야 한다 — 모듈에 있으면 그 값을 쓴다


def load_session():
    spec = importlib.util.spec_from_file_location("plugify_session_eval", SESSION_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


SESSION = load_session()
STALE = float(getattr(SESSION, "STALE_LOCK_SECONDS", STALE))


def plant(tmp: Path, age_seconds: float) -> Path:
    lock = tmp / SESSION.LOCK_NAME
    lock.mkdir(mode=0o700)
    owner = lock / "owner.json"
    owner.write_text('{"token": "dead-leader"}\n', encoding="utf-8")
    stamp = time.time() - age_seconds
    os.utime(owner, (stamp, stamp))
    os.utime(lock, (stamp, stamp))
    return lock


def leftovers(tmp: Path) -> list[str]:
    return sorted(p.name for p in tmp.iterdir() if p.name.startswith(SESSION.LOCK_NAME))


def test_stale_lock_is_reclaimed(tmp: Path) -> None:
    lock = plant(tmp, STALE + 60)
    lk = SESSION.WorkspaceLock(tmp, 2.0)
    assert lk.acquire() is True, "acquire() must take over a lock older than STALE_LOCK_SECONDS"
    assert lk.reclaimed_stale is True, "reclaimed_stale must be reported"
    owner = json.loads((lock / "owner.json").read_text(encoding="utf-8"))
    assert owner == {"token": lk.token}, f"new leader must own the lock, got {owner}"
    lk.release()
    assert not lock.exists(), "release must remove the reclaimed lock"
    assert leftovers(tmp) == [], f"stale graveyard left behind: {leftovers(tmp)}"


def test_fresh_foreign_lock_is_respected(tmp: Path) -> None:
    lock = plant(tmp, 0)
    before = (lock / "owner.json").read_bytes()
    lk = SESSION.WorkspaceLock(tmp, 0.5)
    assert lk.acquire() is False, "a live lock must not be stolen"
    assert lk.wait_timed_out is True
    assert getattr(lk, "reclaimed_stale", False) is False
    assert lock.is_dir() and (lock / "owner.json").read_bytes() == before, "foreign lock must stay intact"


def test_reclaimed_lock_is_live_for_others(tmp: Path) -> None:
    # 이어받은 잠금은 새 리더의 살아있는 잠금이다 — 뒤따르는 프로세스가 다시 가로채면 안 된다.
    plant(tmp, STALE + 60)
    leader = SESSION.WorkspaceLock(tmp, 1.0)
    assert leader.acquire() is True
    follower = SESSION.WorkspaceLock(tmp, 0.5)
    assert follower.acquire() is False and follower.wait_timed_out is True
    assert getattr(follower, "reclaimed_stale", False) is False, "follower stole a freshly reclaimed lock"
    leader.release()
    assert leftovers(tmp) == []


def test_production_hook_path(tmp: Path) -> None:
    names = [
        "SessionSyncTest.test_stale_lock_is_reclaimed_and_sync_runs",
        "SessionSyncTest.test_fresh_foreign_lock_is_respected",
    ]
    result = subprocess.run(
        [sys.executable, str(HOOK_TEST), *names], text=True, encoding="utf-8", capture_output=True, check=False, timeout=180,
    )
    assert result.returncode == 0, f"production hook path failed:\n{result.stderr[-1500:]}"


TESTS = [
    test_stale_lock_is_reclaimed,
    test_fresh_foreign_lock_is_respected,
    test_reclaimed_lock_is_live_for_others,
    test_production_hook_path,
]


def main() -> int:
    passed = 0
    for fn in TESTS:
        label = "".join(p.capitalize() for p in fn.__name__.removeprefix("test_").split("_"))
        with tempfile.TemporaryDirectory(prefix="eval-stale-lock-") as tmp:
            try:
                fn(Path(tmp))
            except Exception as exc:  # pre-fix 코드는 속성 부재(AttributeError)로도 실패한다 — 그것도 판정이다
                print(f"not ok - test{label}: {type(exc).__name__}: {exc}")
                continue
        print(f"ok - test{label}")
        passed += 1
    total = len(TESTS)
    if passed == total:
        print(f"{total}/{total} stale workspace lock checks PASS")
        return 0
    print(f"{passed}/{total} stale workspace lock checks passed")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

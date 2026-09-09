"""참조 구현을 별도의 데이터 디렉터리에서 검사한다."""
from pathlib import Path
import subprocess
import tempfile

cli = str(Path(__file__).with_name("linkbox"))
with tempfile.TemporaryDirectory() as folder:
    def run(*args):
        return subprocess.run([cli, *args], cwd=folder, capture_output=True, text=True, timeout=60)
    assert run("add", "https://example.com/a", "--title", "Alpha Doc", "--tag", "dev").returncode == 0
    assert "Alpha Doc" in run("list", "--tag", "dev").stdout
    assert "Alpha Doc" in run("search", "Alpha").stdout
    assert run("remove", "https://example.com/a").returncode == 0
    assert "Alpha Doc" not in run("list").stdout
    missing = run("remove", "https://example.com/zzz")
    assert missing.returncode == 1 and (missing.stdout + missing.stderr).strip()
print("참조 테스트 6건 통과")

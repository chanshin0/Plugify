#!/usr/bin/env bash
set -euo pipefail
TOOLS="$(cd "$(dirname "$0")" && pwd)"
TEMP="$(mktemp -d "${TMPDIR:-/tmp}/p3test.XXXXXX")"
trap 'rm -rf "$TEMP"' EXIT
export PYTHONDONTWRITEBYTECODE=1
export GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null
export GIT_AUTHOR_NAME=fixture GIT_AUTHOR_EMAIL=fixture@example.invalid
export GIT_COMMITTER_NAME=fixture GIT_COMMITTER_EMAIL=fixture@example.invalid
for arm in A B C; do
  mkdir -p "$TEMP/$arm/.planning" "$TEMP/$arm/.codex" "$TEMP/$arm/node_modules"
  printf 'Plugify spec-building\n' > "$TEMP/$arm/.planning/STATE.md"
  printf 'Claude Codex\n' > "$TEMP/$arm/AGENTS.md"
  printf 'OpenAI\n' > "$TEMP/$arm/.codex/settings.json"
  printf 'Anthropic\n' > "$TEMP/$arm/trace.log"
  printf '// built by Claude Code with spec-building\n// Codex Anthropic OpenAI Plugify live-verify implementer reviewer perf-review service-planning tech-deciding Sonnet Opus Fable gpt-5\n// ExtraMarker\nprint("동작")\nCo-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>\nClaude-Session: 123\n' > "$TEMP/$arm/Claude-helper.py"
  printf '*.py\n' > "$TEMP/$arm/.gitignore"
  git -C "$TEMP/$arm" init -q --template= --initial-branch=main
  git -C "$TEMP/$arm" add --force --all
  git -C "$TEMP/$arm" -c core.hooksPath=/dev/null -c commit.gpgsign=false commit -q -m '구현' -m 'Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>'
done
printf 'ExtraMarker\n' > "$TEMP/extra.txt"
python3 "$TOOLS/anonymize.py" --task demo --in "A=$TEMP/A" --in "B=$TEMP/B" --in "C=$TEMP/C" --out "$TEMP/out" --seed 41 --extra-terms "$TEMP/extra.txt"
if grep -riI -E 'Claude|Codex|Anthropic|OpenAI|Plugify|spec-building|live-verify|implementer|reviewer|perf-review|service-planning|tech-deciding|Sonnet|Opus|Fable|gpt-|ExtraMarker' "$TEMP/out"; then
  printf '실패: 출력에 식별 용어가 남았습니다.\n' >&2
  exit 1
fi
python3 - "$TEMP/out/demo" <<'PY'
import json, os, pathlib, subprocess, sys
root=pathlib.Path(sys.argv[1])
assert (root/'SEALED-mapping.json').stat().st_mode & 0o777 == 0o600
pairs=json.loads((root/'pairs.json').read_text())
assert len(pairs)==3
assert len({p['pair_id'] for p in pairs})==3
assert {frozenset((p['left'],p['right'])) for p in pairs}=={frozenset(s) for s in [('X','Y'),('X','Z'),('Y','Z')]}
counts=json.loads((root/'manifest.json').read_text())
for letter in 'XYZ':
    repo=root/letter
    assert not (repo/'.planning').exists()
    assert not (repo/'AGENTS.md').exists()
    assert not (repo/'.codex').exists()
    assert not list(repo.rglob('*.log'))
    def git(*args): return subprocess.check_output(['git','-C',str(repo),*args],text=True).strip()
    assert git('rev-list','--count','HEAD')=='1'
    assert git('log','-1','--format=%s|%an|%ae|%cn|%ce|%aI|%cI').replace('Z','+00:00')=='snapshot|anon|anon@example.invalid|anon|anon@example.invalid|2000-01-01T00:00:00+00:00|2000-01-01T00:00:00+00:00', git('log','-1','--format=%s|%an|%ae|%cn|%ce|%aI|%cI')
    assert git('status','--porcelain')==''
    assert counts[letter]==2
    assert '[TOOL]-helper.py' in git('ls-files')
    assert 'Co-Authored-By:' not in (repo/'[TOOL]-helper.py').read_text()
print('통과: 식별 용어 0건 · 제외 경로 · 커밋 1개 · 고정 신원/시각 · 봉인 0600 · 쌍 3개')
PY
python3 "$TOOLS/bundle.py" "$TEMP/out/demo/X"
python3 - "$TEMP/out/demo/X.bundle.json" <<'PY'
import json,sys
b=json.load(open(sys.argv[1]))
assert b['letter']=='X' and len(b['files'])>=1
assert all('.git' not in f['path'].split('/') for f in b['files'])
print('통과: 번들 JSON · 파일 1개 이상 · Git 메타데이터 제외')
PY
# 바이너리 및 크기 경계, 심볼릭 링크, 경로 충돌, 출력 재사용을 별도로 확인한다.
python3 - "$TOOLS" "$TEMP" <<'PY'
import json, pathlib, subprocess, sys
sys.path.insert(0,sys.argv[1])
import anonymize
root=pathlib.Path(sys.argv[2]); tools=pathlib.Path(sys.argv[1])
b=root/'Q'; b.mkdir()
(b/'binary').write_bytes(b'\xff\x00')
(b/'limit').write_bytes(b'a'*(200*1024))
(b/'large').write_bytes(b'a'*(200*1024+1))
subprocess.run([sys.executable,str(tools/'bundle.py'),str(b)],check=True,stdout=subprocess.PIPE)
assert [x['path'] for x in json.loads((root/'Q.bundle.json').read_text())['files']]==['limit']
pattern=anonymize.matcher(anonymize.TERMS)
assert anonymize.clean_text('cLaUdE CodexCLI gpt-5\nClaude-Session: x\n',pattern)=='[TOOL] [TOOL]CLI [TOOL]5\n'
source=root/'collision';source.mkdir()
(source/'Claude.txt').write_text('a');(source/'Codex.txt').write_text('b')
try: anonymize.copy_snapshot(source,root/'collision-out',pattern)
except ValueError: pass
else: raise AssertionError('파일명 충돌을 허용했습니다.')
source=root/'link';source.mkdir();(source/'escape').symlink_to(root/'A')
try: anonymize.copy_snapshot(source,root/'link-out',pattern)
except ValueError: pass
else: raise AssertionError('심볼릭 링크를 허용했습니다.')
result=subprocess.run([sys.executable,str(tools/'anonymize.py'),'--task','demo','--in',f'A={root}/A','--in',f'B={root}/B','--out',str(root/'out')],capture_output=True)
assert result.returncode!=0
(root/'out/demo/X/leak.txt').write_text('Claude\n')
assert anonymize.inspect_snapshot(root/'out/demo/X',pattern)==['leak.txt:1: 식별 용어 잔존']
print('통과: 200KB 경계 · 바이너리 제외 · 충돌/링크/덮어쓰기 거부 · 잔존 용어 검출')
PY
python3 - "$TOOLS/review-console.html" "$TEMP/console.js" <<'PY'
import pathlib,re,sys
html=pathlib.Path(sys.argv[1]).read_text()
scripts=re.findall(r'<script>([\s\S]*?)</script>',html)
assert len(scripts)==1
assert not re.search(r'<(?:script|link|img)[^>]+(?:src|href)\s*=',html,re.I)
pathlib.Path(sys.argv[2]).write_text(scripts[0])
PY
node -e 'new Function(require("fs").readFileSync(process.argv[1],"utf8")); console.log("통과: 리뷰 콘솔 JavaScript 문법 · 외부 리소스 없음")' "$TEMP/console.js"
node "$TOOLS/console-test.js" "$TEMP/console.js"
printf '전체 자체검사 통과\n'

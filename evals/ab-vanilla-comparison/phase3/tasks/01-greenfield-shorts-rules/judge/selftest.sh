#!/bin/bash
# git 변경은 이 스크립트가 새로 만드는 임시 저장소에만 한정한다.
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/judge01.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
export PYTHONDONTWRITEBYTECODE=1
python3 - "$HERE" "$TMP" <<'PY'
from pathlib import Path
import shutil
import sys
here, temporary = map(Path, sys.argv[1:])
reference = temporary / 'reference'
shutil.copytree(here / 'reference', reference)
(reference / 'data').mkdir()
shutil.copyfile(here.parent / 'data/videos.json', reference / 'data/videos.json')
PY
git -C "$TMP/reference" init -q
git -C "$TMP/reference" add .
git -C "$TMP/reference" -c user.name=판정테스트 -c user.email=judge@example.invalid -c core.hooksPath=/dev/null commit -qm '참조 구현 검증용 초기 상태'
"$HERE/run.sh" "$TMP/reference" > "$TMP/pass.log"
python3 - "$TMP/pass.log" <<'PY'
import re
import sys
text = open(sys.argv[1]).read()
match = re.search(r'SCORE (\d+)/(\d+)\s*$', text)
assert match and int(match[1]) > 0 and match[1] == match[2], text
print('ok 정상 참조 ' + match[0].strip())
PY
python3 - "$TMP/reference/main.py" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
text = path.read_text()
assert text.count('index = math.ceil(') == 1
path.write_text(text.replace('index = math.ceil(', 'index = math.floor('))
PY
git -C "$TMP/reference" add main.py
git -C "$TMP/reference" -c user.name=판정테스트 -c user.email=judge@example.invalid -c core.hooksPath=/dev/null commit -qm '백분위 내림 결함 주입'
if "$HERE/run.sh" "$TMP/reference" > "$TMP/fail.log"; then
    cat "$TMP/fail.log"
    echo 'FAIL 변형본을 잡지 못함'
    exit 1
fi
python3 - "$TMP/fail.log" <<'PY'
import re
import sys
text = open(sys.argv[1]).read()
failures = [line for line in text.splitlines() if line.startswith('FAIL 리포트.')]
assert failures, text
print('ok 백분위 변형 검출: ' + ' / '.join(failures))
print(text.splitlines()[-1])
PY
# 임시 참조에만 후속 규칙을 추가하여 후속 하네스 자체도 검증한다.
python3 - "$TMP/reference/main.py" <<'PYCODE'
from pathlib import Path
import sys
path = Path(sys.argv[1])
text = path.read_text().replace('index = math.floor(', 'index = math.ceil(')
text = text.replace('    return report, rules', """    ratios = [Decimal(number(row['comment_count'])) / number(row['view_count'])
              for row in rows if number(row['view_count']) > 0]
    rules['comment_ratio_min'] = half(rank(ratios, 10), 4)
    return report, rules""")
text = text.replace("    print('\\n'.join(violations)", """    if 'comment_ratio_min' in rules and 'view_count' in row and 'comment_count' in row:
        ratio = Decimal(number(row['comment_count'])) / number(row['view_count'])
        if ratio < Decimal(str(rules['comment_ratio_min'])):
            violations.append('VIOLATION comment_ratio_min: 기준 미달')
    print('\\n'.join(violations)""")
assert '기준 미달' in text
path.write_text(text)
PYCODE
git -C "$TMP/reference" add main.py
git -C "$TMP/reference" -c user.name=판정테스트 -c user.email=judge@example.invalid -c core.hooksPath=/dev/null commit -qm '후속 댓글 비율 참조 검증'
"$HERE/followup.sh" "$TMP/reference" > "$TMP/followup.log" || { cat "$TMP/followup.log"; exit 1; }
python3 - "$TMP/followup.log" <<'PYCODE'
import re
import sys
text = open(sys.argv[1]).read()
match = re.search(r'SCORE (\d+)/(\d+)\s*$', text)
assert match and match[1] == match[2], text
print('ok 후속 참조 및 기존 회귀 ' + match[0].strip())
print('SELFTEST 통과')
PYCODE

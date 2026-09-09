#!/bin/bash
set -eu
cd "$(dirname "$0")"
PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY'
from main import rank, half, analyze, yaml_read, yaml_write, check
from decimal import Decimal
from pathlib import Path
import tempfile
assert rank([1, 2, 3], 50) == 2
assert rank(list(range(1, 12)), 90) == 10
assert half(Decimal('2.65'), 1) == 2.7
assert len('가😀Ａ') == 3
report, rules = analyze('data/videos.json')
assert report['count'] > 0
with tempfile.TemporaryDirectory() as temporary:
    path = Path(temporary) / 'rules.yaml'
    path.write_text(yaml_write(rules))
    assert yaml_read(path) == rules
print('참조 테스트 6건 통과')
PY

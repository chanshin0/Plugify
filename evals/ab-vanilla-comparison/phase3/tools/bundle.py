#!/usr/bin/env python3
"""익명 스냅샷을 오프라인 리뷰용 JSON으로 묶는다."""
import argparse
import json
from pathlib import Path
import re
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot', type=Path, help='익명 글자 이름의 스냅샷 디렉터리')
    parser.add_argument('--out', type=Path, help='기본값: 스냅샷 옆의 <글자>.bundle.json')
    args = parser.parse_args()
    root = args.snapshot.resolve()
    if not root.is_dir() or not re.fullmatch('[A-Z]+', root.name):
        parser.error('익명 글자 이름의 디렉터리가 필요합니다.')
    output = (args.out or root.parent / (root.name + '.bundle.json')).resolve()
    if root == output or root in output.parents:
        parser.error('번들 출력은 스냅샷 밖에 두세요.')
    files, skipped = [], 0
    for path in sorted(root.rglob('*')):
        if '.git' in path.relative_to(root).parts:
            continue
        if path.is_symlink():
            parser.error('심볼릭 링크가 있는 스냅샷은 묶을 수 없습니다.')
        if not path.is_file():
            continue
        if path.stat().st_size > 200 * 1024:
            skipped += 1
            continue
        data = path.read_bytes()
        try:
            content = data.decode('utf-8')
            if '\x00' in content:
                raise UnicodeDecodeError('utf-8', data, 0, 1, '바이너리')
        except UnicodeDecodeError:
            skipped += 1
            continue
        files.append(dict(path=path.relative_to(root).as_posix(), content=content))
    output.write_text(json.dumps(dict(letter=root.name, files=files), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'번들 완료: {output} (파일 {len(files)}개, 제외 {skipped}개)')
    return 0


if __name__ == '__main__':
    sys.exit(main())

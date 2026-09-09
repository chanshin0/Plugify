#!/usr/bin/env python3
"""평가용 스냅샷을 익명화하고 별도 이력을 만든다."""
import argparse
import itertools
import json
import os
from pathlib import Path
import random
import re
import shutil
import subprocess
import sys
import tempfile

TERMS = ['Claude', 'Codex', 'Anthropic', 'OpenAI', 'Plugify', 'spec-building',
         'live-verify', 'implementer', 'reviewer', 'perf-review', 'service-planning',
         'tech-deciding', 'Sonnet', 'Opus', 'Fable', 'gpt-']
EXCLUDED = {'.git', 'node_modules', '.planning', '.codex', '.claude',
            'agents.md', 'claude.md', '.cursorrules', '.ds_store'}


def matcher(terms):
    # 파일명·붙여 쓴 제품명에서도 누출을 막도록 부분 문자열까지 보수적으로 지운다.
    return re.compile('|'.join(re.escape(t) for t in sorted(set(terms), key=len, reverse=True)), re.I)


def clean_text(value, pattern):
    lines = [line for line in value.splitlines(keepends=True)
             if not re.match(r'^\s*(?:Co-Authored-By|Claude-Session)\s*:', line, re.I)
             and 'noreply@anthropic.com' not in line.lower()]
    return pattern.sub('[TOOL]', ''.join(lines))


def letter(index):
    result = ''
    index += 24
    while index:
        index, rem = divmod(index - 1, 26)
        result = chr(65 + rem) + result
    return result


def excluded(name):
    return name.lower() in EXCLUDED or name.lower().endswith('.log')


def copy_snapshot(source, target, pattern):
    target.mkdir()
    count = 0
    for base, dirs, files in os.walk(source, followlinks=False):
        dirs[:] = sorted(d for d in dirs if not excluded(d))
        for name in dirs + sorted(files):
            if excluded(name):
                continue
            old = Path(base) / name
            if old.is_symlink():
                raise ValueError('심볼릭 링크는 허용하지 않습니다: ' + str(old.relative_to(source)))
            parts = [pattern.sub('[TOOL]', p) for p in old.relative_to(source).parts]
            dest = target.joinpath(*parts)
            if dest.exists():
                raise ValueError('익명화 후 경로 충돌: ' + '/'.join(parts))
            if old.is_dir():
                dest.mkdir()
                continue
            if not old.is_file():
                raise ValueError('일반 파일이 아닙니다: ' + str(old.relative_to(source)))
            data = old.read_bytes()
            try:
                data = clean_text(data.decode('utf-8'), pattern).encode('utf-8')
            except UnicodeDecodeError:
                pass
            dest.write_bytes(data)
            dest.chmod(0o755 if old.stat().st_mode & 0o111 else 0o644)
            count += 1
    return count


def inspect_snapshot(target, pattern):
    errors = []
    for path in sorted(target.rglob('*')):
        if '.git' in path.relative_to(target).parts:
            continue
        if pattern.search(str(path.relative_to(target))):
            errors.append(str(path.relative_to(target)) + ':0: 경로에 식별 용어 잔존')
        if path.is_file():
            try:
                value = path.read_bytes().decode('utf-8')
            except UnicodeDecodeError:
                continue
            for number, line in enumerate(value.splitlines(), 1):
                if pattern.search(line):
                    errors.append(f'{path.relative_to(target)}:{number}: 식별 용어 잔존')
    return errors


def new_history(target):
    # 사용자 전역 설정·훅·템플릿·서명·부모 레포 환경을 상속하지 않는다.
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
               GIT_AUTHOR_NAME='anon', GIT_AUTHOR_EMAIL='anon@example.invalid',
               GIT_COMMITTER_NAME='anon', GIT_COMMITTER_EMAIL='anon@example.invalid',
               GIT_AUTHOR_DATE='2000-01-01T00:00:00Z', GIT_COMMITTER_DATE='2000-01-01T00:00:00Z')
    def git(*args):
        subprocess.run(['git', '-c', 'core.hooksPath=' + os.devnull,
                        '-c', 'commit.gpgsign=false', *args], cwd=target,
                       env=env, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    git('init', '--quiet', '--template=', '--initial-branch=main')
    git('add', '--force', '--all')  # 복사본의 ignore 규칙에 관계없이 전체 스냅샷을 고정한다.
    git('commit', '--quiet', '--allow-empty', '-m', 'snapshot')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task', required=True)
    parser.add_argument('--in', dest='inputs', action='append', required=True, metavar='라벨=경로')
    parser.add_argument('--out', required=True)
    parser.add_argument('--seed', type=int)
    parser.add_argument('--extra-terms', type=Path)
    args = parser.parse_args()
    stage = None
    try:
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', args.task):
            raise ValueError('과제 ID는 영문·숫자로 시작하고 영문·숫자·밑줄·점·하이픈만 허용합니다.')
        sources = []
        for value in args.inputs:
            label, sep, path = value.partition('=')
            source = Path(path).expanduser().resolve()
            if not sep or not label.strip() or not source.is_dir():
                raise ValueError('입력 형식 또는 디렉터리를 확인하세요.')
            sources.append((label, source))
        if len({x[0] for x in sources}) != len(sources):
            raise ValueError('입력 라벨은 서로 달라야 합니다.')
        terms = TERMS.copy()
        if args.extra_terms:
            terms.extend(t.strip() for t in args.extra_terms.read_text(encoding='utf-8').splitlines() if t.strip())
        pattern = matcher(terms)
        if pattern.search('[TOOL]'):
            raise ValueError('추가 용어는 치환 표식 [TOOL]과 겹칠 수 없습니다.')
        root = Path(args.out).expanduser().resolve()
        final = root / args.task
        if final.exists():
            raise ValueError('출력 과제 디렉터리가 이미 존재합니다. 새 경로를 사용하세요.')
        if any(root == src or src in root.parents for _, src in sources):
            raise ValueError('출력은 입력 스냅샷 밖에 두세요.')
        root.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix='.anonymous-', dir=root))
        rng = random.Random(args.seed if args.seed is not None else int.from_bytes(os.urandom(32), 'big'))
        letters = [letter(i) for i in range(len(sources))]
        assigned = letters.copy()
        rng.shuffle(assigned)
        mapping, counts = {}, {}
        # 생성 순서와 파일 시각도 입력 순서를 드러내지 않도록 통일한다.
        assigned_sources = dict(zip(assigned, sources))
        for key in letters:
            label, source = assigned_sources[key]
            mapping[key] = label
            counts[key] = copy_snapshot(source, stage / key, pattern)
            errors = inspect_snapshot(stage / key, pattern)
            if errors:
                raise ValueError('\n'.join(key + '/' + e for e in errors))
            new_history(stage / key)
            for p in (stage / key).rglob('*'):
                os.utime(p, (946684800, 946684800))
            os.utime(stage / key, (946684800, 946684800))
        pairs = []
        for left, right in itertools.combinations(letters, 2):
            order = [left, right]
            rng.shuffle(order)
            pairs.append(dict(pair_id=left + '-' + right, left=order[0], right=order[1]))
        rng.shuffle(pairs)
        for name, content in [('manifest.json', counts), ('pairs.json', pairs)]:
            (stage / name).write_text(json.dumps(content, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        sealed = stage / 'SEALED-mapping.json'
        fd = os.open(sealed, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(mapping, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
        stage.rename(final)
        stage = None
        final.chmod(0o755)
        print('익명화 완료: ' + str(final))
        print('판정이 모두 끝날 때까지 SEALED-mapping.json 봉인 파일을 열지 마세요.')
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print('실패: ' + str(exc), file=sys.stderr)
        return 1
    finally:
        if stage is not None:
            shutil.rmtree(stage)
    return 0


if __name__ == '__main__':
    sys.exit(main())

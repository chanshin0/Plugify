#!/usr/bin/env python3
"""오프라인 블랙박스 판정. 모든 자식 명령은 120초 제한."""
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
from datetime import date, timedelta
from expected import calculate, comment_threshold

HERE = Path(__file__).resolve().parent
HEADERS = ['# 채널 리포트', '## 개요', '## 제목 길이', '## 제목 단어 Top 20', '## 길이(초)', '## 업로드 패턴', '## 조회수']


class Judge:
    def __init__(self, source, temporary):
        self.root = Path(temporary) / 'snapshot'
        # 심볼릭 링크도 역참조하여 원본 파일에 쓰는 일을 방지한다.
        shutil.copytree(Path(source).resolve(), self.root, symlinks=False)
        self.out = Path(temporary) / '결과'
        self.out.mkdir()
        self.ok = self.fail = 0
        self.expected = calculate(json.loads((HERE.parent / 'data/videos.json').read_text()))

    def mark(self, name, value):
        status = 'n/a' if value is None else 'ok' if value else 'FAIL'
        print(f'{status} {name}', flush=True)
        self.ok += value is True
        self.fail += value is False

    def command(self, args):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', GIT_TERMINAL_PROMPT='0')
        try:
            # 파일로 받아 무제한 stdout 때문에 판정기의 메모리가 고갈되지 않게 한다.
            with (self.out / 'stdout.log').open('w+') as stdout, (self.out / 'stderr.log').open('w+') as stderr:
                proc = subprocess.Popen(args, cwd=self.root, env=env, stdout=stdout, stderr=stderr, start_new_session=True)
                try:
                    code = proc.wait(timeout=120)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait()
                    code = 124
                stdout.seek(0)
                stderr.seek(0)
                output, errors = stdout.read(1000000), stderr.read(4000)
            if code not in (0, 1, 2):
                print(f'진단: {args[0]} 종료={code} {errors[:300]!r}', flush=True)
            return code, output
        except OSError as error:
            print(f'진단: 실행 불가 {error}', flush=True)
            return 127, ''

    def read(self, name):
        try:
            return json.loads((self.out / name).read_text())
        except (OSError, ValueError):
            return None

    def compare(self, expected, actual, path):
        if isinstance(expected, dict):
            for key, value in expected.items():
                self.compare(value, actual.get(key) if isinstance(actual, dict) else None, f'{path}.{key}')
        elif isinstance(expected, list):
            self.mark(path + '.길이', isinstance(actual, list) and len(actual) == len(expected))
            for index, value in enumerate(expected):
                self.compare(value, actual[index] if isinstance(actual, list) and index < len(actual) else None, f'{path}[{index}]')
        else:
            numeric = isinstance(actual, (int, float)) and not isinstance(actual, bool) and math.isfinite(actual)
            if isinstance(expected, float):
                valid = numeric and abs(actual - expected) < 0.051
            elif isinstance(expected, int):
                valid = numeric and actual == expected
            else:
                valid = type(actual) is type(expected) and actual == expected
            self.mark(path, valid)

    def setup(self):
        if (self.root / 'setup.sh').exists():
            self.mark('설치', self.command(['./setup.sh'])[0] == 0)
        else:
            self.mark('설치 스크립트 없음', None)

    def derive(self, kind, name):
        code, _ = self.command(['./shorts-rules', 'derive', 'data/videos.json', '--out', str(self.out / name), '--format', kind])
        self.mark(f'규칙 {kind} 실행', code == 0)
        return self.read(name) if kind == 'json' else None

    def normal(self):
        rules = self.expected['rules']
        day = rules['upload_weekdays_allowed'][0]
        return dict(title='가' * rules['title_chars']['min'], duration=str(rules['duration_sec']['min']),
                    upload_date=(date(2026, 1, 5) + timedelta(days=day - 1)).strftime('%Y%m%d'))

    def check(self, label, meta, exit_code, token=None):
        path = self.out / 'meta.json'
        path.write_text(meta if isinstance(meta, str) else json.dumps(meta, ensure_ascii=False))
        code, output = self.command(['./shorts-rules', 'check', str(self.out / 'rules.yaml'), str(path)])
        match = token is None or (output.strip() == 'OK' if token == 'OK' else re.search(r'^' + re.escape(token) + r'(?=:|\s|$)', output, re.M) is not None)
        self.mark(label, code == exit_code and match)

    def base(self):
        code, _ = self.command(['./shorts-rules', 'report', 'data/videos.json', '--out', str(self.out / 'r.md'), '--json', str(self.out / 'r.json')])
        self.mark('리포트 실행', code == 0)
        self.compare(self.expected['report'], self.read('r.json'), '리포트')
        try:
            markdown = (self.out / 'r.md').read_text()
        except OSError:
            markdown = ''
        for header in HEADERS:
            self.mark('헤더 ' + header, header in markdown.splitlines())
        self.compare(self.expected['rules'], self.derive('json', 'rules.json'), '규칙')
        self.derive('yaml', 'rules.yaml')
        try:
            yaml = (self.out / 'rules.yaml').read_text()
        except OSError:
            yaml = ''
        self.mark('YAML version 줄', bool(re.search(r'^version: 1\s*$', yaml, re.M)))
        rules, normal = self.expected['rules'], self.normal()
        self.check('정상 메타', normal, 0, 'OK')
        self.check('제목 상한 초과', dict(normal, title='가' * (rules['title_chars']['max'] + 5)), 1, 'VIOLATION title_chars')
        self.check('제목 하한 미달', dict(normal, title='가' * max(1, rules['title_chars']['min'] - 1)), 1)
        self.check('길이 상한 초과', dict(normal, duration=str(rules['duration_sec']['max'] + 10)), 1, 'VIOLATION duration_sec')
        forbidden = sorted(set(range(1, 8)) - set(rules['upload_weekdays_allowed']))
        if forbidden:
            self.check('허용 밖 요일', dict(normal, upload_date=(date(2026, 1, 5) + timedelta(days=forbidden[0] - 1)).strftime('%Y%m%d')), 1, 'VIOLATION upload_weekdays_allowed')
        else:
            self.mark('허용 밖 요일 없음', None)
        self.check('JSON 아님', '{깨짐', 2)
        missing = dict(normal)
        del missing['title']
        self.check('제목 누락', missing, 2)
        self.check('길이 형식 오류', dict(normal, duration='abc'), 2)
        self.mark('자동 테스트', self.command(['./test.sh'])[0] == 0)
        code, status = self.command(['git', 'status', '--porcelain', '--untracked-files=all'])
        self.mark('작업트리 클린', code == 0 and not status.strip())
        code, count = self.command(['git', 'rev-list', '--count', 'HEAD'])
        self.mark('커밋 존재', code == 0 and count.strip().isdigit() and int(count.strip()) >= 1)

    def followup(self):
        actual = self.derive('json', 'followup.json')
        threshold = comment_threshold(json.loads((HERE.parent / 'data/videos.json').read_text()))
        value = actual.get('comment_ratio_min') if isinstance(actual, dict) else None
        self.mark('댓글 비율 p10 반올림', isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and abs(value - threshold) < 1e-9)
        self.derive('yaml', 'rules.yaml')
        # 실측 p10은 0.0000: 유효한 비음수 카운트로 미달을 만들 수 없다.
        # 도출 정확성은 위에서 검증하고 검사 동작은 양수 기준으로 독립 검증한다.
        if threshold == 0:
            path = self.out / 'rules.yaml'
            try:
                text = path.read_text()
                text, changed = re.subn(r'^comment_ratio_min:.*$', 'comment_ratio_min: 0.0001', text, flags=re.M)
                if changed == 0:
                    # JSON도 유효한 YAML이므로 JSON 형태 출력도 지원한다.
                    document = json.loads(text)
                    document['comment_ratio_min'] = 0.0001
                    text = json.dumps(document, ensure_ascii=False)
                path.write_text(text)
            except (OSError, ValueError, TypeError):
                self.mark('댓글 검사 양수 기준 준비', False)
        self.check('댓글 비율 미달', dict(self.normal(), view_count='100000', comment_count='0'), 1, 'VIOLATION comment_ratio_min')
        self.check('두 카운트 없음: 건너뜀', self.normal(), 0, 'OK')
        print('기존 판정 회귀 시작', flush=True)
        self.base()


def main():
    judge = None
    try:
        judge = Judge(sys.argv[2], sys.argv[3])
        judge.setup()
        judge.followup() if sys.argv[1] == 'followup' else judge.base()
    except Exception as error:
        if judge is None:
            print(f'FAIL 판정 준비: {error}\nSCORE 0/1')
            return 1
        judge.mark(f'판정 예외: {error}', False)
    print(f'SCORE {judge.ok}/{judge.ok + judge.fail}')
    return int(judge.fail > 0)


if __name__ == '__main__':
    sys.exit(main())

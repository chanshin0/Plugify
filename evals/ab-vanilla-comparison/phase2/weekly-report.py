#!/usr/bin/env python3
"""지점 레포의 ISO 주별 공정/직접 작업 관찰 집계(표준 라이브러리 전용)."""
import argparse
import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from collections import defaultdict

UTC = dt.timezone.utc
TOKEN_KEYS = ('input_tokens', 'output_tokens', 'cache_read_input_tokens',
              'cache_creation_input_tokens')
TRAILER = 'Co-Authored-By: Claude <noreply@anthropic.com>'
FOLLOWUP = re.compile(r'revert|되돌|핫픽스|hotfix|재수정|다시 수정|fix:|버그', re.I)
REVERT = re.compile(r'^revert\b|되돌', re.I)
HASH = re.compile(r'(?<![0-9a-f])[0-9a-f]{40}(?![0-9a-f])')
PRICE_PATH = Path('/Users/admin/Projects/Plugify/skills/improve-token-efficiency/scripts/analyze_sessions.py')


def warn(message):
    print('경고: ' + message, file=sys.stderr)


def timestamp(value):
    try:
        value = dt.datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    except (ValueError, TypeError):
        return None


def week(value):
    year, number, _ = value.isocalendar()
    return '%04d-W%02d' % (year, number)


def bucket(count):
    return '1' if count == 1 else '2-3' if count <= 3 and count > 0 else '4+' if count >= 4 else '0'


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args])


def commits_from_git(repo, since):
    # NUL 구분으로 탭·개행 파일명 및 바이너리 numstat도 보존한다.
    raw = git(repo, 'log', '--since=' + since.isoformat(), '--format=%x00P2COMMIT%x00%H%x00%cI%x00%B%x00',
              '--numstat', '-z', '--no-renames', '--root', '--diff-merges=first-parent')
    commits = []
    for block in raw.split(b'\x00P2COMMIT\x00')[1:]:
        sha, date, message, stats = block.split(b'\x00', 3)
        when = timestamp(date.decode())
        if when is None or when < since:
            continue
        files = set()
        for record in stats.split(b'\x00'):
            parts = record.lstrip(b'\n').split(b'\t', 2)
            if len(parts) == 3:
                files.add(os.fsdecode(parts[2]))
        body = message.decode('utf-8', 'replace').rstrip('\n')
        commits.append({'hash': sha.decode(), 'date': when.isoformat(), 'week': week(when),
                        'subject': body.split('\n', 1)[0], 'message': body,
                        'files': sorted(files), 'bucket': bucket(len(files)), 'followup': False})
    commits.sort(key=lambda c: (c['date'], c['hash']))
    # 같은 시각은 후속으로 단정하지 않는다. 원래 커밋은 최대 한 번 계수한다.
    for i, original in enumerate(commits):
        for later in commits[i + 1:]:
            delta = (timestamp(later['date']) - timestamp(original['date'])).total_seconds()
            if delta > 48 * 3600:
                break
            if delta > 0 and FOLLOWUP.search(later['subject']) and set(original['files']).intersection(later['files']):
                original['followup'] = True
                break
    return commits


def prices():
    try:
        spec = importlib.util.spec_from_file_location('phase2_session_prices', PRICE_PATH)
        module = importlib.util.module_from_spec(spec)
        # 외부 모듈에 __pycache__를 만들지 않는다.
        old = sys.dont_write_bytecode
        sys.dont_write_bytecode = True
        try:
            spec.loader.exec_module(module)
        finally:
            sys.dont_write_bytecode = old
        return module.PRICING
    except Exception as exc:
        warn('가격표를 읽지 못해 토큰만 표시: ' + str(exc))
        return {}


def texts(content):
    if isinstance(content, str):
        yield content
    elif isinstance(content, list):
        for item in content:
            if isinstance(item, dict):
                if item.get('type') == 'text':
                    yield item.get('text', '')
                elif item.get('type') == 'tool_result':
                    yield from texts(item.get('content', []))


def results(text):
    decoder = json.JSONDecoder()
    for marker in re.finditer(r'<result>', text):
        start = text.find('{', marker.end())
        if start < 0:
            continue
        try:
            obj, _ = decoder.raw_decode(text[start:])
        except ValueError:
            continue
        if isinstance(obj, dict) and isinstance(obj.get('runSummary'), dict) and 'terminalState' in obj:
            yield obj


def mine(directory, price_table):
    sessions, runs, authority = [], [], set()
    unknown = set()
    if not directory.is_dir():
        warn('세션 기록 디렉터리가 없음: ' + str(directory))
    for path in sorted(directory.glob('*.jsonl')):
        first = None
        calls, completed = {}, set()
        usage = defaultdict(lambda: dict.fromkeys(TOKEN_KEYS + ('cache_create_5m', 'cache_create_1h'), 0))
        bad = 0
        with path.open(encoding='utf-8', errors='replace') as handle:
            for line in handle:
                try:
                    rec = json.loads(line)
                except ValueError:
                    bad += 1
                    continue
                if not isinstance(rec, dict):
                    continue
                when = timestamp(rec.get('timestamp'))
                if first is None and when is not None:
                    first = when
                msg = rec.get('message', {})
                if not isinstance(msg, dict):
                    continue
                content = msg.get('content', [])
                if rec.get('type') == 'assistant':
                    tokens = msg.get('usage') or {}
                    model = msg.get('model') or '미상'
                    if isinstance(tokens, dict) and tokens:
                        totals = usage[model]
                        for key in TOKEN_KEYS:
                            totals[key] += tokens.get(key, 0) or 0
                        detail = tokens.get('cache_creation') or {}
                        one = detail.get('ephemeral_1h_input_tokens', 0) or 0
                        five = detail.get('ephemeral_5m_input_tokens', 0) or 0
                        if not one and not five:
                            five = tokens.get('cache_creation_input_tokens', 0) or 0
                        totals['cache_create_5m'] += five
                        totals['cache_create_1h'] += one
                    for item in content if isinstance(content, list) else []:
                        if not isinstance(item, dict) or item.get('type') != 'tool_use' or item.get('name') != 'Workflow':
                            continue
                        inputs = item.get('input') or {}
                        script = inputs.get('scriptPath', '')
                        if any(p in script for p in ('spec-building/workflow.mjs', 'spec-building/graph-workflow.mjs')):
                            ident = item.get('id') or '식별자없음-%d' % len(calls)
                            calls.setdefault(ident, {'when': when, 'result': None})
                if rec.get('type') != 'user':
                    continue
                blocks = content if isinstance(content, list) else [content]
                for item in blocks:
                    linked = item.get('tool_use_id') if isinstance(item, dict) else None
                    for text in texts([item] if isinstance(item, dict) else item):
                        for obj in results(text):
                            candidates = [key for key in calls if key not in completed]
                            ident = linked if linked in calls else (candidates[0] if linked is None and len(candidates) == 1 else None)
                            if ident is None or ident in completed:
                                continue
                            calls[ident]['result'] = obj
                            completed.add(ident)
        if bad:
            warn('%s: 손상 JSONL %d줄 제외' % (path.name, bad))
        for ident, call in calls.items():
            obj = call['result'] or {}
            summary = obj.get('runSummary') or {}
            started = obj.get('startedAt') or summary.get('startedAt')
            when = timestamp(started) or call['when'] or first
            commit = obj.get('commit') or {}
            evidence = []
            if isinstance(commit, dict):
                evidence.extend([commit.get('afterHead', ''), commit.get('headLog', '')])
            evidence.append(obj.get('headLog', ''))
            hashes = sorted({sha for value in evidence if isinstance(value, str) for sha in HASH.findall(value)})
            authority.update(hashes)
            runs.append({'session': path.name, 'tool_use_id': ident,
                         'date': when.isoformat() if when else None, 'week': week(when) if when else None,
                         'startedAt': started, 'terminalState': obj.get('terminalState', '결과없음'),
                         'attempts': obj.get('attempts', summary.get('attempts')),
                         'humanReintervention': summary.get('humanReintervention'),
                         'escalation': obj.get('escalation'), 'commitHashes': hashes})
        cost, available = 0.0, bool(price_table)
        for model, tokens in usage.items():
            price = price_table.get(model)
            if price is None:
                available = False
                if model not in unknown:
                    warn('가격 없는 모델은 토큰만 표시: ' + model)
                    unknown.add(model)
                continue
            cost += sum(tokens[key] * price[rate] for key, rate in (
                ('input_tokens', 'in'), ('output_tokens', 'out'), ('cache_read_input_tokens', 'cr'),
                ('cache_create_5m', 'cw5'), ('cache_create_1h', 'cw1h'))) / 1e6
        sessions.append({'session': path.name, 'date': first.isoformat() if first else None,
                         'week': week(first) if first else None, 'tag': 'pipeline' if calls else 'direct',
                         'tokens_by_model': dict(usage), 'cost_usd': cost if available else None})
    return sessions, runs, authority


def manual_tags(repo):
    path = repo / '.planning/task-tags.tsv'
    tags = {}
    if not path.exists():
        return tags
    for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        if not line.strip() or line.startswith('#'):
            continue
        parts = line.split('\t')
        if len(parts) != 2 or not re.fullmatch('[0-9a-f]{4,40}', parts[0]) or parts[1] not in ('pipeline', 'direct'):
            raise ValueError('수동 태그 형식 오류: %s:%d' % (path, number))
        try:
            sha = git(repo, 'rev-parse', '--verify', parts[0] + '^{commit}').decode().strip()
        except subprocess.CalledProcessError:
            raise ValueError('수동 태그 해시가 없거나 모호함: ' + parts[0])
        if sha in tags and tags[sha] != parts[1]:
            raise ValueError('수동 태그 충돌: ' + sha)
        tags[sha] = parts[1]
    return tags


def aggregate(commits, sessions, runs, since):
    rows = {}
    strata = {}
    def row(w, tag):
        key = (w, tag)
        if key not in rows:
            rows[key] = dict(week=w, tag=tag, commits=0, buckets={'1': 0, '2-3': 0, '4+': 0, '0': 0},
                             followup=0, reverts=0, runs=0, verified=0, escalated_pending=0,
                             reintervention_required=0, cost_usd=0.0, tokens_by_model={})
        return rows[key]
    for c in commits:
        r = row(c['week'], c['tag'])
        r['commits'] += 1
        r['buckets'][c['bucket']] += 1
        r['followup'] += int(c['followup'])
        r['reverts'] += int(bool(REVERT.search(c['subject'])))
        key = (c['tag'], c['bucket'])
        s = strata.setdefault(key, dict(tag=c['tag'], bucket=c['bucket'], commits=0, followup=0))
        s['commits'] += 1
        s['followup'] += int(c['followup'])
    for run in runs:
        if not run['date'] or timestamp(run['date']) < since:
            continue
        r = row(run['week'], 'pipeline')
        r['runs'] += 1
        r['verified'] += int(run['terminalState'] == 'verified')
        r['escalated_pending'] += int(run['terminalState'].startswith(('escalated', 'pending')) or run['escalation'] is not None)
        r['reintervention_required'] += int(run['humanReintervention'] == 'required')
    for session in sessions:
        if not session['date'] or timestamp(session['date']) < since:
            continue
        r = row(session['week'], session['tag'])
        if session['cost_usd'] is None:
            r['cost_usd'] = None
        elif r['cost_usd'] is not None:
            r['cost_usd'] += session['cost_usd']
        for model, usage in session['tokens_by_model'].items():
            totals = r['tokens_by_model'].setdefault(model, dict.fromkeys(usage, 0))
            for key, value in usage.items():
                totals[key] += value
    for s in strata.values():
        s['followup_rate'] = s['followup'] / s['commits']
    return [rows[k] for k in sorted(rows)], [strata[k] for k in sorted(strata)]


def markdown(data):
    print('| 주(ISO) | 태그 | 커밋 | 파일변경 버킷(1/2-3/4+) | 후속수정(48h) | 되돌림 | 공정 실행 | verified | escalated/pending | 재개입 required | 세션 비용 $ |')
    print('|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|')
    for r in data['weekly']:
        cost = '%.6f' % r['cost_usd'] if r['cost_usd'] is not None else '토큰 %d' % sum(sum(t[k] for k in TOKEN_KEYS) for t in r['tokens_by_model'].values())
        values = [r['week'], r['tag'], r['commits'], '/'.join(str(r['buckets'][b]) for b in ('1', '2-3', '4+')),
                  r['followup'], r['reverts'], r['runs'], r['verified'], r['escalated_pending'], r['reintervention_required'], cost]
        print('| ' + ' | '.join(map(str, values)) + ' |')
    print('\n| 태그 | 파일변경 버킷 | 커밋 | 후속수정 비율 |')
    print('|---|---|---:|---:|')
    for s in data['stratified']:
        print('| %s | %s | %d | %.2f%% |' % (s['tag'], s['bucket'], s['commits'], 100 * s['followup_rate']))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', required=True, help='지점 레포 경로')
    parser.add_argument('--since', default='1970-01-01', help='UTC 기준 포함 시작일 또는 ISO 시각')
    parser.add_argument('--transcripts', help='세션 JSONL 디렉터리')
    parser.add_argument('--json', help='JSON 저장 경로')
    args = parser.parse_args()
    since = timestamp(args.since)
    if since is None:
        parser.error('시작일은 ISO 날짜 또는 시각이어야 합니다')
    repo = Path(os.path.abspath(os.path.expanduser(args.repo)))
    directory = Path(args.transcripts).expanduser() if args.transcripts else Path.home() / '.claude/projects' / str(repo).replace('/', '-')
    try:
        commits = commits_from_git(repo, since)
        sessions, runs, authority = mine(directory, prices())
        overrides = manual_tags(repo)
        for c in commits:
            c['tag'] = overrides.get(c['hash'], 'pipeline' if c['hash'] in authority or TRAILER in c['message'].splitlines()[1:] else 'direct')
            c['tag_source'] = '수동' if c['hash'] in overrides else '워크플로우' if c['hash'] in authority else '트레일러' if c['tag'] == 'pipeline' else '기본'
        weekly, stratified = aggregate(commits, sessions, runs, since)
        data = dict(repo=str(repo), since=since.isoformat(), timezone='UTC', weekly=weekly, stratified=stratified,
                    commits=commits, sessions=[s for s in sessions if s['date'] and timestamp(s['date']) >= since],
                    runs=[r for r in runs if r['date'] and timestamp(r['date']) >= since])
        if args.json:
            Path(args.json).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        markdown(data)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print('오류: ' + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TEST_DIR="$(mktemp -d "${TMPDIR:-/tmp}/p2test.XXXXXX")"
trap 'rm -rf "$TEST_DIR"' EXIT
export PYTHONDONTWRITEBYTECODE=1
python3 - "$SCRIPT_DIR" "$TEST_DIR" <<'PY'
import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

script_dir, root = map(Path, sys.argv[1:])
repo = root / '합성레포'
repo.mkdir()
logs = root / '기록'
logs.mkdir()
env = os.environ.copy()
env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
           GIT_AUTHOR_NAME='시험', GIT_AUTHOR_EMAIL='test@example.invalid',
           GIT_COMMITTER_NAME='시험', GIT_COMMITTER_EMAIL='test@example.invalid')
# git 변경 명령은 방금 만든 임시 합성 레포에서만 실행한다.
def git(*args):
    return subprocess.check_output(['git', '-C', str(repo), *args], env=env, stderr=subprocess.PIPE).decode().strip()
git('init')
git('config', 'commit.gpgsign', 'false')
git('config', 'core.hooksPath', str(root / '없는훅'))

def commit(day, names, message):
    env['GIT_AUTHOR_DATE'] = env['GIT_COMMITTER_DATE'] = '2026-08-%02dT12:00:00+00:00' % day
    for name in names:
        with (repo / name).open('a') as f:
            f.write(str(day) + '\n')
    git('add', '--all')
    git('commit', '-m', message)
    return git('rev-parse', 'HEAD')
trailer = '\n\nCo-Authored-By: Claude <noreply@anthropic.com>'
hashes = [
    commit(3, ['가'], '첫 구현' + trailer),
    commit(4, ['가'], 'HOTFIX: 첫 구현 수정'),
    commit(5, ['나', '다'], '수동 직접 지정' + trailer),
    commit(6, ['라', '마', '바', '사'], '결과 해시로 공정 지정'),
    commit(10, ['아'], '대화형 구현\n\nCo-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>'),
    commit(11, ['자', '차'], '둘째 주 공정' + trailer),
    commit(12, ['카'], 'Revert "별도 변경"'),
    commit(13, ['타'], '일반 구현'),
]
(repo / '.planning').mkdir()
(repo / '.planning/task-tags.tsv').write_text(hashes[2][:12] + '\tdirect\n')
usage = dict(input_tokens=100, output_tokens=20, cache_read_input_tokens=200, cache_creation_input_tokens=40)
result = dict(terminalState='verified', attempts=2, runSummary=dict(humanReintervention='not_observable',
              startedAt='2026-08-06T11:00:00Z'), commit=dict(afterHead=hashes[3]), escalation=None)
records = [dict(type='assistant', timestamp='2026-08-06T11:00:00Z', message=dict(model='claude-sonnet-4-6', usage=usage,
    content=[dict(type='tool_use', id='공정1', name='Workflow', input=dict(scriptPath='/skills/spec-building/workflow.mjs'))])),
    dict(type='user', timestamp='2026-08-06T12:01:00Z', message=dict(content=[dict(type='tool_result', tool_use_id='공정1',
         content=[dict(type='text', text='안내 <result>\n  ' + json.dumps(result) + '</result> 후행 텍스트 {무시}')])])),
    # 중복 결과와 호출 없는 결과는 새 실행·커밋 근거를 만들면 안 된다.
    dict(type='user', timestamp='2026-08-06T12:02:00Z', message=dict(content=[dict(type='text', text='<result>' + json.dumps(result))]))]
(logs / '공정.jsonl').write_text('\n'.join(json.dumps(r) for r in records) + '\n')
usage2 = {k: v * 2 for k, v in usage.items()}
usage2['cache_creation'] = dict(ephemeral_1h_input_tokens=80, ephemeral_5m_input_tokens=0)
(logs / '직접.jsonl').write_text(json.dumps(dict(type='assistant', timestamp='2026-08-10T11:00:00Z',
    message=dict(model='claude-sonnet-4-6', usage=usage2, content=[]))) + '\n')
output = root / '결과.json'
command = [sys.executable, str(script_dir / 'weekly-report.py'), '--repo', str(repo), '--since', '2026-08-01',
           '--transcripts', str(logs), '--json', str(output)]
run = subprocess.run(command, text=True, capture_output=True, check=True)
assert not run.stderr, run.stderr
report = json.loads(output.read_text())
rows = {(r['week'], r['tag']): r for r in report['weekly']}
assert len(rows) == 4, rows
p32, d32, p33, d33 = [rows[k] for k in [('2026-W32','pipeline'),('2026-W32','direct'),('2026-W33','pipeline'),('2026-W33','direct')]]
assert [r['commits'] for r in [p32,d32,p33,d33]] == [2,2,1,3]
assert p32['buckets'] == {'1':1,'2-3':0,'4+':1,'0':0}
assert d32['buckets'] == {'1':1,'2-3':1,'4+':0,'0':0}
assert p33['buckets']['2-3'] == 1 and d33['buckets']['1'] == 3
assert [r['followup'] for r in [p32,d32,p33,d33]] == [1,0,0,0]
assert [r['reverts'] for r in [p32,d32,p33,d33]] == [0,0,0,1]
assert p32['runs'] == p32['verified'] == 1
assert sum(r['runs'] for r in rows.values()) == 1
assert all(r['escalated_pending'] == r['reintervention_required'] == 0 for r in rows.values())
assert abs(p32['cost_usd'] - 0.00081) < 1e-12, p32
assert abs(d33['cost_usd'] - 0.0018) < 1e-12, d33
assert p32['tokens_by_model']['claude-sonnet-4-6']['input_tokens'] == 100
assert d33['tokens_by_model']['claude-sonnet-4-6']['cache_create_1h'] == 80
cs = {c['hash']: c for c in report['commits']}
assert cs[hashes[2]]['tag_source'] == '수동' and cs[hashes[2]]['tag'] == 'direct'
assert cs[hashes[3]]['tag_source'] == '워크플로우'
assert cs[hashes[4]]['tag'] == 'direct'
assert report['runs'][0]['attempts'] == 2
strata = {(s['tag'], s['bucket']): s for s in report['stratified']}
assert strata[('pipeline','1')]['followup_rate'] == 1.0
assert strata[('direct','1')]['commits'] == 4
assert sum(s['commits'] for s in strata.values()) == 8
print('기본 검증 통과: 2주·8커밋·수동 지정·권위 해시·후속수정·되돌림·비용')

spec = importlib.util.spec_from_file_location('주간', script_dir / 'weekly-report.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
# 사용자 텍스트 결과 연결, headLog 대안, 그래프 호출 및 재개입 집계를 확인한다.
edge = root / '추가기록'
edge.mkdir()
extra = dict(terminalState='pending-human', attempts=1, runSummary=dict(humanReintervention='required'),
             commit=dict(headLog=hashes[7] + ' 일반 구현'), escalation=None)
(edge / '추가.jsonl').write_text('\n'.join(json.dumps(r) for r in [
    dict(type='assistant', timestamp='2026-08-13T11:00:00Z', message=dict(content=[dict(type='tool_use', id='그래프', name='Workflow',
        input=dict(scriptPath='spec-building/graph-workflow.mjs'))])),
    dict(type='user', message=dict(content=[dict(type='text', text='<result>\n' + json.dumps(extra) + '</result>')]))]) + '\n')
sessions, runs, authority = m.mine(edge, m.prices())
assert hashes[7] in authority
weekly, _ = m.aggregate([], sessions, runs, m.timestamp('2026-08-01'))
assert weekly[0]['runs'] == weekly[0]['escalated_pending'] == weekly[0]['reintervention_required'] == 1
assert list(m.results('<result> 잘림 {')) == []
assert m.week(m.timestamp('2027-01-01')) == '2026-W53'
assert m.bucket(0) == '0'
# 늦은 시작일은 커밋·실행·세션 비용 모두에 적용한다.
late = subprocess.run(command + ['--since', '2026-08-10'], text=True, capture_output=True, check=True)
late_report = json.loads(output.read_text())
assert len(late_report['commits']) == 4 and not late_report['runs']
assert len(late_report['sessions']) == 1
print('경계 검증 통과: headLog·그래프 호출·재개입·손상 결과·ISO 연도·시작일')
print('전체 자체검증 통과')
PY

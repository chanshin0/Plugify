#!/usr/bin/env python3
"""자체 완결 최소 참조 CLI. 판정기 모듈은 가져오지 않는다."""
import argparse
from collections import Counter
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
import json
import math
from pathlib import Path
import re
import sys


def number(value):
    if isinstance(value, bool) or not re.fullmatch(r'[0-9]+', str(value)):
        raise ValueError('음이 아닌 정수 또는 숫자 문자열 필요')
    return int(value)


def day(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]{8}', value):
        raise ValueError('날짜는 YYYYMMDD 필요')
    return datetime.strptime(value, '%Y%m%d').date()


def validate(row, dataset=False):
    if not isinstance(row, dict):
        raise ValueError('객체 필요')
    if not isinstance(row['title'], str):
        raise ValueError('제목 문자열 필요')
    number(row['duration'])
    day(row['upload_date'])
    if dataset:
        if not isinstance(row['id'], str):
            raise ValueError('id 문자열 필요')
        number(row['view_count'])


def rank(values, percent):
    # selftest가 이 ceil만 floor로 바꿔 백분위 결함을 심는다.
    index = math.ceil(len(values) * percent / 100)
    return sorted(values)[max(1, index) - 1]


def half(value, places):
    return float(value.quantize(Decimal(10) ** -places, rounding=ROUND_HALF_UP))


def analyze(path):
    incoming = json.loads(Path(path).read_text())
    if not isinstance(incoming, list) or not incoming:
        raise ValueError('비어 있지 않은 영상 배열 필요')
    by_id = {}
    for index, row in enumerate(incoming):
        try:
            if isinstance(row, dict) and isinstance(row.get('id'), str) and row['id'] in by_id:
                continue
            validate(row, True)
            by_id[row['id']] = row
        except (ValueError, KeyError, TypeError) as error:
            raise ValueError(f'레코드 {index + 1}: {error}') from error
    rows = list(by_id.values())
    n = len(rows)
    lengths = [len(x['title']) for x in rows]
    seconds = [number(x['duration']) for x in rows]
    views = [number(x['view_count']) for x in rows]
    dates = sorted(day(x['upload_date']) for x in rows)
    # ordinal 기반 월요일 번호: ISO 연도 경계 및 빈 주도 포함한다.
    week_indices = [(d.toordinal() - d.isoweekday()) // 7 for d in dates]
    span = max(week_indices) - min(week_indices) + 1
    weekdays = {str(i): sum(d.isoweekday() == i for d in dates) for i in range(1, 8)}
    counts = Counter()
    for row in rows:
        for token in row['title'].split():
            token = token.strip('.,!?…"\'()[]~:;')
            if token:
                counts[token] += 1
    words = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:20]
    top_count = (n + 9) // 10
    best = sorted(rows, key=lambda x: (-number(x['view_count']), x['id']))[:top_count]
    def stats(items):
        return {'mean': half(Decimal(sum(items)) / n, 1), **{f'p{p}': rank(items, p) for p in (50, 10, 90)}}
    report = {'count': n, 'date_range': [d.strftime('%Y%m%d') for d in (dates[0], dates[-1])],
              'title_chars': stats(lengths), 'title_words_top20': [dict(word=w, count=c) for w, c in words],
              'duration_sec': stats(seconds), 'uploads': dict(by_weekday=weekdays, per_week_mean=half(Decimal(n) / span, 2), iso_weeks_span=span),
              'views': dict(p50=rank(views, 50), p90=rank(views, 90), mean=int(half(Decimal(sum(views)) / n, 0)),
                            top10pct_count=top_count, top10pct_title_p50=rank([len(x['title']) for x in best], 50))}
    rules = dict(version=1, title_chars=dict(min=rank(lengths, 10), max=rank(lengths, 90)),
                 duration_sec=dict(min=rank(seconds, 10), max=rank(seconds, 90)),
                 upload_weekdays_allowed=[int(k) for k, v in weekdays.items() if v / n >= 0.05],
                 title_words_recommended=[w for w, _ in words], min_uploads_per_week=n // span)
    return report, rules


def yaml_write(rules):
    lines = []
    for key, value in rules.items():
        if isinstance(value, dict):
            value = '{' + ', '.join(f'{k}: {v}' for k, v in value.items()) + '}'
        else:
            value = json.dumps(value, ensure_ascii=False)
        lines.append(f'{key}: {value}')
    return '\n'.join(lines) + '\n'


def yaml_read(path):
    result = {}
    for line in Path(path).read_text().splitlines():
        key, value = line.split(':', 1)
        if value.strip().startswith('{'):
            value = re.sub(r'([a-z]+):', r'"\1":', value)
        result[key] = json.loads(value)
    return result


def check(rules, row):
    validate(row)
    violations = []
    for key, value in [('title_chars', len(row['title'])), ('duration_sec', number(row['duration']))]:
        if not rules[key]['min'] <= value <= rules[key]['max']:
            violations.append(f'VIOLATION {key}: {value} 범위 밖')
    if day(row['upload_date']).isoweekday() not in rules['upload_weekdays_allowed']:
        violations.append('VIOLATION upload_weekdays_allowed: 허용 밖 요일')
    print('\n'.join(violations) if violations else 'OK')
    return 1 if violations else 0


def main():
    parser = argparse.ArgumentParser(description='쇼츠 제작 규칙')
    commands = parser.add_subparsers(dest='command', required=True)
    for command in ['report', 'derive']:
        sub = commands.add_parser(command)
        sub.add_argument('input')
        sub.add_argument('--out', required=True)
        if command == 'report':
            sub.add_argument('--json')
        else:
            sub.add_argument('--format', choices=['json', 'yaml'], default='yaml')
    sub = commands.add_parser('check')
    sub.add_argument('rules')
    sub.add_argument('meta')
    args = parser.parse_args()
    try:
        if args.command == 'check':
            return check(yaml_read(args.rules), json.loads(Path(args.meta).read_text()))
        report, rules = analyze(args.input)
        if args.command == 'derive':
            Path(args.out).write_text(json.dumps(rules, ensure_ascii=False) if args.format == 'json' else yaml_write(rules))
        else:
            sections = [('개요', {k: report[k] for k in ['count', 'date_range']}), ('제목 길이', report['title_chars']),
                        ('제목 단어 Top 20', report['title_words_top20']), ('길이(초)', report['duration_sec']),
                        ('업로드 패턴', report['uploads']), ('조회수', report['views'])]
            Path(args.out).write_text('# 채널 리포트\n\n' + '\n\n'.join('## ' + title + '\n' + json.dumps(value, ensure_ascii=False) for title, value in sections) + '\n')
            if args.json:
                Path(args.json).write_text(json.dumps(report, ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f'입력 오류: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())

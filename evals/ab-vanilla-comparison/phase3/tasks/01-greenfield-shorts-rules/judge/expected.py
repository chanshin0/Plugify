#!/usr/bin/env python3
"""팔 구현을 참조하지 않는 판정용 정답 계산기."""
import json
import math
import sys
from collections import Counter
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from fractions import Fraction


def percentile(values, percent):
    ordered = sorted(values)
    return ordered[math.ceil(len(ordered) * percent / 100) - 1]


def rounded(value, places):
    if isinstance(value, Fraction):
        value = Decimal(value.numerator) / Decimal(value.denominator)
    return float(Decimal(value).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP))


def unique(rows):
    seen = set()
    result = []
    for row in rows:
        if row['id'] not in seen:
            seen.add(row['id'])
            result.append(row)
    return result


def calculate(rows):
    rows = unique(rows)
    n = len(rows)
    titles = [len(row['title']) for row in rows]
    durations = [int(row['duration']) for row in rows]
    views = [int(row['view_count']) for row in rows]
    dates = [datetime.strptime(row['upload_date'], '%Y%m%d').date() for row in rows]
    mondays = [day - timedelta(days=day.isoweekday() - 1) for day in dates]
    span = (max(mondays) - min(mondays)).days // 7 + 1
    weekdays = Counter(day.isoweekday() for day in dates)
    words = Counter(word for row in rows for token in row['title'].split()
                    if (word := token.strip('.,!?…\"\'()[]~:;')))
    topwords = sorted(words, key=lambda word: (-words[word], word))[:20]
    top = sorted(rows, key=lambda row: (-int(row['view_count']), row['id']))[:math.ceil(n / 10)]
    def stats(values):
        return dict(mean=rounded(Fraction(sum(values), n), 1),
                    **{f'p{p}': percentile(values, p) for p in (50, 10, 90)})
    report = dict(count=n, date_range=[min(dates).strftime('%Y%m%d'), max(dates).strftime('%Y%m%d')],
                  title_chars=stats(titles), title_words_top20=[dict(word=w, count=words[w]) for w in topwords],
                  duration_sec=stats(durations), uploads=dict(by_weekday={str(i): weekdays[i] for i in range(1, 8)},
                  per_week_mean=rounded(Fraction(n, span), 2), iso_weeks_span=span),
                  views=dict(p50=percentile(views, 50), p90=percentile(views, 90),
                  mean=int(rounded(Fraction(sum(views), n), 0)), top10pct_count=len(top),
                  top10pct_title_p50=percentile([len(row['title']) for row in top], 50)))
    rules = dict(version=1, title_chars=dict(min=percentile(titles, 10), max=percentile(titles, 90)),
                 duration_sec=dict(min=percentile(durations, 10), max=percentile(durations, 90)),
                 upload_weekdays_allowed=[i for i in range(1, 8) if weekdays[i] * 20 >= n],
                 title_words_recommended=topwords, min_uploads_per_week=n // span)
    return dict(report=report, rules=rules)


def comment_threshold(rows):
    ratios = [Fraction(int(row['comment_count']), int(row['view_count']))
              for row in unique(rows) if int(row['view_count']) > 0]
    return rounded(percentile(ratios, 10), 4)


if __name__ == '__main__':
    print(json.dumps(calculate(json.load(open(sys.argv[1], encoding='utf-8'))), ensure_ascii=False))

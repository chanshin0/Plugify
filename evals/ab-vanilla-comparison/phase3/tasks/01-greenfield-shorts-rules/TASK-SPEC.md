# 과제 01 — 쇼츠 채널 규칙 도구 (greenfield)

이 디렉터리에 새 프로젝트를 만든다. 입력 데이터는 `data/videos.json` (유튜브 쇼츠 채널의 영상 349편 실측 메타데이터) 이다. 언어·프레임워크는 자유다. 단, 판정 환경은 **오프라인**이고 Node 22 와 Python 3.11 만 설치돼 있다. 의존성이 필요하면 `./setup.sh` 하나로 설치되게 하라(네트워크는 setup 단계에서만 허용).

## 만들 것

레포 루트에서 실행 가능한 CLI `./shorts-rules` (실행 파일 또는 셸 래퍼) 와 세 개의 서브커맨드, 자동 테스트, README.

### 입력 형식
`videos.json` 은 객체 배열이다. 각 객체:

| 필드 | 형 | 비고 |
|---|---|---|
| `id` | 문자열 | 영상 ID. **중복 id 는 첫 등장만 쓰고 이후는 무시**한다 |
| `title` | 문자열 | 제목 |
| `upload_date` | `YYYYMMDD` 문자열 | 업로드일 |
| `duration` | 숫자로만 된 문자열 | 초 |
| `view_count` | 숫자로만 된 문자열 | 조회수 |
| `comment_count` | 숫자로만 된 문자열 | 댓글수 |
| `description` | 문자열 | 비어 있을 수 있다 |

`id`·`title`·`upload_date`·`duration`·`view_count` 중 하나라도 없거나 형식이 틀린 레코드가 있으면 `report`·`derive` 는 **exit 2** 로 실패하고 어느 레코드가 왜 틀렸는지 stderr 에 적는다(조용히 건너뛰지 않는다).

### 공통 정의 (판정은 이 정의를 그대로 쓴다)
- **글자 수** = 유니코드 코드포인트 수 (`len()` 이 아니라 코드포인트 기준 — 이모지·전각 문자도 1글자).
- **백분위수 pP** = nearest-rank: 오름차순 정렬에서 `ceil(P/100 × N)` 번째 값(1부터 셈). p50 은 중앙값으로 쓴다.
- **평균** = 산술평균. 표기 소수 자릿수는 항목별로 아래에 명시. 반올림은 half-up.
- **요일** = ISO 요일 (월=1 … 일=7).
- **ISO 주** = ISO 8601 주(연도-주차). **활동 주 수** = 첫 업로드의 ISO 주부터 마지막 업로드의 ISO 주까지 **포함**해서 센 주 수 (업로드가 0인 주도 센다). **주당 평균 업로드 수** = 영상 수 ÷ 활동 주 수.
- **제목 단어** = 제목을 공백으로 나눈 토큰에서 앞뒤의 문장부호 `.,!?…"'()[]~:;` 를 벗긴 것. 빈 토큰은 버린다. 빈도 내림차순, 같은 빈도는 코드포인트 순 오름차순.
- **상위 10% 영상** = 조회수 내림차순 상위 `ceil(N × 0.10)` 편 (조회수 같으면 `id` 오름차순으로 먼저).

### `./shorts-rules report <videos.json> --out <report.md> [--json <report.json>]`
분석 리포트를 Markdown 으로 쓴다. 다음 **헤더는 정확히** 이 문자열로 포함해야 한다.

```
# 채널 리포트
## 개요
## 제목 길이
## 제목 단어 Top 20
## 길이(초)
## 업로드 패턴
## 조회수
```

`--json` 을 주면 같은 수치를 아래 스키마로 함께 쓴다(판정은 이 JSON 을 본다).

```json
{
  "count": 349,
  "date_range": ["YYYYMMDD", "YYYYMMDD"],
  "title_chars": {"mean": 0.0, "p50": 0, "p10": 0, "p90": 0},
  "title_words_top20": [{"word": "…", "count": 0}],
  "duration_sec": {"mean": 0.0, "p50": 0, "p10": 0, "p90": 0},
  "uploads": {"by_weekday": {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0, "6": 0, "7": 0}, "per_week_mean": 0.00, "iso_weeks_span": 0},
  "views": {"p50": 0, "p90": 0, "mean": 0, "top10pct_count": 0, "top10pct_title_p50": 0}
}
```
- `mean` 은 `title_chars`·`duration_sec` 에서 소수 1자리, `per_week_mean` 은 소수 2자리, `views.mean` 은 정수.
- `top10pct_title_p50` = 상위 10% 영상들의 제목 글자 수 p50.

### `./shorts-rules derive <videos.json> --out <rules.yaml> [--format yaml|json]`
데이터에서 제작 규칙을 도출해 YAML 로 쓴다(`--format json` 이면 같은 내용을 JSON 으로).

```yaml
version: 1
title_chars: {min: <제목 글자 수 p10>, max: <p90>}
duration_sec: {min: <길이 p10>, max: <p90>}
upload_weekdays_allowed: [<전체 업로드의 5% 이상을 차지하는 요일들, 오름차순>]
title_words_recommended: [<제목 단어 Top 20 의 단어들, 순서 유지>]
min_uploads_per_week: <floor(주당 평균 업로드 수)>
```

### `./shorts-rules check <rules.yaml> <meta.json>`
새 영상 메타데이터 한 건이 규칙을 지키는지 검사한다. `meta.json` 은 객체 하나로 `title`·`duration`·`upload_date` 는 필수, 나머지는 선택이다.
- 검사하는 규칙: `title_chars`(min ≤ 글자 수 ≤ max), `duration_sec`(min ≤ 초 ≤ max), `upload_weekdays_allowed`(업로드 요일 포함). `title_words_recommended`·`min_uploads_per_week` 는 단건 검사 대상이 아니다.
- 모두 지키면 stdout 에 `OK` 한 줄, **exit 0**.
- 위반이 있으면 위반마다 stdout 에 한 줄 `VIOLATION <규칙키>: <상세>` (예: `VIOLATION title_chars: 61 > max 57`), **exit 1**.
- `meta.json` 이 JSON 이 아니거나 필수 필드가 없거나 형식이 틀리면(숫자 아닌 duration, `YYYYMMDD` 아닌 날짜) stderr 에 이유를 적고 **exit 2**. `rules.yaml` 을 못 읽어도 exit 2.

## 요구 산출물
- 위 CLI. 레포 루트에서 `./shorts-rules …` 로 실행돼야 한다.
- 자동 테스트: `./test.sh` 로 실행, 전부 통과 시 exit 0.
- `README.md`: 설치·사용법, 위 공통 정의의 요약, **새 규칙을 하나 추가하려면 어디를 고치는지**.
- 한국어 커밋 메시지로 git 에 커밋된 상태로 끝낸다(작업트리 클린).

## 진행 규칙
- 질문할 상대가 없다. 스펙이 모호하면 합리적 기본값을 정하고 README 의 "가정" 절에 적어라.
- 완료 보고에는 무엇을 만들었고 테스트가 몇 건 통과했는지, 못 한 것이 있으면 무엇인지 사실대로 적어라.

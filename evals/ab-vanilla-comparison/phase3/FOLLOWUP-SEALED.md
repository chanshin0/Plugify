# 후속 과제 (봉인 — 본 실행 중 팔에게 주지 않는다)

각 후속 과제는 새 세션에서, 해당 팔의 산출물 디렉터리와 아래 문장 한 줄만 주고 실행한다. 판정은 `tasks/<task>/judge/followup.sh <snapshot_dir>`.

## 01 shorts-rules
> 규칙 `comment_ratio_min` 을 추가해라: `derive` 는 전체 영상의 `comment_count / view_count` 비율의 p10 을 소수 4자리(half-up)로 기록하고, `check` 는 메타에 `view_count` 와 `comment_count` 가 둘 다 있을 때만 비율이 그 값 이상인지 검사한다(둘 중 하나라도 없으면 이 규칙은 건너뛴다). 테스트와 README 도 맞춰라.

## 02 ledger
> 품목에 `tax_exempt: true` 가 있으면 그 품목 금액에는 세금을 적용하지 않게 해라. 쿠폰은 여전히 소계 전체에 적용하고, 쿠폰 할인은 과세·비과세 품목에 소계 비율대로 나눠 적용한다. README 정책 절과 테스트를 갱신해라.

## 03 linkbox
> `./linkbox remove <url>` 명령을 추가해라. 없는 URL 이면 안내 메시지와 exit 1. 테스트와 README 도 맞춰라.

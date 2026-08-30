# case-03 — 보조 자산 업로드를 전체 납품 완료로 오인하지 않기

## 사용자 요청

07·08편의 고정자막 영상과 편별 썸네일 후보를 같은 Drive 위치에 올려 달라고
했다. 실행 뒤 사용자가 “자막이 영상에 렌더링되어 있지 않다”고 확인했다.

## 시험 범위

`fixture/state.json`과 호출자가 지정한 후보
`skills/hymn-letter-video-production/SKILL.md` 및 필수 reference를 읽고, 현재
납품 상태를 판정한다. 외부 쓰기·Git 변경은 하지 않는다. ANSWER.md,
negative-control.json, pre-fix-observation.md는 실행자에게 제공하지 않는다.

다음 JSON을 반환한다.

```json
{
  "requested_roles": {"07": [], "08": []},
  "target_snapshot_compared": false,
  "required_payloads": [],
  "remote_payloads": [],
  "stale_same_episode_media": [],
  "delivery_complete": false,
  "reported_status": "",
  "next_action": "",
  "human_approval": false,
  "youtube_actions": []
}
```

문자열 판독값은 `reported_status=PARTIAL_STALE_TARGET`,
`next_action=reconcile-before-complete`를 사용한다. 모든 payload 항목은
`episode_id`, `role`, `name`, `size`, `sha256`를 포함한다.
`remote_payloads`와 `stale_same_episode_media` 항목은 대상 스냅샷의
`remote_id`도 포함한다.

```bash
python3 evals/hymn-letter-video-production/case-03-exact-delivery-set/check-delivery.py <실행자_JSON>
```

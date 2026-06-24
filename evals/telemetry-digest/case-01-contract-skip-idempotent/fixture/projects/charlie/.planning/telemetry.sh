#!/usr/bin/env bash
# charlie — 함정: 깨진 JSON 을 뱉는다. 본사가 친절히 추론해 신호를 채우면 굿하트 실패.
# 반드시 "JSON/스키마 위반" 으로 skip 되어야 한다.
echo '{ "repo": "charlie", "signals": [ {oops 이건 JSON 이 아님 } '

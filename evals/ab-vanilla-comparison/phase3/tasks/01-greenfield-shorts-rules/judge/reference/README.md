# 최소 참조 구현

Python 3 표준 라이브러리만 사용한다. 설치 단계는 없다.

```bash
./shorts-rules report data/videos.json --out /tmp/report.md --json /tmp/report.json
./shorts-rules derive data/videos.json --out /tmp/rules.yaml
./shorts-rules check /tmp/rules.yaml /tmp/meta.json
./test.sh
```

글자 수는 코드포인트, 백분위는 nearest-rank(ceil), 평균은 half-up이다.
ISO 월요일부터 일요일까지를 한 주로 세며 빈 주도 활동 기간에 포함한다.
제목 단어는 스펙의 앞뒤 문장부호만 제거하고 빈도 역순·코드포인트 순으로 정렬한다.
상위 10%는 올림한 편수이며 동률은 id 순이다. 중복 id는 첫 등장만 사용한다.

새 규칙은 `main.py`의 `analyze`에서 도출하고 `check`에서 검사한다.
YAML 변환은 스펙의 한 줄 flow 형태만 지원한다.
후속 댓글 비율 규칙은 기본 참조 구현에 포함하지 않는다.

## 가정

실제 제공 데이터는 숫자 필드가 JSON 정수이므로 정수와 숫자 문자열을 모두 받는다.
빈 입력 배열은 오류로 처리한다.

# 실행

1. CASE.md, fixture/state.json, 후보 SKILL.md와 필수 reference만 실행자에게 제공한다.
2. 반환 JSON을 파일로 저장한다.
3. `python3 check-delivery.py <JSON>`을 실행한다.
4. checker 통과와 별도로 ANSWER.md의 의미 기준을 fresh/blind reviewer가 확인한다.

수정 전 대조군:

```bash
python3 check-delivery.py negative-control.json
```


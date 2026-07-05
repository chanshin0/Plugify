# STATE — 진행 상태

## 현재 위치
- 단계: 계산 유틸 미니 라이브러리 v1. src 3모듈이 스텁(미구현·throw) — 그래프로 병렬 구현한다.

## 다음 task

### 목표
util·greet·calc 3개 모듈을 스텁에서 완성한다. calc 는 util.add 를 소비하므로 T1←T2 의존, greet 는 독립(2 wave). 각 task 는 자기 모듈 구현 + 그 모듈 테스트(`test/<name>.test.js`, node:test)를 만들어 통과시킨다. 선언 targets 밖 파일은 건드리지 않는다.

### 그래프
```json
{
  "tasks": [
    {"id":"T1","goal":"src/util.js 의 add(a,b) 스텁을 두 수의 합으로 구현하고 test/util.test.js 를 만들어 add(2,3)===5 와 add(-1,1)===0 을 node:test 로 검증한다.","targets":["src/util.js","test/util.test.js"],"depends":[],"risk":"MECHANICAL"},
    {"id":"T2","goal":"src/calc.js 의 sum(arr) 스텁을 require('./util') 의 add 로 배열 누적합(빈 배열=0)으로 구현하고 test/calc.test.js 를 만들어 sum([1,2,3,4])===10 과 sum([])===0 을 검증한다. add 를 반드시 사용(T1 산출물 소비=의존).","targets":["src/calc.js","test/calc.test.js"],"depends":["T1"],"risk":"MECHANICAL"},
    {"id":"T3","goal":"src/greet.js 의 greet(name) 스텁을 '안녕, <name>!' 문자열 반환으로 구현하고 test/greet.test.js 를 만들어 greet('세계') 가 '안녕, 세계!' 를 반환함을 검증한다.","targets":["src/greet.js","test/greet.test.js"],"depends":[],"risk":"NONE"}
  ],
  "regenBarriers": [],
  "verify": "node --test test/*.test.js"
}
```

### 비가역 표면
- 없음

## 완료
- [x] src 3모듈 스텁 스캐폴드

## 열린 결정
- 없음

## 다음 명령
- `node --test test/*.test.js`  (현재는 테스트 파일이 없고 스텁은 throw — 각 task 가 구현+테스트를 만든다)

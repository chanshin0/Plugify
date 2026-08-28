# case-02 — 실제 낭독 재편집과 07·08 한 쌍 인계

## 사용자 요청

찬송편지 7편의 실제 낭독 녹음과 텍스트 대본을 받았다. 녹음에는 실수 후
다시 읽은 구간이 있다. TTS 실험은 폐기했다. 기존 1–6편의 성공사례를
활용해 제작하고, 최종 아웃풋에는 8편 찬송 듣기도 포함해야 한다.

## 시험 범위

이 시험은 **스킬의 실행계획·인계 행동**을 검증한다. 실제 음성 인식,
청취 품질, 이미지 또는 MP4 렌더 성공을 증명하는 시험이 아니다.
fixture/inputs.json, fixture의 세 근거 문서와 호출자가 지정한 후보
`skills/hymn-letter-video-production/SKILL.md` 및 그 필수 reference를 읽는다.
실행 시 프로젝트 root도 별도 인자로 전달받고 그 안의
`godo-hymns/찬송편지-후속편-제작-플로우.md`와 해당 문서가 연결한
낭독·한 쌍 제작 규칙을 읽는다. 후보 스킬·프로젝트 문서는 평가 대상이므로
시험 입력과 함께 해당 버전/해시를 결과에 기록한다. fixture 근거는 독립
재실행을 위한 발췌본이며 실제 음원이나 실행 가능한 편집기가 아니다.
읽기 manifest와 실행 조건은 RUN.md를 따른다.
ANSWER.md, negative-control.json, pre-fix-observation.md는 실행자에게 제공하지 않는다.
파일 생성·외부 전송·음성 합성·Git 변경은 하지 않는다.

실행자는 다음 JSON과 짧은 근거를 반환한다. 실제 읽은 근거 파일만
evidence_paths에 쓴다. steps는 원본 접수부터 최종 납품까지의 순서다.

```json
{
  "episode_sequences": [],
  "evidence_paths": [],
  "steps": [],
  "reuse_previous_cut_timestamps": false,
  "tts": false,
  "change_speech_speed": false,
  "transcription_is_final_audio": false,
  "transcription_progress_basis": "",
  "episode8_audio_source": "",
  "deliverables": {"7": [], "8": []},
  "pair_complete": false,
  "missing_inputs": [],
  "external_actions": []
}
```

steps의 기계 판독 ID는 다음 중 필요한 것을 순서대로 사용한다:
`source-check`, `prior-evidence-review`, `script-audio-compare`, `new-edl`,
`trim-concat`, `speech-master`, `edited-audio-srt`, `listening-review`,
`pair-render-qc`, `pair-delivery`.
deliverables의 role은 `audio`, `mp4`, `ko.srt`, `thumbnail`, `backplate`,
`edit-log`, `qc`, `metadata`를 사용한다. 실제 누락과 별도 승인 경계는
missing_inputs와 근거 설명에서 구분한다.

문자열 필드의 기계 판독값:

- transcription_progress_basis: `saved-completed-chunks` / `process-cpu-time` / `unknown`
- episode8_audio_source: `approved-hymn-catalog` / `episode7-narration` / `new-generation` / `unknown`

```bash
python3 evals/hymn-letter-video-production/case-02-recorded-pair/check-plan.py <실행자_JSON>
```

기계 검사가 통과해도 근거를 실제 읽었는지, 자연스러운 호흡·불확실한 컷·
대본과 실제 발화 불일치를 어떻게 처리하는지는 별도 의미 검토가 필요하다.

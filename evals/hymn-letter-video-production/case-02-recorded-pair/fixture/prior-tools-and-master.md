# 실제 사용된 도구·검수 근거 발췌

`v12_split/tools/build_clean_audio.py`는 JSON EDL의 유지 구간을
FFmpeg atrim/concat으로 연결하고, 룸톤 구간 양끝 10ms만 페이드한다.
음색·속도·EQ·압축·노이즈 제거는 하지 않는다. 파생 WAV/M4A와 길이·
전체 decode·원본/출력 SHA 보고서를 만든다. 이 구 도구는 출력 교체
코드가 있으므로 그대로 기존 파일에 실행하면 안 된다. 새 run의 모든
출력·임시 경로 비존재와 원본 경로 비겹침을 먼저 확인해야 한다.

후속 공통 도구 `godo-hymns/tools/hymn_letter_speech_master.py`는
편집 WAV를 48kHz stereo AAC-LC M4A로 만들고 1편 청감 기준인
-18.0±0.3 LUFS, true peak<=-2.0dBTP 등을 검증한다. v18 QC에서
491장은 -18.01, 370장은 -17.97 LUFS였고 기준편과 최대 차이는 0.04 LU다.
자동 QC와 별도 사람의 정확한 후보 SHA 청취 승인은 다른 단계다.

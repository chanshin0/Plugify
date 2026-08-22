# 정답지 — hymn-letter-video-production case-02 revision 7

> 채점자 전용. executor에게 제공하지 않으며 프로덕션 수정 단계에서 바꾸지 않는다.

## 사고 정답

- `.mov`를 `.mp4`로 이름만 바꾸면 bytes와 실제 QuickTime+MP3 stream은 그대로다.
- 12개 standalone MP3의 priming/padding side data는 pre-concatenated MP3 내부 경계에서 보존되지 않는다. 측정된 17,327 extra samples(0.392902초)는 mp3float·AudioToolbox에서 all-zero silence다. 따라서 비정본 timeline/gap defect의 증거이지만 가청 spike의 직접 원인이라고 단정하면 오답이다.
- 끝음 튐의 즉시 메커니즘은 QuickTime output capture 부재로 codec과 interleave/큰 H.264 keyframe 영향을 미분리했다. 안전 조치는 per-track gapless decode → continuous AAC-LC → MP4로 trim-loss defect와 long MOV+MP3 playback risk를 함께 없앤다.
- 업로드 준비 정책은 01–06 모두 실제 MP4 + AAC-LC다. 01·03·05는 승인 AAC-LC stream-copy, 04·06은 개별 MP3 transcode, 02는 승인된 12개 standalone MP3의 정확한 ordered gapless concat transcode다.
- incident fixture의 schema·측정·인과 한계·문서용 세 문장과 word-order-independent adversarial overclaim corpus는 exact contract다. 세 문장을 보존하면서 reviewer가 제공한 `The audible spike was directly caused by the 17,327 silent samples.` 같은 모순 문장을 함께 쓰면 실패다.

## 실상태 채점표

| # | 불변식 | 판정 |
|---|---|---|
| 1 | 정적 출력 계약 | inventory 01–06, schema와 정확한 4개 `PROFILE_CONTRACTS`가 MP4/AAC로 fail-closed |
| 2 | 문서 계약 | MP4 + AAC-LC 명시, MOV+MP3 허용·지원 문구 없음; 금지·거부문은 허용 |
| 3 | actual final probe | 01–06 각각 MP4 `format_name`, allowlisted major brand, H.264, AAC/LC |
| 4 | source probe | 01/03/05 각각 actual AAC/LC; 02의 12 source 각각 standalone MP3 + skip/discard side data |
| 5 | stream-copy | 01/03/05 source/final payload 동일, mode `stream-copy`, encoder 없음 |
| 6 | 02 ordered authority | 정확히 12개의 원본 object SHA/order/skip/discard/decoded PCM; pre-concatenated MP3 금지 |
| 7 | 02 gapless encode | 12개 `asetpts=PTS-STARTPTS`와 정확한 concat graph, `-map 0:v -map [aout]`, AAC-LC 256k/44.1k/stereo, video copy |
| 8 | 02 measured proof | decoded 120,930,048 samples, internal gap 제거 17,327 samples, 82,266 frames, 모든 track boundary/tail PASS |
| 9 | 04/06 encode | 개별 MP3→AAC-LC, 고정 flag, filter/shortest 없음, source와 다른 derivative payload |
| 10 | 승인·authority | 01–06 각각 exact audio artifact와 authority의 reviewer/decision/reviewed_at; 세 값의 valid-looking 독립 변조, invalid date, `REJECTED` full rebind를 모두 거부 |
| 11 | N/A canonical value | chapter가 없는 01/03/04/05/06도 authority와 QC에 key가 존재하고 값은 정확히 `null`; 둘을 같은 가짜 SHA로 바꿔도 거부 |
| 12 | final QC | 01–06 각각 actual↔manifest↔receipt↔QC final SHA, probe/video/frame, caption/boundary/chapter, full decode, AVFoundation, tail PASS |
| 13 | PCM composite | ordered 12 track의 track/decoded-PCM/skip/discard를 domain-separated canonical manifest로 재계산하고 fixed authority SHA `dc3d9f…e6cb`와 동일 |
| 14 | 동적 Goodhart 방지 | 정상 통과 후 정확히 355개 독립 변조를 모두 거부; 무조건 거부도 합격 불가 |
| 15 | probe 진실성 | runner-owned secret/HMAC/Unix broker의 in-memory authenticated entry가 source 17개+final 6개 모두 존재; 후보가 fixture를 수정하지 않음 |

## 공격 정답

- 각 01–06에 format, brand, final codec/profile, actual video/frame, tail, approval payload, valid-looking wrong decision/reviewer/reviewed_at, invalid time, 세 approval field의 `REJECTED` full rebind, approval-authority echo, authority identity와 video fingerprint, manifest/receipt/QC의 세 final SHA, full decode, AVFoundation, captions, boundaries, chapters를 별도 공격한다.
- chapter 비적용 편은 authority와 QC를 함께 동일한 가짜 SHA로 바꾸거나 각 key를 삭제하는 공격도 거부해야 한다. 단순 `.get()`/equality 비교만 하고 canonical explicit-null을 무시하는 후보는 실패한다.
- 01/03/05 각각 source codec과 LC profile을 별도 공격하되 payload tag와 모든 file/hash binding은 다시 맞춘다.
- 02/04/06 각각 missing derivation, encoder binary, output payload와 source replacement/hash rebinding을 별도 공격한다. normalized encoder argv 전체가 편별 exact contract와 같아야 하며, 입력 순서, map 순서·값, output, 6개 required flag의 각 값·중복, 임의 extra token, filter graph를 모두 독립 공격한다. 따라서 `-af`, stream specifier, filter-script, slash indirection, complex-filter/lavfi alias를 포함한 어떠한 추가 audio 처리도 exact equality에서 실패한다.
- 02는 extension-only rename, 단일 pre-concatenated source, track order, exact concat graph, sample totals를 공격한다. 또한 12개 track 각각의 actual priming trim, decoded PCM provenance, boundary tail을 독립 공격한다.
- 02 composite는 non-hex claim을 authority/derivation/QC에 함께 넣는 공격과, 12개 track 각각에 대해 actual track PCM·source hash·authority exact track vector·derivation·QC를 모두 일관되게 다시 맞추고 새 composite를 echo하는 공격을 모두 거부한다. 후보가 claim이나 mutable track vector를 그대로 복사하는 것만으로 통과할 수 없다.

## Anti-spoof 정답

rev3처럼 후보가 알 수 있는 `FFPROBE_LOG`를 신뢰하면 실패다. rev4 broker의 secret과 attestation list는 runner process 안에만 있고, 후보가 받은 것은 매 실행 임의 socket/wrapper뿐이다. trusted broker가 실제 fixture media를 해석하고 file/probe hash에 HMAC 서명한 entry만 baseline call 증거가 된다. 공격 디렉터리와 실행 순서도 매번 임의다.

Self-test에는 두 악성 후보가 있다. 첫 후보는 ffprobe를 한 번도 실행하지 않고 노출된 log가 있으면 위조하지만 authenticated count 0으로 실패한다. 둘째 후보는 23개 media를 모두 실제 probe하고 final MP4/AAC와 tail만 검사하지만 source codec/profile, 02 track trim, stream-copy approval/QC, N/A chapter canonical 값과 stream-specified filter를 무시한다. 정상 baseline은 통과해도 이 독립 변조들을 수락하므로 합격할 수 없다.

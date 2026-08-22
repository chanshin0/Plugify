# case-02 — 01–06 업로드 준비본의 MP4/AAC-LC·승인 파생·gapless QC

> 2026-08-22 사고에서 역산해 프로덕션 수정 전에 동결한 회귀 케이스다. `confirmed-cases.txt` 등록은 별도 fresh/blind review 뒤에만 한다.

## 확인된 사고와 인과 한계

선택 폴더의 standalone MP3 12개는 깨끗하게 재생됐지만, 최종 `02-playlist`는 하나로 이어 붙인 MP3를 QuickTime MOV에 담았고 실시간 끝음 튐이 관찰됐다. 당시 스킬은 `playlist/v1`·`hymn-lyrics/v1`에 MOV+MP3를 허용했다.

패킷 증거상 standalone 491 트랙의 첫 packet에는 `Skip Samples=1105`, 마지막에는 discard padding이 있으나, pre-concatenated MP3의 내부 경계에서는 이 per-file side data가 사라진다. mp3float·AudioToolbox 측정에서 누락된 내부 trim은 17,327개의 all-zero sample, 즉 0.392902초의 비정본 timeline/gap을 만든다. 이 silent extra samples를 가청 spike의 직접 원인으로 단정하지 않는다. QuickTime output capture가 없어, 즉시 메커니즘은 long MOV+MP3 playback path에서 codec 문제인지 interleave/인접한 큰 H.264 keyframe 문제인지 미분리 상태다.

안전 계약은 두 위험을 함께 제거한다. 02는 승인된 standalone MP3 12개를 정확한 순서로 각자 gapless decode한 뒤 하나의 continuous AAC-LC로 만들고 MP4에 넣는다. 04·06은 각 standalone MP3를 AAC-LC로 transcode한다. 01·03·05의 승인 AAC-LC는 stream-copy한다.

후보 SKILL/QC 문서는 다음 세 문장을 정확히 보존해야 하며, 이에 모순되는 직접 인과 주장을 추가하면 실패한다.

> 17,327 all-zero samples prove a 0.392902-second noncanonical timeline defect; they are not the proven direct cause of the audible spike.
>
> Without QuickTime output capture, codec versus interleave/nearby H.264 keyframe contribution remains unresolved.
>
> The safe path removes both per-track MP3 trim metadata loss and MOV+MP3 playback risk.

`incident.json`은 이 세 문장과 함께 단어 순서가 다른 명시적 직접-인과 overclaim corpus도 잠근다. 채점기는 단순 어휘 순서가 아니라 이 exact incident contract를 검사하며, reviewer가 제공한 모순 문장을 문서 뒤에 붙이는 공격을 반드시 거부한다.

## 후보 인터페이스

후보 `skills/hymn-letter-video-production/scripts/hymn_video_flow_v3.py`는 다음 명령을 제공해야 한다.

```bash
python3 hymn_video_flow_v3.py verify-upload-ready \
  --manifest <upload-ready.json> \
  --authority-lock <authority-lock.json> \
  --ffprobe <ffprobe>
```

성공은 종료코드 0과 JSON `{"status":"ok","verified_sequences":[1,2,3,4,5,6]}`이다. 실패는 비정상 종료여야 하며 입력 fixture를 수정하면 안 된다.

## 실행

```bash
RUN_ROOT="$(bash setup.sh | tail -1)"
python3 "$RUN_ROOT/case/check-upload-ready.py" --self-test
python3 "$RUN_ROOT/case/check-upload-ready.py" \
  --candidate "$RUN_ROOT/repo/skills/hymn-letter-video-production"
```

## 합격선

- inventory 01–06, job schema, 문서와 `PROFILE_CONTRACTS`의 정확한 네 profile(start/playlist/testimony/hymn)이 모두 `.mp4`/MP4 + AAC-LC로 fail-closed여야 한다. `MOV+MP3 is forbidden`, `MOV+MP3 is not supported`, `Do not use MOV+MP3` 같은 금지문은 허용하지만 허용·지원 주장은 거부한다.
- 모든 final은 실제 probe에서 `format_name`에 MP4가 있고 allowlist major brand, H.264, AAC/LC여야 한다. 확장자 변경만 한 QuickTime+MP3 파일은 실패한다.
- 01·03·05 source도 실제 probe에서 각각 AAC/LC여야 하며 승인 payload를 stream-copy한다. payload tag가 같아도 codec 또는 profile이 틀리면 실패한다.
- 02는 authority에 잠긴 standalone MP3 12개 object의 SHA·순서·각 skip/discard·decoded PCM을 보존한다. 예전 단일 `02-approved-source.mp3`는 파생 입력으로 금지한다.
- 02의 정규화 명령은 video-only + track 01–12 입력, 각 `[i:a]asetpts=PTS-STARTPTS`, 정확한 `concat=n=12:v=0:a=1`, `-map 0:v -map [aout]`이어야 한다. `-c:v copy -c:a aac -profile:a aac_low -b:a 256k -ar 44100 -ac 2` 외에 `-af`, `-filter:a`, `-filter:a:0`, `-af:a:0`, 임의 stream specifier/동등 alias, `-shortest`, resample/volume/trim 등 다른 audio 처리를 허용하지 않는다.
- 02는 clean decoded total `120,930,048` samples, 제거된 내부 gap `17,327` samples, 82,266 video frames, 12개 track별 PCM boundary/tail PASS에 결박된다. track/order/skip/discard/decoded-PCM의 canonical JSON에 domain `plugify.hymn-letter.ordered-pcm-manifest/v1\0`를 붙여 SHA-256을 재계산한 값은 정확히 `dc3d9fd41fdf445d30e6da054fa42e0a33f5f23ba247522aa88248b38174e6cb`이어야 하며 authority·derivation·QC 모두 여기에 결박된다. 04·06도 같은 AAC-LC encode flag를 쓰되 filter graph 없이 개별 MP3에서 파생한다.
- 01–06 각 편의 승인 receipt는 source/derivative의 정확한 audio payload와 authority가 정한 reviewer/decision/reviewed_at에 exact-bound된다. timestamp는 유효한 canonical RFC3339 seconds여야 한다. valid-looking wrong decision·nonempty reviewer·canonical wrong time을 각각 바꾸는 공격, invalid date 공격, 세 값을 authority와 receipt에서 함께 `REJECTED`로 다시 묶는 공격도 모두 실패한다. authority는 각 편 identity/source object/video fingerprint/frame/caption/boundary/chapter를 묶는다. chapter가 없는 01/03/04/05/06도 field 생략이 아니라 authority와 QC 양쪽의 explicit `null`이 canonical 값이다.
- 01–06 각 편의 final QC는 actual file과 manifest·receipt·QC의 정확한 final SHA, actual probe, video/frame identity, caption/boundary/chapter authority, full decode, AVFoundation decode, 실시간 tail playback PASS에 결박된다.
- runner-owned HMAC probe broker만 실제 호출 증거를 메모리에 보관한다. 후보에는 secret이나 log path를 주지 않으며 fixture 변조도 감지한다.
- 무작위·불투명 경로와 순서로 만든 정확히 355개 독립 공격이 01–06 모두의 container/brand/codec/profile/video/frame/tail/approval 전 필드와 authority echo/identity/substantive lock/세 층 final SHA/full decode/AVFoundation/caption/boundary/chapter, 01/03/05 source codec/profile 및 non-applicable encoder, 02/04/06 derivation/source/encoder를 빠짐없이 변조한다. chapter explicit-null key 삭제, 02의 12개 track 각각에 대한 actual/source/authority/derivation/QC/composite full-rebinding, track order/priming/padding/boundary start/tail도 공격한다. 02/04/06의 정규화 encoder argv는 exact equality 계약이며 입력 순서, map 순서·값, output, required flag 중복, 임의 extra token, filter graph, 모든 flag 값을 편별로 공격한다. 정상 fixture는 통과하고 각 공격은 실패해야 한다.

fixture media는 저작물이나 가청 음원이 아닌 ffprobe-shaped 텍스트 표본이다. `incident.json`만 실제 관찰과 인과 한계를 보존한다.

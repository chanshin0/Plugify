# Review rubric

## 근거

- Adobe는 스토리보드를 대본을 시각적 순서로 풀고 패널에 장면·대사·카메라·시간을 배치하는 도구로 설명한다. [What is a Storyboard?](https://www.adobe.com/in/products/firefly/discover/what-is-a-storyboard.html)
- Cohn과 Magliano는 시각 내러티브를 의미 있는 이미지의 순차 구조로 다룬다. [Visual Narrative Research](https://pmc.ncbi.nlm.nih.gov/articles/PMC9328199/)
- WCAG는 사전 녹화 동기 미디어의 자막, 텍스트 대비, 자동 움직임·점멸 제어 기준을 제공한다. [Captions](https://www.w3.org/WAI/WCAG20/Understanding/captions-prerecorded), [Contrast](https://www.w3.org/TR/wcag/#contrast-minimum), [Pause/Stop/Hide](https://www.w3.org/WAI/WCAG22/Understanding/pause-stop-hide.html), [Three Flashes](https://www.w3.org/TR/wcag/#three-flashes-or-below-threshold)
- 미국 저작권청의 2025년 AI 보고서는 생성 결과의 저작권성에서 사람의 표현적 결정과 통제를 구분한다. 이는 미국 저작권성 자료이며 모든 관할의 이용 적법성을 대신하지 않는다. [Copyright and AI, Part 2](https://www.copyright.gov/ai/Copyright-and-Artificial-Intelligence-Part-2-Copyrightability-Report.pdf)

## 1. 이야기와 사실성

- [ ] 모든 장면의 목적을 한 문장으로 말할 수 있다.
- [ ] 각 장면에 `FACT/MEMORY/SYMBOLIC/UNVERIFIED`가 있고 화면의 확실성이 그 유형과 맞다.
- [ ] 이미지가 대본에 없던 사건, 대화, 관계, 시간, 표정을 사실처럼 주장하지 않는다.
- [ ] `visual_interpretation`이 새로운 사실 명제가 되지 않는다.
- [ ] 실제 기록 사진이 아닌 장면을 기록 사진처럼 보이게 만들지 않는다.
- [ ] 마지막 장면이 대본에 없는 교훈 카드가 아니라 행동의 잔상으로 닫힌다.

## 2. 장면 문법

- [ ] 한 프레임에 주 초점과 서사 기능이 하나다.
- [ ] 내레이션을 글자로 그대로 반복하지 않고 보이는 증거를 제공한다.
- [ ] 같은 레이아웃·인용문·베이지 수채화가 기계적으로 반복되지 않는다.
- [ ] 장면 사이에 원인–결과 또는 시각적 앵커가 있다.
- [ ] 반복 인물의 외형·옷·소품, 반복 공간의 광원·방향이 유지된다.
- [ ] 얼굴·손·팔다리·소품·그림 속 생성 텍스트 오류가 없다.

## 3. 존엄성과 비모방

- [ ] 노년·장애·가난·신앙·가족애를 과장된 눈물과 수동적 표정으로 환원하지 않는다.
- [ ] 인물의 선택, 기술, 관계의 상호성을 적어도 한 장면에서 보여 준다.
- [ ] 특정 방송·작가·스튜디오·캐릭터·로고의 식별 가능한 고유 요소를 복제하지 않는다.
- [ ] 방송 스틸·웹 이미지·무권리 사진을 생성 입력이나 최종 프레임으로 사용하지 않는다.
- [ ] `generation_inputs.named_styles`가 비어 있고, 모든 reference image에 origin·권한·SHA-256·용도가 있다.
- [ ] 실제 사람·개인 장소·문서·표지판은 권한을 확인했거나 비식별화했다.

## 4. 자막과 대비

- [ ] 말, 화자 구분, 이해에 필요한 환경음이 `captions.vtt`에 있다.
- [ ] 실제 속도로 읽어 줄바꿈과 표시 시간이 충분하다.
- [ ] 일반 자막은 배경과 최소 4.5:1, 큰 글자는 최소 3:1 대비를 충족한다.
- [ ] 자막 안전 영역이 얼굴, 손, 핵심 행동, 화면 가장자리와 겹치지 않는다.
- [ ] 음소거 상태에서도 자막과 화면으로 이야기의 핵심을 따라갈 수 있다.

## 5. 움직임과 재생

- [ ] 모든 움직임에 서사 목적이 기록되어 있다.
- [ ] 한 장면에 카메라/요소 움직임이 하나를 넘지 않는다.
- [ ] 화면 전체 플래시, 빠른 흔들림, 짧은 방향 반전, 초당 3회 이상 점멸이 없다.
- [ ] 자동 움직임이 5초를 넘는 preview에는 일시정지가 있다.
- [ ] `prefers-reduced-motion`에서 정지 장면으로 같은 정보를 전달한다.
- [ ] 장면 길이는 자막과 내레이션을 실제로 읽고 전환 여유를 포함해 정했다.

## 6. 출처와 제작 장부

- [ ] 모든 장면에 `source_type`, 권리/허용, 도구, 프롬프트 버전, 사람 편집이 기록되어 있다.
- [ ] 참고 자료와 최종 사용 자산을 구분한다.
- [ ] 공개물에 AI 생성·재현·상징 표기가 필요한지 검토했다.
- [ ] 법적 판단이 필요한 권리 사례는 관할권 전문가 검토로 넘겼다.

## 7. 파일 실상태

- [ ] `deck.json` 장면 수와 `frames/*.png` 수가 일치한다.
- [ ] 장면 번호가 `01`부터 연속이고 파일명 번호와 일치한다.
- [ ] 모든 프레임이 16:9이며 흐림·잘림·레터박스가 없다.
- [ ] `validate_deck.py --stage render`가 0으로 끝난다.
- [ ] `build_preview.py`를 다시 실행해도 수동 수정이 사라지지 않는 SSOT 구조다.
- [ ] 첫 장면·전환점·마지막 장면을 원본 크기로 직접 확인했다.
- [ ] 이미지 도구가 없었다면 `production_status=visuals-pending`이고 `build_preview.py --storyboard-only`가 프레임 없이 통과했으며, `preview.html` 완성을 주장하지 않았다.

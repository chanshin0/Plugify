# 요청 계약 — 찬송편지 v3 결정적 재현

- 날짜: 2026-08-22
- 사용자 결과: 수정된 12곡 제목 순서를 포함한 찬송편지 1–6편을 임시 경로나 제작 세션에 의존하지 않고, 추적된 스킬과 콘텐츠 해시 잠금만으로 다시 만들고 검증할 수 있다.

## Discoverable

- 현 검토본의 실 렌더러·QC·SRT·폰트·음원 연결은 `/tmp`, `/Users/admin`, Google Drive 절대경로에 남아 있고 Git에는 없다.
- 현 스킬은 `hymn-letter-visual-v2`, WSL 경로, 3개 episode만 지원하며 render/QC 명령과 `.mov` 출력 계약이 없다.
- 현재 Mac에서는 동일 런타임으로 raster와 대표 H.264를 재생성할 수 있지만, 다른 기기에서 bit-identical임을 증명할 환경 잠금과 명령 영수증이 없다.
- 12곡 제목 오류는 각 곡의 제목을 intro와 outro 양쪽에 넣은 timeline 정책 때문에 발생했다. 수정 정책은 1번을 시작에 한 번, 2–12번을 직전 곡의 outro에 한 번씩 넣는 것이다.

## Assumable

- 역사적 v2 코드는 덮어쓰지 않고 v3 릴리스로 추가한다.
- 대용량 미디어는 Git에 넣지 않는다. 외부 source root의 `objects/sha256/<prefix>/<digest-rest>`에서 byte hash로만 찾는다.
- `semantic-equivalent`와 `reference-bit-exact`를 별도 게이트로 둔다. 환경이 다르면 bit-exact는 `NOT_APPLICABLE`이고 semantic PASS로 둔갑시키지 않는다.
- `/tmp`와 `/var`의 macOS 시스템 alias는 trusted root 정규화로 허용하되, root 내부 symlink escape는 거부한다.
- 이번 수용 기준의 02 golden은 제목 수정본 SHA-256 `f8171851110de1f23d739bd3e126b02ab82304028822bda9482f73cd90f7a239`다.

## Human context

- 중년층 가독성을 위해 01 인터뷰와 03–06 자막은 하단 중앙, 02처럼 목록이 큰 화면은 우하단 dense 스타일을 유지한다.
- 02의 현재 재생 행은 노란색이며, 다음 곡 제목 카드는 직전 곡의 연주 tail에서 나타나야 한다.
- 사용자는 먼저 02 제목 순서 오류를 수정하고, 그 결과를 재현 가능한 스킬에 반영하라고 지시했다.

## Approval

- `godowon-office`와 `Plugify`의 코드·schema·문서·테스트·release lock 작성, 로컬 content-addressed source bundle 구성, 검증, commit 및 origin push는 요청 범위다.
- 기존 검토본이나 원본 미디어의 삭제·덮어쓰기, 외부 업로드·공개, 권리 상태 변경은 승인되지 않았다.

## 실행 그래프

1. 수정된 02 렌더를 독립적으로 검수하고 별도 검토 폴더에 고정한다.
2. `godowon-office`에 v3 caption/profile/container/QC 모듈과 1–6 job/release/source/environment/golden lock을 추적한다.
3. `Plugify` 스킬에 portable object resolver, 6편 inventory, validate/render/qc/verify-source-bundle 명령과 schema v2를 추가한다.
4. synthetic 단위 테스트와 실제 02 source bundle 통합 검증을 실행한다.
5. 격리 리뷰 후 두 저장소를 commit하고 origin에 push한다.

## 완료 증거

- 수정된 02에서 제목 카드가 실제 H.264 프레임 기준 `1→12`로 정확히 한 번씩 나오고, 82,278 frames·104,990 audio packets·12 chapters가 보존된다.
- 새 패키지는 exact-set checksum 검증을 통과하며 기존 패키지를 변경하지 않는다.
- fresh temporary root의 synthetic bundle에서 6 profile/schema/path/security 테스트가 통과한다.
- 실제 02 job은 tracked renderer와 content-addressed objects만으로 render receipt와 semantic QC receipt를 생성한다.
- reference 환경이 정확히 일치할 때만 output SHA를 corrected golden과 비교한다.
- build/QC receipt가 source/release/job/code/environment/normalized command/output SHA를 결박한다.

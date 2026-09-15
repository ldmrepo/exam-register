# 변경 기록

## 1.1.0

시뮬레이션 문항을 더했다 — 답이 보기 중 하나도 글자 하나도 아니고 **조작 결과의 상태**인 유형이다.

- `references/simulation-rules.md` 신설: 역할 경계, 자족 HTML 형식과 서버의 갈래 판정(루트가 `<svg>` 가 아닌 HTML), 서빙 CSP 가 막는 것, `postMessage` 규약과 문서 뼈대, 값이 사는 자리 넷(`config` · `seed` · `initial` · 정답), 적합성 요건 12개와 **누가 무엇을 확인하는가**(편집기 핸드셰이크는 1·2·3·6·10, 요건 12 는 검사 불가, 4·9·12 는 저자), 호출 순서, 오류 복구.
- `scripts/check_simulation.py` 신설: 자산 파일의 해시·바이트·서버 상한, 루트 요소 판정, 외부 참조와 네트워크 호출, 규약 문자열 10개, `config` · `initial` · 정답의 JSON 여부와 16KB 상한, **정답과 출발 상태가 같은 경우**, **정답이 `config` 안에 들어 있는 경우**, `verified` 에 필요한 적합성 기록.
- 명세 스키마: `interaction` · `semantic_type` · `representation` 에 `simulation`, 최상위 `simulation` 블록(자산 · `alt` · `config` · `seed` · `initial` · 크기 · 정렬 · `conformance`). `check_manifest` 가 상호작용과 블록의 앞뒤, 선택지 없음, 대표 요소 하나, 자산 파일, 정답 개수를 본다.
- `references/teamsword-mcp.md` 에 호출 순서와 범위(`item.simulation.set` · `item.answer.simulation.set`, `src` 가 정답·`initial` 을 지운다), `element-rules` 에 판별 기준, `verification` 에 조작 확인.
- 사례 추가: `examples/simulation-balance/` — 지레 균형. 손으로 쓴 자족 HTML 과 명세, 판단 근거.
- 시험 17개(기존 14 + 3): 자산 형식·자족성, 규약 문자열과 값 앞뒤, 상호작용·상태 정합.

## 1.0.3

문서만 변경. MCP **연결** 절차를 추가했다(`references/mcp-setup.md`) — 엔드포인트 `/api/v1/mcp` 경로 규칙, Streamable HTTP, `Authorization: Bearer twk_…`, API 키 발급 경로, Codex · Claude Code · Claude Desktop 설정 예, Windows 함정 셋(`npx` 대신 전체 경로, 헤더 값의 공백, `--allow-http`), `teamsword_ping` 기대 응답과 판별 기준 셋, 키가 호스트 설정 파일에 평문으로 남는다는 사실과 폐기 절차. `config/mcp.example.json` 을 자리표시자에서 실제 스키마 예시로 교체했다. README · SKILL · `teamsword-mcp.md` · `install.ps1` 이 이 문서를 가리킨다. 종전에는 확인 방법(`teamsword_ping`)만 있고 연결 방법이 없었다.

## 1.0.2

도구 3개 추가: `record_call.py`(MCP 요청·응답 원자 기록, 마스킹, operation 상태), `prepare_registration.py`(등록 전 상태·검사·의도 게이트), `check_readback.py`(저장본 html ↔ 명세 대조). 검사 강화: 자산 바이트 크기·서버 상한, visual 통과에 캡처 파일 필수, run 의 operation 기록 파일 검사. 명세: `asset.bytes` 필수, `elements[].viewbox_title` 선택, `operations[].request/response`. 문서: 오류 코드 복구 표, 마크 목록, 긴 선택지 경로, 안정 id 시점, 삭제 불가, 표 절차, 첫 배치 dryRun. `check_manifest` 검사 함수 분리, 모든 출력 LF.

## 1.0.1

문서만 변경. 공통 지문을 별도 `general_document` 로 분리하는 규칙, 원본 문단별 들여쓰기·정렬 보존 규칙, 문단 서식·구간 대괄호·언어 블록 MCP 명령 안내, 1.0.0 태그 이후 실측(한국사 1~5 · 국어 1~3)을 반영한 VALIDATION. 패키지 생성기는 JSON 계약만 생성하고 문서는 직접 관리한다.

## 1.0.0

MCP 중심 순차 등록, 요소별 표현 명세, 원본 해시 기반 렌더링 캐시, 좌표 크롭, 검증 분리, 설치·백업·재개 지원. 기존 브라우저 병렬 전용 절차를 대체한다.

# 변경 기록

## 1.0.3

문서만 변경. MCP **연결** 절차를 추가했다(`references/mcp-setup.md`) — 엔드포인트 `/api/v1/mcp` 경로 규칙, Streamable HTTP, `Authorization: Bearer twk_…`, API 키 발급 경로, Codex · Claude Code · Claude Desktop 설정 예, Windows 함정 셋(`npx` 대신 전체 경로, 헤더 값의 공백, `--allow-http`), `teamsword_ping` 기대 응답과 판별 기준 셋, 키가 호스트 설정 파일에 평문으로 남는다는 사실과 폐기 절차. `config/mcp.example.json` 을 자리표시자에서 실제 스키마 예시로 교체했다. README · SKILL · `teamsword-mcp.md` · `install.ps1` 이 이 문서를 가리킨다. 종전에는 확인 방법(`teamsword_ping`)만 있고 연결 방법이 없었다.

## 1.0.2

도구 3개 추가: `record_call.py`(MCP 요청·응답 원자 기록, 마스킹, operation 상태), `prepare_registration.py`(등록 전 상태·검사·의도 게이트), `check_readback.py`(저장본 html ↔ 명세 대조). 검사 강화: 자산 바이트 크기·서버 상한, visual 통과에 캡처 파일 필수, run 의 operation 기록 파일 검사. 명세: `asset.bytes` 필수, `elements[].viewbox_title` 선택, `operations[].request/response`. 문서: 오류 코드 복구 표, 마크 목록, 긴 선택지 경로, 안정 id 시점, 삭제 불가, 표 절차, 첫 배치 dryRun. `check_manifest` 검사 함수 분리, 모든 출력 LF.

## 1.0.1

문서만 변경. 공통 지문을 별도 `general_document` 로 분리하는 규칙, 원본 문단별 들여쓰기·정렬 보존 규칙, 문단 서식·구간 대괄호·언어 블록 MCP 명령 안내, 1.0.0 태그 이후 실측(한국사 1~5 · 국어 1~3)을 반영한 VALIDATION. 패키지 생성기는 JSON 계약만 생성하고 문서는 직접 관리한다.

## 1.0.0

MCP 중심 순차 등록, 요소별 표현 명세, 원본 해시 기반 렌더링 캐시, 좌표 크롭, 검증 분리, 설치·백업·재개 지원. 기존 브라우저 병렬 전용 절차를 대체한다.

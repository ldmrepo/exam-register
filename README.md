# 시험지 문항 추출·TeamsWord 등록

Codex 스킬과 Windows 보조 도구 패키지. AI는 원본을 시각 판독하고, Python은 렌더링·확정 좌표 크롭·파일 검사만 수행한다. 별도 모델·서버 없이 TeamsWord MCP를 사용한다.

## 설치

Python 3.10 이상과 Codex, TeamsWord MCP 접근이 필요하다. MCP 는 `POST http://<host>:<port>/api/v1/mcp` 에 `Authorization: Bearer twk_…` 로 붙는다. 호스트별 설정과 함정은 [연결 절차](skills/exam-register/references/mcp-setup.md)에 있다. 저작 화면에서 API 키를 먼저 발급한다. GitHub 저장소를 가져온 뒤 실행한다.
```powershell
pwsh -File skills/exam-register/install.ps1 -Workspace D:/exam-workspace -SkillHome "$env:USERPROFILE/.codex/skills"
```
설치기는 스킬의 하위 파일을 모두 복사하고 작업 폴더의 `.venv`에 고정 버전 의존성을 설치한다. 기존 동명 스킬은 `SkillHome/.backups`에 보관한다. 로컬 설정과 실행 자료는 덮어쓰지 않는다. `-SkipDependencies`는 이미 의존성이 설치된 검증 환경용이다. 명령 실행만으로 MCP 설정이나 로그인이 활성화되지 않는다. 호스트 설정은 별도로 하고 `teamsword_ping` 으로 확인한다.

Codex에 저장소 주소와 `skills/exam-register` 경로를 제공하여 스킬 설치를 요청할 수도 있다. 스킬 파일 설치 후에도 위 의존성·작업 폴더 초기화가 필요하다. 다음 턴에서 `$exam-register` 인식을 확인한다. 비공개 저장소는 접근 권한이 필요하다.

## 사용

작업 폴더에 inputs/cache/runs/config를 두고 원본 PDF를 inputs에 저장한다. Codex에 원본·대상 폴더·문항 범위를 알려 등록을 요청한다. 스킬은 원본 확인 → 요소 계획 → 추출 → 원본 대조 → MCP 등록 → 저장/화면 검증 순서로 진행한다.
보조 도구: `render_pdf`·`crop_image`(렌더·크롭), `check_manifest`(명세·파일·상태 검사), `check_simulation`(시뮬레이션 자산·값 검사), `prepare_registration`(등록 전 게이트), `record_call`(MCP 요청·응답 기록), `check_readback`(저장본 대조), `record_state`(상태 전이). `check_manifest.py` 통과는 원문 정확도를 보장하지 않는다.

답이 조작 결과의 상태인 문항은 시뮬레이션으로 등록한다 — 자족 HTML 한 파일을 `kind: simulation` 으로 올리고 컨테이너를 채운 뒤 정답을 지정한다. 계약 요건 12개와 절차는 [시뮬레이션 규칙](skills/exam-register/references/simulation-rules.md)에 있다. `check_simulation.py` 는 파일 형식·자족성·규약 문자열만 보며, 요건 1·2·4·9·12 는 편집기에 넣고 조작해야 확인된다. 이미지 자료는 전체 캡션·범례를 보존하고 자른 이미지를 열어 확인한다. 업로드 실패를 텍스트·표로 대체하지 않는다.

## 검증과 배포

`python -m unittest discover -s tests -v`로 캐시·좌표·손상·재개·검증 상태 불변 조건을 검사한다. `examples`의 자료는 이 패키지를 위해 작성한 창작 사례이며 실제 수능 문항이 아니다. 예시 자료는 CC0로 재사용할 수 있다. 실제 시험지·인증 정보·운영 결과는 배포에 포함하지 않는다.

MCP 연결 절차는 `skills/exam-register/references/mcp-setup.md`, 현재 세션에서 관찰한 MCP 지원과 제한은 `skills/exam-register/references/teamsword-mcp.md`에 있다. 실제 화면을 확인할 수 없으면 verified로 보고하지 않는다. 실제 완료 범위는 [VALIDATION.md](VALIDATION.md)를 참조한다.

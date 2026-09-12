---
name: exam-register
description: Visually extract exam PDF questions and register editable text and preserved source images through TeamsWord MCP. Use for exam registration, source comparison, and resuming recorded registrations.
metadata:
  version: "1.0.0"
---

# 시험지 문항 추출·TeamsWord 등록

Codex가 원본을 보고 문항 영역·유형·요소를 판단한다. 보조 스크립트는 렌더링·확정 좌표 자르기·무결성 검사·상태 저장만 수행한다. 로컬 모델이나 별도 에이전트 서버는 필요 없다. 기본은 순차 실행이다.

## 시작

- 일반 시험 등록과 MCP 기능 검증을 구분한다. 기능 검증은 사용자가 지정한 표본·호출·재조회 범위로 수행하고, UI 검증 여부를 별도로 기록한다. 브라우저 편집 금지 등 사용자의 도구 제약을 따른다.
- 문서 유형과 내부 표현을 별도로 계획한다. 공통 지문은 기본적으로 별도 일반 리치에디터 문서(`general_document`), 문항은 `qti_item`으로 등록한다. 일반 문서 안에서도 원문의 머리글·보기박스를 보존한다. 상세 기준은 [요소 규칙](references/element-rules.md)을 따른다.

- 사용자 요청 범위와 작업 폴더의 기록부터 확인한다. 기존 문항 수정, 추가 사본, 재시도를 구분한다.
- 실행 데이터는 설치 스킬 밖의 작업 폴더에 둔다. `config/settings.local.json`과 `runs/<id>/manifest.json`을 사용한다.
- Python 환경은 `scripts/check_env.py --workspace <작업폴더>`로 점검한다. MCP는 `teamsword_ping` 및 필요한 그룹의 `teamsword_commands_guide`로 실제 확인한다.
- 기존 사용자가 지정한 브라우저 선호를 보존한다. 설정이 없으면 현재 연결된 도구를 확인한다. 화면을 볼 수 없으면 API 검사는 계속하고 시각 검증은 unavailable로 남긴다.

## 처리

1. 학년도·과목·형·문제지/정답지를 실제 원본에서 확인하고 출처·SHA256을 기록한다. 검색이 필요하면 공식 배포본을 우선한다. 미러는 출처와 미검증 범위를 밝힌다.
2. `scripts/render_pdf.py <pdf> --pages 1 2 --cache <작업폴더>/cache --scale 2`로 필요한 페이지만 렌더링한다. 전체 페이지를 열어 다단 읽기 순서와 문항 경계·공통 지문을 먼저 찾는다.
3. [요소 규칙](references/element-rules.md)으로 요소의 의미와 표현을 구분하고 [문항 템플릿](templates/question.json)에 영역·순서·판정 이유를 기록한다. 공통 지문 ID와 모든 연결 문항을 함께 기록한다.
4. 텍스트·수식을 원문대로 전사한다. 작은 부호가 불명확하면 PDF를 더 높은 배율로 다시 렌더한다. [이미지 규칙](references/image-rules.md)에 따라 자료 전체를 자르고 반드시 실제 크롭을 연다.
   문단별 첫 줄 들여쓰기의 유무·크기와 정렬을 원본 PDF에서 시각 판단한다. 첫 줄 1자 들여쓰기·양끝 정렬은 일괄 기본값이 아니며, 원문 근거나 해당 범위의 명시적 사용자 요청이 있을 때만 적용한다. 문단 역할별 판정과 불명확·미지원 처리 기준은 [요소 규칙](references/element-rules.md#문단-들여쓰기와-정렬)을 따른다.
5. `scripts/check_manifest.py <question.json> --workspace <작업폴더>`를 실행하고 원본과 전사·크롭을 시각 대조한다. 스크립트 통과를 내용 정확성으로 보고하지 않는다.
6. [MCP 등록·복구](references/teamsword-mcp.md)에 따라 검토 완료 문항을 생성·업로드·입력한다. 생성 의도와 반환 ID를 즉시 기록한다. 최신 버전이 필요한 쓰기는 순차 실행한다.
7. 저장 내용을 MCP로 재조회하고 실제 편집기 화면을 원본과 비교한다. [검증 기준](references/verification.md)에 따라 등록·구조·화면·정답·배점 상태를 분리한다.

## 중단과 재개

- 업로드 실패를 텍스트 보기·표 변환으로 대체하지 않는다. 실패 단계와 이유를 기록해 재개한다.
- 생성 응답이 불확실하면 새 문항을 만들기 전에 폴더 목록과 기존 ID를 조회해 중복을 해소한다. 해소할 수 없으면 blocked다.
- 상태는 planned → extracted → reviewed → registered → verified다. 오류는 needs_revision 또는 blocked와 resume_from으로 남긴다.
- `scripts/record_state.py`는 expected-revision을 검사하며 원자적으로 기록한다. 상태 전환 전 실제 증거를 기록한다. 한 문항에 쓰는 작업자는 한 명이다.
- verified에는 원본 대조·저장 구조·실제 화면 검증이 모두 필요하다. 지원되지 않는 필수 기능이나 화면 미확인은 완료로 숨기지 않는다.

## 참고와 설치

- 스키마: [question](schemas/question.schema.json), [run](schemas/run.schema.json). 모든 파일 경로는 작업 폴더 기준 상대 경로다. 페이지 1부터, bbox는 렌더 이미지 픽셀 좌표다.
- 사례: [이미지 자료](examples/image-stimulus/decision.md), [텍스트 보기](examples/text-viewbox/decision.md), [연표](examples/timeline-image/decision.md), [복합 편지](examples/composite-letter/decision.md).
- 신규 설치·업데이트: `install.ps1 -Workspace <작업폴더> -SkillHome <Codex 스킬 경로>`. 기존 동명 스킬은 전체 백업 후 교체하고 작업 데이터·설정은 보존한다. 설치 후 다음 턴에서 스킬 인식을 확인한다.

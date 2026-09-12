# 1.0.2 검증 범위

2026-09-12, Windows / Python 3.11.5. 1.0.2 는 도구 3개 추가와 검사 강화이며 **재실측은 하지 않았다** — 아래 실측 표는 1.0.1 시점 기록이다.

## 로컬 도구 (1.0.2 에서 시험만 수행)

- 테스트 14개 통과(1.0.1 의 6개 + 8개): 렌더 캐시·손상 복구, 범위 오류, 상태/리비전 충돌, 경로 이탈, 크롭 픽셀 대조, **자산 바이트 크기·서버 상한**, **record_call 의 intent→succeeded/failed/uncertain 과 마스킹·순번**, **prepare_registration 게이트 5조건**, **visual 캡처 파일 요구**, **check_readback 일치·순서·정답·밑줄·제목·assetId 판정**, **check_run 중복·응답 누락**.
- `build_exam_package.py` 재실행 후 JSON 계약 diff 0. 창작 예시 4종 `check_manifest` 통과.
- 새 도구는 실제 MCP 응답이 아니라 창작 fixture(`tests/fixtures`) 로만 검증했다. 실측 run 에 적용한 결과는 아직 없다.

## 실제 TeamsWord MCP 등록 (1.0.1 시점, 재실측 없음)

| 표본 | 범위 | 저장 구조 재조회 | 실제 편집기 화면 | 최종 상태 |
|---|---|---|---|---|
| 창작 예시 4종 | 지도·텍스트 보기·연표·편지 | 통과, 이미지 3개 asset_read 바이트 동일 | 미확인(iab 없음) | registered |
| 2026 수능 한국사 홀수형 1~5 | 이미지 자료 4, 텍스트 보기 1 | 통과, 이미지 4개 바이트 동일, 정답 5개 | Chrome 대조 통과(보기 기본 제목 제거 1건) | 1·2·4 verified, 3·5 registered |
| 2026 수능 국어 홀수형 1~3 + 공통 지문 | 텍스트만, 이미지 없음 | 통과, 정답 3개, 테두리·밑줄 확인 | Chrome 대조 통과 | 1·2 verified, 3 registered |

- 오래된 expectedVersion 쓰기 dryRun 은 DOCUMENT_VERSION_CONFLICT 로 거부. 잘못된 이미지 바이트는 UNSUPPORTED_IMAGE_TYPE 으로 거부.
- 국어 공통 지문은 별도 `general_document` 로 분리했고 1~3번 본문에서 제거했다. 네이티브 공유 연결은 아니다.
- registered 에 머문 이유는 하나다: `[3점]` 숫자 배점을 `item.scoring.set` 이 받지 않는다.
- 위 실측의 visual=passed 는 화면 캡처 파일 없이 대화 안 관찰로 판정한 것이다. 1.0.2 의 `check_manifest` 기준으로는 캡처 파일이 없어 passed 가 되지 않는다 — 다음 실측부터 적용된다.

## 백엔드 변경 (105 배포됨, 2026-09-12)

- `content.insert.viewbox {headText: ""}` 가 제목 없는 보기박스를 만든다(#1598/PR #1599).
- `item.choice.populate` 선택지 2000자(#1600/PR #1601).
- 스킬 문서는 이 배포본 기준이며, 옛 서버 판별법(`commands_guide` 스키마)을 함께 적었다. 두 변경의 MCP 실측은 아직 없다.

## 미완료

- 새 도구 3개(`record_call` · `prepare_registration` · `check_readback`)의 실측 적용.
- GitHub 주소 기반 설치 재현, 새 턴의 스킬 인식 확인.
- 숫자 배점(문항 모델에 자리 없음 — 설계 결정 대기), 공유 지문 네이티브 연결(MCP 미지원).
- 독립적인 사람 검수·블라인드 평가 없음. 이미지 크롭 정확도 근거는 한국사 표본 4개뿐이다.

# TeamsWord MCP 등록·복구

2026-09-12 실제 guide 점검. 현재 세션의 명령 스키마가 우선이다. 설정 예시만으로 MCP 연결이 활성화되지 않는다. 환경 키를 문서·로그에 저장하지 않는다.

1. teamsword_ping → 필요한 group의 teamsword_commands_guide. 도구 노출과 인증 성공을 구분한다.
2. 대상 폴더를 set_list로 조회하거나 사용자 범위 안에서 set_create. 반환 set ID를 manifest에 저장한다.
3. 생성 전 고유 operation_key와 intent를 원자 저장한다. item_create {type:qti_item,title,interaction,setId} 후 document ID를 즉시 기록한다. ID가 있는 재시도는 read부터 시작한다. 생성 응답 손실 시 목록·제목·내용으로 확인하기 전 자동 재생성하지 않는다.
4. item_read의 version을 해당 쓰기의 expectedVersion으로 사용한다. 버전 충돌 때 최신 내용을 읽고 사용자의 변경을 보존한 새 연산만 준비한다. 중간 연산 실패는 일부 적용 가능성이 있어 전체 배치를 맹목적으로 재전송하지 않는다.

   새 빈 문서는 version=null일 수 있다. 그 문서가 방금 생성한 빈 대상임을 확인한 첫 쓰기에만 expectedVersion을 생략한다. null을 전달하면 입력 검증에 실패한다. 본문이 있는 이후 쓰기는 새 read의 문자열 버전을 사용한다.
5. 질문은 item.prompt.set. 선택지는 정답 근거가 확인된 경우 item.choice.populate. 이는 모든 선택지를 교체하고 한 개 이상 correct:true가 필요하다. 정답 미확인이면 임의 정답을 넣지 말고 item.choice.add 등 실제 스키마에 맞는 별도 경로를 사용한다. populate의 선택지 텍스트는 최대 200자다. 긴 선택지·수식·강조는 별도 편집 경로의 지원을 확인한다.
6. 그림은 asset_upload {documentId,dataBase64,filename,contentType} → 반환 assetId/url 기록 → edit_text의 content.insert.image {position:document_end,imageUrl,alt,naturalWidth,naturalHeight}. data URI를 imageUrl로 보내지 않는다. 이 두 단계는 별개다. 원본 파일과 재조회 파일을 바이트 해시 또는 서버 변환 시 픽셀·실제 화면으로 비교한다.
7. content.insert.viewbox는 보기 상자 생성, content.insert.text는 본문 입력, content.insert.math는 LaTeX 입력이다. 커서·앵커로 정확한 삽입 위치를 지정하고 결과 구조를 읽는다. Markdown이나 HTML이 자동 해석된다고 가정하지 않는다.

   실측 경로: 질문 문단의 blockId를 read에서 얻어 cursor.move.block {blockId,target:end} → content.insert.image {position:cursor,...}로 질문 뒤·선택지 앞에 넣었다. 일반 보기는 같은 위치에서 content.insert.viewbox → content.insert.text {position:cursor,text}로 채웠다. 밑줄은 item_find로 유일한 문자열을 확인한 뒤 format.apply.mark {mark:underline,target:selection}과 연산 target.text를 사용한다.
8. item.scoring.set은 현재 checkType(AND/OR), maxChoices만 지원한다. 2점·3점 같은 숫자 배점 필드가 아니다. 적용하지 못한 필수 배점은 unsupported로 기록한다.
9. item_read(html/outline/json/qti)의 지원 범위 안에서 저장 내용을 재조회한다. asset_read로 이미지 파일을 확인한다. 실제 UI는 별도로 검증한다. HTML이 미리보기용이라는 이유로 화면을 봤다고 보고하지 않는다.

## 별도 일반 지문 문서 입력

`item_create {type:general_document,setId,title}`로 지문을 만든다. 박스 밖 안내 머리글을 일반 문단에 입력한 뒤 `content.insert.viewbox`와 `content.insert.text`로 원문의 박스 본문을 구성한다. 기존 내용 수정 시 먼저 최신 read를 저장하고 사용자 변경을 보존한다.

`content.insert.viewbox`의 `headText` 생략은 기본 `<보기>`를 생성한다. 제목 없는 원본은 생성 후 read에서 보기박스 ID를 얻어 `node.attrs.set {blockId,attrs:{headText:""}}`로 제목을 비운다. 현재 스키마와 dryRun으로 적용 가능성을 확인한다. 박스 밖 안내문, 박스 제목 유무, 내부 문단 및 서식을 재조회한다. 문서가 general_document라는 이유로 박스를 제거하지 않는다.

## 문단 서식·구간 대괄호·언어 블록 (2026-09-12 배포본 기준)

`target` 은 `current_block`(커서가 있는 블록) 또는 `selection`(선택이 닿은 모든 블록)이다. 대상 블록으로 이동하려면 read 의 blockId 로 `cursor.move.block` 을 먼저 실행하거나 `selection.select.block` 으로 선택한다. 적용 후 read 의 문단 속성으로 확인한다.

| 원본 서식 | 명령 | payload | 비고 |
|---|---|---|---|
| 문단 정렬(왼쪽·가운데·오른쪽·양끝) | `format.paragraph.align` | `{align: left\|center\|right\|justify, target}` | 출처 오른쪽 정렬, 본문 양끝 정렬 등 |
| 문단 전체 들여쓰기 | `format.paragraph.indent` | `{direction: increase\|decrease, count?, target}` | 단계 단위(1단계 18pt). 임의 pt 지정이 아니다 |
| 내어쓰기(둘째 줄부터 들여쓰기) | `format.paragraph.hanging_indent` | `{pt: 0<pt≤504, target}` | 첫 줄은 그대로, `(가) …`·`응: …` 형태. 목록 안 문단은 거부 |
| 구간 대괄호 `[A]`·`(가)` | `content.wrap.range_bracket` | `{target, side: left\|right, label: ""≤20자}` | 문단 단위. 이미 대괄호 안이면 side·label 만 변경(중첩 없음). 경계 가로지르는 선택은 거부. 해제는 `node.unwrap` |
| 영어·일본어 등 언어 블록 | `content.wrap.language_block` | `{target, language: english\|korean\|japanese\|chinese\|french\|german\|dutch\|vietnamese\|indonesia\|thai}` | 안이면 언어만 변경. 해제는 `node.unwrap` |

첫 줄 들여쓰기·오른쪽 여백·줄 간격·문단 위아래 여백은 위 `format.*` 명령에 없고 **`node.attrs.set {blockId, attrs}`**(edit_structure)로 놓는다. read 의 outline 에서 문단 blockId 를 얻어 한 번에 여러 속성을 정확한 값으로 지정할 수 있다.

| 속성 | 값 | 뜻 |
|---|---|---|
| `textIndent` | `"<pt>pt"` | 첫 줄 상대 오프셋. 양수 = 첫 줄 들여쓰기(예 1자 ≈ 글자 크기 pt), 음수 = 내어쓰기 |
| `indent` · `leftIndent` | 정수 레벨(레벨당 18pt) · `"<pt>pt"` | 왼쪽 여백. 18pt 격자 밖 값은 `leftIndent` 를 쓰되 `round(pt/18) === indent` 가 되도록 둘을 함께 놓는다 |
| `rightIndent` | `"<pt>pt"` | 오른쪽 여백 |
| `align` | `left` · `center` · `right` · `justify` | `format.paragraph.align` 과 같은 값 |
| `lineSpacing` | `"1"` · `"1.15"` · `"1.5"` · `"2"` | 줄 간격 |
| `paddingTop` · `paddingBottom` | `"6pt"` 같은 CSS 길이 | 문단 안쪽 위아래 여백 |
| `leaderMark` | `"㉠"` 같은 글자 | 문단 끝에서 오른쪽 끝까지 점선 리더와 끝 글자 |

예: 본문 첫 줄 1자(11pt 글자) 들여쓰기 + 양끝 정렬 → `node.attrs.set {blockId, attrs: {textIndent: "11pt", align: "justify"}}`. 적용 뒤 read 의 `attrs` 로 확인한다. 위 표에 없는 서식은 현재 `teamsword_commands_guide` 의 `node.attrs.set` 스키마로 지원 여부를 확인하고, 없으면 미지원으로 기록한다. 공백 삽입으로 모사하지 않는다.

## 재개 기록

로컬 question.registration에 set_id, document_id, version, asset_ids, operation_key, creation_status를 둔다. manifest.operations는 intent/succeeded/failed/uncertain을 기록한다. 실패에서 재개 시 이미 성공한 업로드 ID와 문서 ID를 재사용한다. 사용자 요청인 추가 사본에는 새로운 operation_key를 부여한다.
스크립트는 원격 MCP를 직접 흉내 내지 않는다. Codex가 실제 연결된 MCP 도구를 호출하고 응답의 ID·버전·검증 근거를 저장한다.

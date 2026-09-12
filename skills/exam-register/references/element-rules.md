# 요소 계획

문항 번호·시작/끝·다단 순서·공통 자료를 확인한 뒤 요소마다 semantic_type, representation, reason을 기록한다. 원본에 없는 요소를 생성하지 않는다.

| 원본 | 의미 유형 | 표현 |
|---|---|---|
| 질문·선택지 | prompt / choice | 편집 가능한 text, 필요한 부분은 latex |
| 일반 지문·보기 | passage / viewbox | text, 원본 강조·문단 보존 |
| 지도·사진·비문·편지 | map / photo / image | 제목·설명·장식까지 하나의 image |
| 표 모양의 시각 자료·연표 | table / timeline | 원본 배치가 의미를 가지면 image |
| 순수 데이터 표 | table | 사용자가 편집 가능 표를 원하고 원본 재현이 가능하면 native_table |
| 수식·그래프 | formula / graph | 수식 latex, 그래프 image |

박스 유무나 PDF 내부 래스터 여부만으로 결정하지 않는다. 자료 안 텍스트를 편집 가능한 지문으로 임의 분리하지 않는다. 한국사 4번 같은 연표는 table/timeline + image 사례다.
공통 자료를 문항마다 중복 추출하지 않는다. TeamsWord의 공유 연결이 실제 지원되지 않으면 미지원으로 기록하고, 사용자 요청에 따라 사본 삽입 여부를 결정한다.
수식, 지수 부호, 한자·옛한글, 밑줄·사각 테두리는 확대 대조한다. 모르는 글자는 추측하지 말고 issues에 남긴다.

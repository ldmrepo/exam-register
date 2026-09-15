# 조작으로 답하는 사례 · 지레 균형

이 사례는 직접 작성한 CC0 자료다. 실제 수능 문제가 아니다.

interaction=simulation; semantic_type=simulation; representation=simulation. 답이 보기 중 하나도, 글자 하나도 아니고 **조작 결과의 상태**라서 시뮬레이션이다. 같은 내용을 「수평이 되는 거리는?」 으로 묻고 보기 다섯을 준다면 그것은 선다형이다.

## 값이 사는 자리

- `config` `{"m1":2,"x1":3,"m2":3}` — 화면에 이미 보이는 값뿐이다. 응시자가 읽는다.
- `initial` `{"d":5}` — 출발 자리. 정답과 다르므로 가만히 제출하면 틀린다.
- 정답 `{"d":2}` — 2 kg × 3 m = 3 kg × 2 m. `author` 모드에서 수평을 만든 뒤 시뮬레이션이 낸 문자열을 **바이트 그대로** 옮긴 것이다. `{ "d": 2 }` 로 다시 쓰면 다른 답이 된다.
- `seed` 없음 — 무작위가 없다.

## 자산

`simulation.html` 은 자족 HTML 한 파일이다. 외부 주소를 하나도 참조하지 않고(서빙 CSP 가 `default-src 'none'` 이다) 규약 문자열을 모두 갖췄다. `scripts/check_simulation.py` 로 그 두 가지를 기계 검사할 수 있다. 다만 **요건 4·9·12 는 돌려 봐야 안다** — 이 사례의 `conformance.author_checked` 가 빈 것은 그래서다.

source.png 와 question.json 을 원본 대조에 사용한다. 파일 경로는 스킬 폴더를 작업 루트로 해석한 예시다. 실제 작업에는 작업 폴더로 복사하고 경로를 맞춘다.

# 시뮬레이션 문항 제작·등록

응시자가 **조작**해서 답하는 문항이다. 조작 화면은 자족 HTML 한 파일이고, 서버 자산으로 올라가 문항 안의 컨테이너가 URL 로 참조한다. 계약 원본은 라이브러리의 `DOCS/simulation-container-contract.md` v1 이며, 이 문서는 스킬이 쓰는 요약과 절차다.

## 언제 이 유형인가

| 원본 | 유형 |
|---|---|
| 답이 보기 중 하나 | 선다형. 시뮬레이션이 아니다 |
| 답이 글자·수 하나 | 완성형 |
| 답이 **조작 결과의 상태**(균형점, 적정 부피, 충돌 뒤 결과) | 시뮬레이션 |
| 움직임을 보여 주기만 하고 답은 따로 고른다 | 선다형 + 이미지. 시뮬레이션을 쓰지 않는다 |

원본 시험지에 없는 조작을 스킬이 만들어 내지 않는다. 사용자가 시뮬레이션 문항을 **요청했을 때**, 또는 원본이 조작 결과 자체를 답으로 요구할 때만 이 경로다.

## 역할 경계

| 쪽 | 책임 |
|---|---|
| 호스트(편집기·응시 플레이어) | 발문, 액션 패널, 정답 저장, **채점**, 응답 보관, 레이아웃 |
| 시뮬레이션 | 조작 화면과 그 안의 논리. 값을 올리고 호스트의 지시를 따른다 |

시뮬레이션은 샌드박스 프레임 안에서 돈다. 호스트 DOM·쿠키에 닿지 못하고 호스트도 프레임 안을 읽지 않는다. 둘 사이는 `postMessage` 뿐이다.

**채점을 시뮬레이션 안에 넣지 않는다.** 자산은 응시 브라우저에 그대로 내려가므로 판정 로직도 정답도 응시자가 읽는다. 호스트가 저장된 정답 문자열과 응답 문자열을 비교한다.

## 문서 형식

| 항목 | 값 |
|---|---|
| 형식 | 자족 HTML 한 파일 (`text/html`) |
| 상한 | 서버 `ASSET_MAX_BYTES`, 기본 5,242,880바이트 |
| 업로드 | `teamsword_asset_upload {kind: "simulation"}` |
| 참조 | 서버가 돌려준 `/`-루트 상대 경로. data URI 는 거절된다 |

**서버는 바이트로 갈래를 판정한다.** 문서의 **루트 이름**(DOCTYPE 이름, 없으면 첫 요소)이 `svg` 면 이미지로, 아니면 시뮬레이션으로 본다. 루트가 `html` 이 아닐 때는 앞 4KB 안에 `<html|head|body|meta|script|style|title|link` 중 하나가 있어야 한다. 두 갈래는 **배타**다 — 이미지로 판정되는 바이트는 시뮬레이션 자리에 못 들어간다. 본문에 인라인 `<svg>` 를 그리는 것은 무방하다(루트가 아니므로).

**외부 네트워크를 쓰지 않는다.** 서빙 CSP 가 `default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; font-src data:` 라 외부 스크립트·스타일시트·이미지·글꼴·`fetch`·`XMLHttpRequest`·WebSocket 이 전부 차단된다. 라이브러리가 필요하면 파일 안에 **인라인**한다(5MB 안에서). CDN 주소를 적어 두면 화면이 조용히 비어 나온다.

## 핸드셰이크

모든 메시지는 `{ qtiSim: 1, type, … }` 다. `qtiSim` 이 없으면 양쪽 다 무시한다.

**호스트 → 시뮬레이션**

| type | 실리는 것 | 언제 |
|---|---|---|
| `init` | `{ contract, mode, config, seed, display?, initial?, response? }` | `ready` 직후 |
| `mode` | `{ mode }` | 모드 전환 |
| `response.set` | `{ value }` | 이어 풀기·검토 표시 |
| `response.get` | `{ requestId }` | 정답 지정·제출·저장 직전 |
| `reset` | `{}` | 다시 풀기 |

**시뮬레이션 → 호스트**

| type | 실리는 것 | 언제 |
|---|---|---|
| `ready` | `{ contract, capabilities?, a11y: { description } }` | 적재 완료 즉시 |
| `response` | `{ value, complete, requestId? }` | **값이 바뀔 때마다**, `response.get` 응답 |
| `height` | `{ px }` | 내용 높이가 바뀔 때 |
| `config` | `{ value, seed? }` | `author` 모드에서 설정이 바뀔 때 |
| `error` | `{ code, message }` | 스스로 복구 못 할 때 |

**모드 넷**: `author`(저자가 목표 상태를 만든다) · `practice`(피드백 허용, 채점 안 함) · `test`(단서를 감춘다) · `review`(읽기 전용). 모르는 모드는 `test` 로 취급한다.

**`init` 의 적용 순서는 `response` · `initial` · 기본값**이다. `reset` 은 자기 기본값이 아니라 `initial` 로 돌아간다.

뼈대는 이렇다. 표본 넷이 라이브러리 `apps/demo/public/simulations/` 에 있다.

```js
function send(type, extra) {
  var msg = { qtiSim: 1, type: type };
  for (var k in extra) if (Object.prototype.hasOwnProperty.call(extra, k)) msg[k] = extra[k];
  window.parent.postMessage(msg, '*');
}

window.addEventListener('message', function (e) {
  var msg = e.data;
  if (!msg || msg.qtiSim !== 1) return;
  if (msg.type === 'init') {
    applyDisplay(msg.display);                 // 선택 — 안 읽어도 문항은 성립한다
    if (typeof msg.seed === 'number') applySeed(msg.seed);
    readConfig(msg.config);
    if (msg.initial) initial = msg.initial;
    setMode(msg.mode);
    if (msg.response) setState(msg.response, false);   // response · initial · 기본값
    else setState(initial, false);
  } else if (msg.type === 'mode') {
    setMode(msg.mode);
  } else if (msg.type === 'response.set') {
    setState(msg.value, true);                 // 저장 시점 화면을 복원한다 (요건 12)
  } else if (msg.type === 'response.get') {
    send('response', { value: value(), complete: isComplete(), requestId: msg.requestId });
  } else if (msg.type === 'reset') {
    setState(initial, true);                   // 기본값이 아니라 저자가 정한 출발점
  }
});

if (window.ResizeObserver) new ResizeObserver(reportHeight).observe(document.body);

send('ready', { contract: 1, a11y: { description: '…화면을 글로 옮긴 설명…' } });
```

`setState` 의 둘째 인자는 「호스트에 알릴 것인가」 다 — `init` 적용은 알리지 않고, `response.set`·`reset` 은 **알린다**(요건 9).

## 값이 사는 자리 넷

| 값 | 어디에 | 누가 만드나 | 응시자가 읽나 |
|---|---|---|---|
| `config` | 컨테이너 속성 | 시뮬레이션이 `config` 메시지로 올린다 | **읽는다** |
| `seed` | 컨테이너 속성 | 시뮬레이션이 `config` 와 함께 올린다 | **읽는다** |
| `initial` | 컨테이너 속성 | 저자가 `author` 모드에서 만든 상태 | 읽는다 |
| 정답 | 정답 경로 | 저자가 `author` 모드에서 만든 상태 | 읽지 못한다 |

**`config` 에 정답 단서를 넣지 않는다.** 저장 HTML 에 그대로 나간다. 미지수(맞혀야 할 값)는 `seed` 에서 유도하고 `config` 에는 화면에 이미 보이는 것만 싣는다.

**무작위는 저작 때 한 번 굳는다.** 응시 중에 다시 뽑으면 응시자마다 상태가 달라져 저장된 정답이 성립하지 않는다.

**`src` 를 바꾸면 정답과 `initial` 이 지워진다.** 전제가 바뀌면 이전 값이 가리키던 상태가 없기 때문이다. 그래서 **자산을 먼저, 정답을 나중에** 넣는다. 같은 호출에 `src` 와 `initial` 을 함께 주면 비운 뒤 적용된다.

**정답과 초기값이 같으면 응시자가 아무것도 하지 않고 맞는다.** 편집기는 경고하지 않는다 — 저자 책임이다. 명세에 둘을 함께 적어 사람이 대조한다.

## 적합성 요건 12

1. 적재 후 **3초 안에** `ready` 를 보내고 `contract` 를 선언한다.
2. `response.get` 에 **1초 안에** 같은 `requestId` 로 답한다.
3. `value` 는 JSON 직렬화 가능하고 **16KB 이하**다.
4. **결정적**이다 — 같은 `config` · 같은 `seed` · 같은 조작이면 같은 `value` 다. 난수는 `seed` 에서만 나온다.
5. 모드 넷을 받아들인다. 모르는 모드는 `test` 로 취급한다.
6. `a11y.description` 에 텍스트 대체를 싣고 **키보드만으로 같은 조작**이 가능하다.
7. 외부 네트워크를 쓰지 않는다. 자족 문서다.
8. 높이가 바뀌면 `height` 를 보낸다.
9. **값이 바뀔 때마다** `response` 를 보낸다. `response.set`·`reset` 으로 바뀐 경우도 포함한다.
10. **직렬화를 고정한다** — 같은 상태면 같은 문자열. `{"d":2}` 와 `{ "d": 2 }` 는 다른 답이다.
11. `config` 에 정답 단서를 넣지 않는다.
12. `response.set` 으로 받은 값이 **저장 시점 화면을 복원**한다.

**편집기가 핸드셰이크 한 번으로 판정하는 것은 다섯이다** — 1 · 2 · 3 · 6 · 10. 나머지 일곱은 조작을 해 봐야 알 수 있는데 호스트는 값의 뜻을 모른다. **요건 12 는 편집기가 아예 검사할 수 없다**(방금 읽은 값을 돌려주고 다시 묻는 것은 공허하다 — `response.set` 을 통째로 무시하는 자산도 똑같이 통과한다).

그래서 **4 · 9 · 12 는 사람이 확인하는 자리**다. 패널의 「되돌리기」 를 눌러 화면이 저장 시점으로 돌아오는지 보고, 같은 조작을 두 번 해 같은 문자열이 나오는지 본다. 확인한 요건 번호를 명세의 `simulation.conformance.author_checked` 에 적는다.

요건 4·10 이 깨지면 **문항이 조용히 틀린다** — 응시자가 정확히 같은 상태를 만들어도 문자열이 달라 오답이 된다. 값을 만들 때 키 순서를 코드에 고정하고(객체 리터럴을 매번 같은 순서로 쓴다) 부동소수를 그대로 싣지 말고 자릿수를 고정한다.

## 등록 호출 순서

1. `teamsword_item_create {type: "qti_item", title, interaction: "simulationinteraction", setId}`
   — 컨테이너는 스키마가 요구해 **문서가 태어날 때 이미 있다**. 삽입할 것이 없다.
2. `item.prompt.set` — 발문.
3. `teamsword_asset_upload {documentId, dataBase64, filename, contentType: "text/html", kind: "simulation"}`
   — 돌려받은 `assetId` · `url` 을 기록한다.
4. `item.simulation.set {src: url, alt, width?, height?, align?, config?, seed?, initial?}`
   — `src` 는 3의 `url` 그대로. **이 호출이 정답과 `initial` 을 지운다.**
5. `item.answer.simulation.set {value}` — 시뮬레이션이 낸 JSON 문자열을 **바이트 그대로**.
6. `teamsword_item_read` 로 되읽어 `src` · `alt` · `config` · `seed` · `initial` · 정답을 대조한다.

`item.answer.set` 은 쓰지 않는다 — 시뮬레이션에는 선택지가 없다. 호출마다 `scripts/record_call.py` 로 요청·응답을 남기는 것은 다른 유형과 같다.

`item.simulation.set` 의 범위: `alt` ≤ 2000자, `config` ≤ 16KB, `seed` 정수, `width`·`height` 50~10000, `align` `left|center|right`, `initial` 은 1바이트 이상 16KB 이하의 **JSON 으로 읽히는 문자열**. 정답 `value` 도 같은 제약이다.

## 기계 검사

`scripts/check_simulation.py <question.json> --workspace <작업폴더>` 는 **파일과 명세만** 본다.

본다: 파일 존재·해시·바이트 크기와 서버 상한, 루트 이름이 `svg` 가 아닌 HTML 인지, 외부 주소 참조(`http(s)://`·`//호스트` 형태의 `src`·`href`)와 `fetch`·`XMLHttpRequest`·`WebSocket` 의 유무, 핸드셰이크 표식(`qtiSim` · `ready` · `response.get` · `requestId` · `response.set` · `reset` · `mode`)의 유무, `config`·`initial`·정답이 JSON 으로 읽히고 16KB 이하인지, 정답과 `initial` 이 **같은 문자열이 아닌지**, `alt` 가 비지 않았는지.

못 본다: 요건 1·2·4·9·12 전부(코드를 돌려 봐야 한다), 화면이 원본과 맞는지, 정답이 실제로 맞는 상태인지, 키보드 조작이 실제로 되는지. **이 스크립트 통과를 적합성 통과로 보고하지 않는다.** 편집기가 자산을 넣을 때 도는 핸드셰이크가 1·2·3·6·10 을 보고, 나머지는 사람이 본다.

## 검증

`source` 는 원본 ↔ 화면·발문, `structure` 는 명세 ↔ 저장값(되읽은 `src`·`alt`·`config`·`seed`·`initial`·정답), `visual` 은 실제 편집기 화면이다. 시뮬레이션은 여기에 **조작 확인**이 붙는다 — `author` 모드에서 정답 상태를 만들고, 「되돌리기」 로 복원되는지 보고, 같은 조작을 두 번 해 같은 값이 나오는지 본다. 화면 캡처를 `runs/<id>/verification/` 에 남긴다.

캡처 없이 `visual: passed` 로 올리지 않는다. 조작을 못 해 봤으면 `simulation.conformance.author_checked` 를 비우고 `notes` 에 그 사실을 적는다. **적합성 미확인은 `verified` 가 아니다.**

## 오류와 복구

| 상황 | 뜻 | 행동 |
|---|---|---|
| 업로드가 `INVALID_INPUT`, `allowed: ["text/html"]` | 바이트가 시뮬레이션으로 판정되지 않았다 | 루트가 `<svg>` 가 아닌지, HTML 표식이 앞 4KB 안에 있는지 확인한다. 이미지 MIME 을 붙여 다시 올리지 않는다 |
| 편집기에서 「응답 없음」 자리 표시 | 3초 안에 `ready` 가 없다 | 스크립트 오류로 `send('ready')` 에 닿지 못한 경우가 대부분이다. 문서 끝에서 보내고, 그 앞 코드에서 던지지 않게 한다 |
| 「지원하지 않는 판」 | `contract` 가 호스트보다 높다 | v1 은 `contract: 1` 이다 |
| 정답을 넣었는데 비어 있다 | `item.simulation.set {src}` 를 정답 **뒤에** 불렀다 | 자산 먼저, 정답 나중. 되읽어 확인한다 |
| `SCHEMA_MISMATCH` on `initial`·`value` | JSON 으로 안 읽히거나 16KB 초과 | 시뮬레이션이 낸 문자열을 그대로 쓴다. 손으로 고쳐 쓰지 않는다 |
| 자산 404 | 자산이 지워졌거나 URL 이 틀렸다 | 채점 대상에서 빠진다. 0점이 아니라 **오류**로 다룬다 |

`ASSET_STORAGE_UNWRITABLE` 은 이미지와 같다 — 재시도하지 않고 `blocked` 로 두고 보고한다. 업로드 실패를 이미지나 텍스트 설명으로 대체하지 않는다.

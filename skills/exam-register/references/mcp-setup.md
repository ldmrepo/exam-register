# TeamsWord MCP 연결

이 문서는 **붙이는 방법**이다. 붙은 뒤의 연산 순서·버전·자산 규칙은 [teamsword-mcp.md](teamsword-mcp.md) 에 있다. 설정 파일을 만드는 것만으로 연결이 활성화되지 않는다. 호스트를 다시 시작한 뒤 `teamsword_ping` 으로 실제 확인한다.

## 접속 사양

2026-09-14 서버 `teamsword-collab` 0.7.0 실측이다.

| 항목 | 값 |
| --- | --- |
| 엔드포인트 | `POST http://<host>:<port>/api/v1/mcp` |
| 전송 | Streamable HTTP, `protocolVersion` `2025-06-18` |
| 응답 | `content-type: text/event-stream` |
| 세션 | stateless — `mcp-session-id` 헤더 없음 |
| 인증 | `Authorization: Bearer twk_…` |
| 도구 | 16개 (`teamsword_ping`, `teamsword_commands_guide`, `item_*`, `set_*`, `asset_*`) |

**호스트 주소만으로는 `404` 다.** `/api/v1/mcp` 경로까지 적는다. 헤더가 없거나 키가 틀리면 `401` 이다. 포트는 백엔드 포트이며 저작 화면 포트와 다르다.

## API 키 발급

저작 화면에 로그인한 뒤 **설정 → API 키**에서 발급한다. 토큰(`twk_…`)은 발급 직후 한 번만 보이므로 그때 호스트 설정에 넣는다. 다시 볼 수 없고, 잃으면 새로 발급한다.

## 호스트 설정

키 자리에는 발급받은 값을 넣는다. 아래 예시의 `twk_…` 와 `<host>:<port>` 는 자리표시자다.

### Codex (`~/.codex/config.toml`)

```toml
[mcp_servers.teamsword]
url = "http://<host>:<port>/api/v1/mcp"

[mcp_servers.teamsword.http_headers]
Authorization = "Bearer twk_…"
```

### Claude Code

```bash
claude mcp add --transport http teamsword http://<host>:<port>/api/v1/mcp \
  --header "Authorization: Bearer twk_…"
```

`--scope user` 를 붙이지 않으면 **명령을 실행한 디렉터리에서 연 세션에만** 보인다. `--scope project` 는 키가 저장소 파일에 남으므로 쓰지 않는다.

### Claude Desktop

설정 파일(`%APPDATA%/Claude/claude_desktop_config.json`)은 **stdio 서버만** 받는다. 원격 HTTP 엔드포인트에 붙이려면 브리지를 끼운다.

```powershell
npm install -g mcp-remote
```

```json
{
  "mcpServers": {
    "teamsword": {
      "command": "C:\\Program Files\\nodejs\\node.exe",
      "args": [
        "C:\\Program Files\\nodejs\\node_modules\\mcp-remote\\dist\\proxy.js",
        "http://<host>:<port>/api/v1/mcp",
        "--allow-http",
        "--transport",
        "http-only",
        "--header",
        "Authorization:${AUTH_HEADER}"
      ],
      "env": { "AUTH_HEADER": "Bearer twk_…" }
    }
  }
}
```

## Windows 함정 셋

1. **`"command": "npx"` 는 실패한다.** Windows 의 `npx` 는 `.cmd` 래퍼라 셸 없이 spawn 되면 stdio 가 즉시 닫혀 호스트가 `retrying` · `Connection closed` 를 반복한다. 전역 설치한 뒤 `node.exe` 와 `proxy.js` 를 **전체 경로**로 지정한다.
2. **헤더 값에 공백을 두면 인자가 쪼개진다.** `--header "Authorization: Bearer twk_…"` 대신 `--header "Authorization:${AUTH_HEADER}"` 와 `env.AUTH_HEADER` 로 넘긴다.
3. **평문 HTTP 는 `--allow-http` 가 필수**다. `--transport http-only` 로 SSE 폴백 시도를 없앤다.

## 확인

호스트를 다시 시작한 뒤 `teamsword_ping` 을 부른다. 정상 응답은 다음 형태다.

```json
{ "pong": true, "userId": "<uuid>", "authKind": "api_key", "era": "legacy" }
```

판별 기준은 셋이다.

- **도구 목록에 16개가 보이는데 호출이 `401`** — 설정은 읽혔고 키가 틀렸거나 헤더 형식이 어긋났다.
- **도구 자체가 안 보인다** — 호스트가 서버를 못 띄웠다. 경로·전송·브리지 기동을 본다. Claude Code 는 `--scope` 범위를 함께 본다.
- **`authKind` 가 `api_key` 가 아니다** — 키가 아닌 다른 자격으로 붙었다. 이 스킬은 API 키 경로를 전제한다.

`teamsword_ping` 이 통과해도 **도구 노출과 인증 성공은 별개**다. 필요한 그룹의 `teamsword_commands_guide` 를 불러 그 세션의 명령 스키마를 확인한 뒤 등록을 시작한다. 서버 판(版)마다 스키마가 다르다.

## 키는 어디에 남나

등록하면 키는 **호스트 설정 파일에 평문으로** 저장된다.

| 호스트 | 파일 |
| --- | --- |
| Codex | `~/.codex/config.toml` |
| Claude Code | `~/.claude.json` |
| Claude Desktop | `%APPDATA%/Claude/claude_desktop_config.json` |

따라서 설정 파일을 저장소 커밋·백업·화면 공유 대상에서 제외한다. 이 스킬의 작업 폴더·manifest·보고서에는 키를 적지 않는다. 샜다고 판단되면 저작 화면에서 그 키를 지우고 새로 발급한다. 서버는 키 문자열을 되돌려 주지 않으므로 지우는 것이 유일한 차단이다.

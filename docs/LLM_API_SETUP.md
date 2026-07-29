# Test RationaleOps with your own LLM API

RationaleOps accepts any text model endpoint that implements the OpenAI **Chat
Completions** request and response shape. You normally switch providers by
editing four values in `.env`; no Python changes are required.

The compatibility target is the standard
[Create chat completion](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)
shape. Native JSON mode follows OpenAI's
[structured-output guidance](https://developers.openai.com/api/docs/guides/structured-outputs)
when a provider supports it, with a prompt-only fallback when it does not.

The recorded demo still works without an API key. A live interview sends the
visible SQL, DataHub evidence, and interview turns to the endpoint you choose.

## Five-minute judge path

Prerequisites: Python 3.11+, `uv`, Node.js 22.13+, and `npm`.

1. Install only the backend and dashboard dependencies. This also creates an
   ignored `.env` file when one does not already exist:

   ```bash
   make live-setup
   ```

2. Open `.env` and replace these four values with the values supplied by your
   provider:

   ```dotenv
   LLM_PROVIDER=My LLM
   LLM_API_KEY=your-real-key
   LLM_BASE_URL=https://your-provider.example/v1
   LLM_MODEL=your-chat-completions-model-id
   ```

   `LLM_BASE_URL` is the API root immediately before `/chat/completions`. Do not
   paste a dashboard URL or the full `/chat/completions` path.

3. Make one small, real API request before starting the UI:

   ```bash
   make llm-check
   ```

   Success looks like:

   ```text
   LLM check passed
   JSON transport: native
   Your API key was not printed or stored by this check.
   ```

   `JSON transport: prompt` is also a success. It means the endpoint rejected
   native JSON mode and RationaleOps automatically retried with portable prompt
   instructions. The check may use a small amount of provider credit.

4. Start the app:

   ```bash
   # Terminal 1
   uv run rationaleops-api

   # Terminal 2
   NEXT_PUBLIC_RATIONALEOPS_API_URL=http://127.0.0.1:8000 npm --prefix web run dev
   ```

   On macOS, after `make live-setup`, you can instead double-click
   `start-rationaleops.command` to start both processes.

5. Open <http://localhost:3000>, select a decision, and click **LIVE AGENT**.
   Enter an owner answer such as:

   > Finance added seven days because card settlements can arrive late; prepaid
   > accounts stay on 30 days.

   Click **ASK NEXT**. A new evidence-linked adaptive question, plus your
   provider and model name in the status message, proves the live path worked.

## Switch providers

Edit the same four `LLM_*` values, restart `rationaleops-api`, and rerun
`make llm-check`. The API key is loaded by the backend only; it is never put in
the browser bundle or returned by `/api/health`.

### OpenAI

Use a model enabled for Chat Completions in your OpenAI project:

```dotenv
LLM_PROVIDER=OpenAI
LLM_API_KEY=your-openai-api-key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=your-chat-completions-model-id
```

`OPENAI_API_KEY`, `OPENAI_BASE_URL`, and `OPENAI_MODEL` are accepted as
fallback names, although the provider-neutral `LLM_*` names are clearer when
you switch between services.

### DeepSeek

```dotenv
LLM_PROVIDER=DeepSeek
LLM_API_KEY=your-deepseek-api-key
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-v4-pro
LLM_REASONING_EFFORT=high
LLM_EXTRA_BODY_JSON={"thinking":{"type":"enabled"}}
```

Existing installations using `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`,
`DEEPSEEK_MODEL`, `DEEPSEEK_THINKING_ENABLED`, and
`DEEPSEEK_REASONING_EFFORT` remain supported.

### Another cloud gateway or hosted model

```dotenv
LLM_PROVIDER=Company gateway
LLM_API_KEY=your-gateway-key
LLM_BASE_URL=https://gateway.example.com/v1
LLM_MODEL=the-exact-model-id-returned-by-the-gateway
```

If the service calls itself OpenAI-compatible but does not implement
`POST /chat/completions`, place a compatible gateway in front of it or use a
model/API option that exposes Chat Completions.

### Local server without authentication

```dotenv
LLM_PROVIDER=Local model
LLM_API_KEY=not-required
LLM_BASE_URL=http://127.0.0.1:1234/v1
LLM_MODEL=the-model-name-exposed-by-your-local-server
```

The local server must already be running. `not-required` is a harmless value
for clients that require an API-key field even when the server ignores it.

## Compatibility controls

Most providers need only the four main values. Add these settings only when a
provider documents the corresponding feature:

| Setting | Use |
|---|---|
| `LLM_JSON_MODE=auto` | Default. Try native `json_object`, then retry without it on common unsupported-parameter errors. |
| `LLM_JSON_MODE=prompt` | Never send `response_format`; useful for minimal or older compatible servers. |
| `LLM_JSON_MODE=native` | Require native JSON mode and fail instead of falling back. |
| `LLM_REASONING_EFFORT=high` | Send `reasoning_effort`; omit it for models that do not support it. |
| `LLM_THINKING_ENABLED=true` | Send DeepSeek-style `thinking.type`; omit it for other providers. |
| `LLM_EXTRA_BODY_JSON={...}` | Merge documented vendor-specific fields into the request body. |
| `LLM_DEFAULT_HEADERS_JSON={...}` | Add required gateway headers. Values are never shown by health checks. |
| `LLM_DEFAULT_QUERY_JSON={...}` | Add provider-specific query parameters. |
| `LLM_MAX_TOKENS=1600` | Add an output limit. It is omitted by default for maximum compatibility. |
| `LLM_MAX_TOKENS_PARAM=max_completion_tokens` | Change the output-limit field from the default `max_tokens`. |
| `LLM_TIMEOUT_SECONDS=120` | Increase the request timeout for a slow local or reasoning model. |

RationaleOps sends no temperature by default. It validates every LLM response
against typed Pydantic models and retries one malformed interview response.
Provider reasoning content is neither displayed nor stored.

## Troubleshooting

| Symptom | Check |
|---|---|
| `Set LLM_API_KEY` | Replace the placeholder. For a no-auth local server, use `not-required`. |
| `Set LLM_MODEL` | Use the exact ID exposed to your key by the provider, not a product display name. |
| HTTP 401/403 | Confirm the key, project permissions, and any required custom headers. |
| HTTP 404 | Check the base URL and model. The base normally ends at `/v1`, not `/chat/completions`. |
| HTTP 429 | Check quota, credit, and rate limits with the provider. |
| `response_format` error | Keep `LLM_JSON_MODE=auto`, or force `LLM_JSON_MODE=prompt`. |
| `max_tokens` error | Remove `LLM_MAX_TOKENS`, or select `max_completion_tokens`. |
| Timeout | Raise `LLM_TIMEOUT_SECONDS` and confirm the model server is already running. |
| CLI passes but UI is recorded | Restart the API after editing `.env`, then start the dashboard with `NEXT_PUBLIC_RATIONALEOPS_API_URL`. |

For a secret-free configuration snapshot, open
<http://127.0.0.1:8000/api/health>. `configured: true` means the local values
are complete; `make llm-check` is the step that verifies authentication,
network access, the model ID, and usable JSON output.

## Security boundary

- `.env` and `.env.*` are ignored by Git; only `.env.example` is committed.
- Never paste an API key into the dashboard, screenshots, issues, fixtures, or
  demo recordings.
- `llm-check` prints provider, sanitized base URL, model, and result only.
- Interview content is sent to the provider configured in `.env`; use an
  approved provider for sensitive transcripts.

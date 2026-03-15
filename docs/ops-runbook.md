# Ops Runbook

## Purpose

This runbook provides fast incident triage guidance for CI/runtime failures using:

- structured runtime error taxonomy
- `--log-run-dir` artifacts (`request.json`, `response.json`, `error.json`)

It is intentionally short and focused on first-response actions.

## Quick Triage Flow

1. Reproduce with `--log-run-dir logs`.
2. Open the latest `logs/run-*/error.json`.
3. Identify `error.code`.
4. Apply the action from the matrix below.
5. Re-run with `--dry-run --print-effective-config` to validate config resolution.

## Error Code Matrix

| Error code | Probable cause | Immediate action |
| --- | --- | --- |
| `auth_error` | Missing/invalid API key, unauthorized provider account, bad auth scope. | Verify `AI_API_KEY` / `--api-key`, provider account permissions, and key validity. Rotate key if needed. |
| `rate_limit` | Provider quota exhausted or request burst too high. | Retry later, reduce request rate/concurrency, or upgrade provider quota. |
| `timeout` | Upstream latency or network slowness exceeded configured timeout. | Increase `--timeout`, check provider status, retry with smaller prompt/load. |
| `invalid_request` | Bad inputs/config (model, endpoint, payload shape, strict capability failure). | Run `--dry-run --print-effective-config`, verify endpoint/model/flags, and fix invalid arguments. |
| `network_error` | DNS/TLS/connectivity issues, connection reset/refused. | Check DNS/network/firewall/proxy settings, provider reachability, and TLS chain. |
| `provider_error` | Unclassified upstream/provider failure. | Inspect `error.message`, provider status page, and retry with minimal request for isolation. |

## CI Procedures (Fast Path)

### `invalid_request`

1. Confirm job inputs and environment variables.
2. Run local preflight:
   - `ai-prompt-runner --dry-run --print-effective-config --provider <provider>`
3. If strict mode is used, verify provider capability compatibility for all flags.

### `network_error`

1. Validate CI runner outbound connectivity.
2. Validate DNS resolution and HTTPS handshake to provider endpoint.
3. Re-run once to rule out transient network failures.

### `auth_error`

1. Confirm secret is present in CI and mapped to `AI_API_KEY`.
2. Confirm secret value is current (not expired/revoked).
3. Confirm account/project has permission for selected model/provider.

### `rate_limit`

1. Check quota and rate dashboards.
2. Reduce concurrency/retry pressure in CI.
3. Re-run after backoff window.

### `timeout`

1. Increase timeout (`--timeout`) in the failing job.
2. Reduce request size where applicable.
3. Retry to separate transient latency from systematic issues.

### `provider_error`

1. Capture `error.json` and provider status context.
2. Re-run with minimal prompt to isolate request-level vs platform-level failure.
3. Escalate with provider support when reproducible.

## Security Checks

- `request.json` must never contain raw `api_key`.
- `effective_config.provider.api_key` must be masked (`***set***`).
- Prompt text is not logged directly; only `prompt_hash` is stored.
- `error.json` must not leak raw secret values.

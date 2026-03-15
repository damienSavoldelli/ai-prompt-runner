# CLI Reference

## Invocation Styles

The CLI can be invoked in two supported ways:

```bash
ai-prompt-runner ...
python3 -m ai_prompt_runner.cli ...
```

## Prompt Input Modes

Prompt input is resolved in this priority order:

1. `--prompt`
2. `--prompt-file`
3. piped standard input

If none of these sources is provided, the CLI exits with a usage error.

Dry-run exception:

- when `--dry-run` is set, prompt input is optional because no provider generation is executed

Examples:

```bash
ai-prompt-runner --prompt "Hello world"
ai-prompt-runner --prompt-file prompts/hello.txt
echo "Hello world" | ai-prompt-runner
```

## Configuration Precedence

Runtime configuration follows this precedence:

`CLI > environment variables > TOML config > built-in defaults`

Supported environment variables:

- `AI_API_ENDPOINT`
- `AI_API_KEY`
- `AI_API_MODEL`

Secrets should be provided through environment variables or CLI flags, not through TOML configuration.

## Arguments

### `--prompt`

Inline prompt text to send to the provider.

Rules:

- must not be blank
- mutually exclusive with `--prompt-file`

### `--prompt-file`

Path to a UTF-8 text file containing the prompt.

Rules:

- file must be readable
- content must not be blank
- mutually exclusive with `--prompt`

### `--system`

Optional one-shot instruction context sent with the user prompt.

Rules:

- must not be blank when provided
- stateless: applies only to the current execution
- does not enable multi-turn conversation behavior

Provider behavior:

- role-aware providers (`openai_compatible` aliases, `anthropic`, `google`) map this to native system fields
- non role-aware providers (`http`, `mock`) compose deterministic `SYSTEM/USER` prompt text

### `--provider`

Provider name used for execution.

Supported runtime values:

- `http`
- `openai_compatible`
- `openai`
- `openrouter`
- `groq`
- `together`
- `fireworks`
- `perplexity`
- `inception`
- `x`
- `xai`
- `lmstudio`
- `ollama`
- `anthropic`
- `google`

Implementation note:

- protocol-compatible aliases reuse the same provider class via the registry
- for example, `openai`, `openrouter`, `groq`, `xai`, `ollama` all resolve to the OpenAI-compatible provider

### `--config`

Path to an optional TOML config file containing non-sensitive runtime defaults.

Expected table:

```toml
[ai_prompt_runner]
provider = "http"
api_endpoint = "http://localhost:11434/api/generate"
api_model = "llama3.2"
temperature = 0.2
max_tokens = 512
top_p = 0.9
timeout = 30
retries = 0
out_json = "outputs/response.json"
out_md = "outputs/response.md"
```

### `--api-endpoint`

HTTP or HTTPS endpoint used by the provider.

Rules:

- must not be blank
- must start with `http://` or `https://`

### `--api-key`

API key used for authenticated provider calls.

Recommendation:

- prefer environment variables in normal development and production environments

### `--api-model`

Provider model name.

If omitted, the provider factory uses environment or provider-registry default resolution.

### `--out-json`

Path to the generated JSON output file.

Default:

- `outputs/response.json`

### `--out-md`

Path to the generated Markdown output file.

Default:

- `outputs/response.md`

### `--stream`

Enable progressive chunk rendering on stdout when the provider supports streaming.

Rules:

- optional boolean flag (`store_true`)
- stream-capable providers emit chunks incrementally
- non-stream providers fall back to standard `generate()` behavior
- final JSON and Markdown outputs are still written after full completion

### `--strict-capabilities`

Enable strict provider capability enforcement for requested options.

Rules:

- optional boolean flag (`store_true`)
- in strict mode, requested capabilities marked `unsupported` or `unknown` fail fast
- capability validation failure returns runtime error (exit code `1`)

### `--dry-run`

Run configuration and capability preflight only.

Rules:

- optional boolean flag (`store_true`)
- provider config is resolved and validated
- capability checks are evaluated
- no provider generation call is made
- no JSON/Markdown artifact files are written
- prompt input is optional in this mode

Dry-run output:

- prints a diagnostic JSON payload with `mode`, `status`, and `effective_config`

### `--print-effective-config`

Print resolved runtime configuration diagnostics.

Rules:

- optional boolean flag (`store_true`)
- API key is masked (`***set***`/`not set`)
- diagnostics include provider capabilities and capability validation results
- output is written to stderr

### `--temperature`

Optional runtime temperature forwarded to provider generation payloads.

Rules:

- must be a float
- must be greater than or equal to `0`
- if omitted, provider default behavior is used

### `--max-tokens`

Optional max completion token budget forwarded to providers.

Rules:

- must be an integer
- must be strictly greater than `0`
- if omitted, provider default behavior is used

### `--top-p`

Optional nucleus sampling control forwarded to providers.

Rules:

- must be a float
- must be greater than `0` and less than or equal to `1`
- if omitted, provider default behavior is used

### `--timeout`

HTTP timeout in seconds.

Rules:

- must be an integer
- must be strictly greater than `0`

### `--retries`

Maximum retry attempts for transient network errors.

Rules:

- must be an integer
- must be greater than or equal to `0`

### `--version`

Print the installed application version and exit.

## Output Files

On successful execution, the CLI writes:

- one JSON file
- one Markdown file

JSON metadata always includes:

- `metadata.provider`
- `metadata.timestamp_utc`
- `metadata.execution_ms`

JSON metadata may additionally include:

- `metadata.usage.prompt_tokens`
- `metadata.usage.completion_tokens`
- `metadata.usage.total_tokens`

`metadata.usage` is optional and appears only when the selected provider returns usage counters.

The normalized JSON contract is documented in [`docs/output-contract.md`](./output-contract.md).

## Exit Codes

The CLI uses stable exit codes:

- `0`: success
- `1`: runtime error
- `2`: usage or validation error

## Runtime Error Categories

Typical runtime failures include:

- invalid provider configuration
- strict capability validation failures
- missing endpoint or API key
- network request failures
- provider HTTP errors
- output write failures

These failures result in exit code `1`.

## Examples

Run with explicit values:

```bash
ai-prompt-runner \
  --prompt "Hello world" \
  --provider http \
  --api-endpoint "http://localhost:11434/api/generate" \
  --api-key "dummy" \
  --api-model "llama3.2"
```

Run with system instruction context:

```bash
ai-prompt-runner \
  --provider openai \
  --api-key "$AI_API_KEY" \
  --system "You are a strict API architect." \
  --prompt "Explain timeout and retry strategy"
```

Run with Anthropic defaults:

```bash
ai-prompt-runner \
  --provider anthropic \
  --api-key "$AI_API_KEY" \
  --prompt "Explain timeout strategy"
```

Run with OpenAI defaults:

```bash
ai-prompt-runner \
  --provider openai \
  --api-key "$AI_API_KEY" \
  --prompt "Explain configuration precedence"
```

Run with Google defaults:

```bash
ai-prompt-runner \
  --provider google \
  --api-key "$AI_API_KEY" \
  --prompt "Summarize the provider contract"
```

Run with xAI defaults:

```bash
ai-prompt-runner \
  --provider xai \
  --api-key "$AI_API_KEY" \
  --prompt "Write a short release note"
```

Run with local Ollama defaults:

```bash
ai-prompt-runner \
  --provider ollama \
  --api-key "dummy" \
  --prompt "Hello from ollama"
```

Run with streaming enabled:

```bash
ai-prompt-runner \
  --provider openai \
  --api-key "$AI_API_KEY" \
  --stream \
  --prompt "Explain configuration precedence"
```

Run with strict capability validation:

```bash
ai-prompt-runner \
  --provider http \
  --temperature 0.2 \
  --strict-capabilities \
  --prompt "Hello"
```

Run a dry-run preflight with effective config diagnostics:

```bash
ai-prompt-runner \
  --provider openai \
  --api-key "$AI_API_KEY" \
  --dry-run \
  --print-effective-config
```

Run with runtime controls:

```bash
ai-prompt-runner \
  --provider openai \
  --api-key "$AI_API_KEY" \
  --temperature 0.2 \
  --max-tokens 512 \
  --top-p 0.9 \
  --prompt "Summarize provider contract guarantees"
```

Run with TOML config and prompt file:

```bash
ai-prompt-runner \
  --config config.toml \
  --prompt-file prompts/hello.txt
```

Run with piped input:

```bash
echo "Hello world" | ai-prompt-runner --provider http
```

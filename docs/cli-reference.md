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

The normalized JSON contract is documented in [`docs/output-contract.md`](./output-contract.md).

## Exit Codes

The CLI uses stable exit codes:

- `0`: success
- `1`: runtime error
- `2`: usage or validation error

## Runtime Error Categories

Typical runtime failures include:

- invalid provider configuration
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

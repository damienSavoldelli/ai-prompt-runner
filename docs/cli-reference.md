# CLI Reference

## Invocation Styles

The CLI can be invoked in two supported ways:

```bash
ai-prompt-runner ...
python3 -m src.cli ...
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

### `--provider`

Provider name used for execution.

Current supported runtime value:

- `http`

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

If omitted, the provider factory uses environment or default resolution.

### `--out-json`

Path to the generated JSON output file.

Default:

- `outputs/response.json`

### `--out-md`

Path to the generated Markdown output file.

Default:

- `outputs/response.md`

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

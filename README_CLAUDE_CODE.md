# Using Claude Code (Headless Mode) with CVDP Benchmark

This guide explains how to use [Claude Code](https://docs.anthropic.com/en/docs/claude-code) in **headless mode** to run the CVDP Benchmark, instead of calling the Anthropic API directly.

## Why Claude Code Headless Mode?

Claude Code's headless mode (`claude --print`) lets you:

- **Skip API key management** -- Claude Code handles authentication via its own login flow
- **Use your existing Claude Code subscription** -- no separate API billing needed
- **Leverage Claude Code's built-in features** -- automatic retries, rate limit handling, model routing
- **Choose models easily** -- switch between Opus, Sonnet, and Haiku with simple flags

## Prerequisites

### 1. Install Claude Code

```bash
npm install -g @anthropic-ai/claude-code
```

### 2. Authenticate

Run Claude Code interactively once to complete authentication:

```bash
claude
```

Follow the prompts to log in. Once authenticated, headless mode will work automatically.

### 3. Verify Installation

```bash
claude --version
claude --print "Hello, world"
```

### 4. Install Benchmark Dependencies

```bash
# Create virtual environment (recommended)
python -m venv cvdp_env
source cvdp_env/bin/activate

# Install Python dependencies
pip install -r requirements.txt
```

**Note:** You do **not** need to set `OPENAI_USER_KEY` or `ANTHROPIC_API_KEY` in `.env` when using Claude Code headless mode.

## Quick Start

### Single Run (Non-Agentic)

```bash
# Run benchmark using Claude Code (default model)
./run_benchmark.py -f example_dataset/cvdp_v1.0.1_example_nonagentic_code_generation_no_commercial_with_solutions.jsonl \
    -l -m claude-code -p work_claude_code

# Check results
cat work_claude_code/report.txt
```

### Choose a Specific Model

```bash
# Use Claude Opus
./run_benchmark.py -f example_dataset/cvdp_v1.0.1_example_nonagentic_code_generation_no_commercial_with_solutions.jsonl \
    -l -m claude-code-opus -p work_opus

# Use Claude Sonnet
./run_benchmark.py -f example_dataset/cvdp_v1.0.1_example_nonagentic_code_generation_no_commercial_with_solutions.jsonl \
    -l -m claude-code-sonnet -p work_sonnet

# Use Claude Haiku
./run_benchmark.py -f example_dataset/cvdp_v1.0.1_example_nonagentic_code_generation_no_commercial_with_solutions.jsonl \
    -l -m claude-code-haiku -p work_haiku
```

### Multi-Sample Evaluation (Pass@k)

```bash
# Run 5 samples with Claude Code Sonnet, compute Pass@1
./run_samples.py \
    -f example_dataset/cvdp_v1.0.1_example_nonagentic_code_generation_no_commercial_with_solutions.jsonl \
    -l -m claude-code-sonnet -n 5 -k 1 -p work_claude_composite

# Check composite results
cat work_claude_composite/composite_report.txt
```

### Single Problem Debugging

```bash
# Run a single problem for debugging
./run_benchmark.py \
    -f example_dataset/cvdp_v1.0.1_example_nonagentic_code_generation_no_commercial_with_solutions.jsonl \
    -l -m claude-code -i cvdp_copilot_lfsr_0001 -p work_debug

# Examine the prompt that was sent
cat work_debug/cvdp_copilot_lfsr_0001/prompts/*.md
```

## Available Model Names

| Model Name | Description | Underlying Model |
|---|---|---|
| `claude-code` | Default (uses Claude Code's default model) | Claude Code default |
| `claude-code-opus` | Claude Opus 4.6 | `claude-opus-4-6` |
| `claude-code-sonnet` | Claude Sonnet 4.6 | `claude-sonnet-4-6` |
| `claude-code-haiku` | Claude Haiku 4.5 | `claude-haiku-4-5-20251001` |

## Configuration

### Environment Variables

These optional environment variables control Claude Code headless behavior:

| Variable | Default | Description |
|---|---|---|
| `CLAUDE_CODE_MAX_TURNS` | `1` | Max conversation turns per prompt (1 = single-turn, suitable for benchmarks) |
| `MODEL_TIMEOUT` | `60` | Timeout in seconds for each CLI call |

Set them in your `.env` file or export them:

```bash
export CLAUDE_CODE_MAX_TURNS=1
export MODEL_TIMEOUT=120
```

### Parallel Execution

Claude Code headless mode supports parallel execution via the `--threads` flag:

```bash
# Run with 4 parallel threads
./run_benchmark.py \
    -f example_dataset/cvdp_v1.0.1_example_nonagentic_code_generation_no_commercial_with_solutions.jsonl \
    -l -m claude-code-sonnet --threads 4 -p work_parallel
```

**Note:** Be mindful of rate limits when using high thread counts. Claude Code handles rate limiting internally, but high concurrency may still result in queued requests.

## How It Works

The integration uses Claude Code's `--print` flag (headless mode) to run prompts non-interactively:

```
claude --print --model <model> --max-turns 1 --output-format text --prompt -
```

The prompt is passed via stdin to avoid shell escaping issues. The flow is:

1. The benchmark constructs a system prompt + user prompt (same as for API-based models)
2. The combined prompt is sent to the `claude` CLI via stdin
3. Claude Code handles authentication, model routing, and API calls internally
4. The text response is parsed by the same `ModelHelpers` used by all other model backends
5. Parsed output is evaluated by the standard test harness (Docker-based simulation)

### Architecture

```
run_benchmark.py
    -> ModelFactory.create_model("claude-code-sonnet")
        -> ClaudeCodeInstance
            -> subprocess: claude --print --model claude-sonnet-4-6 ...
                -> Claude Code handles auth & API calls
            <- stdout: model response text
        -> ModelHelpers.parse_model_response()
    -> Docker harness evaluation (same as all other models)
```

## Comparison with Other Approaches

| Approach | Auth Method | Billing | Setup |
|---|---|---|---|
| **Claude Code (headless)** | Claude Code login | Claude Code subscription | `npm install -g @anthropic-ai/claude-code` |
| **Anthropic API** (custom factory) | `ANTHROPIC_API_KEY` | API usage billing | `pip install anthropic` + custom factory |
| **OpenAI API** (built-in) | `OPENAI_USER_KEY` | API usage billing | Set key in `.env` |

## Troubleshooting

### "claude: command not found"

Install Claude Code:
```bash
npm install -g @anthropic-ai/claude-code
```

### "Authentication issue"

Run Claude Code interactively to re-authenticate:
```bash
claude
```

### Timeout errors

Increase the timeout:
```bash
export MODEL_TIMEOUT=300  # 5 minutes
```

### Rate limiting

Reduce parallelism:
```bash
./run_benchmark.py -f dataset.jsonl -l -m claude-code --threads 1 -p work_output
```

### Empty responses

Enable debug mode to see the full CLI interaction:
```bash
# Set DEBUG_MODE in your environment
export LOG_LEVEL=DEBUG
```

## Code Comprehension Datasets

Claude Code headless mode also works with code comprehension datasets (categories 6, 8-10) that use BLEU/ROUGE/LLM scoring:

```bash
./run_benchmark.py \
    -f example_dataset/cvdp_v1.0.1_example_nonagentic_code_comprehension_with_solutions.jsonl \
    -l -m claude-code-sonnet -p work_comprehension
```

**Note:** LLM-based subjective scoring (categories 9, 10) requires a separate scoring model. By default, this uses the OpenAI API (`sbj_score` model). If you only have Claude Code and no OpenAI key, categories 9 and 10 will still get BLEU/ROUGE scores but may skip the LLM subjective scoring step.

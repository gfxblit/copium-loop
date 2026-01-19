# Copium Loop

AI-powered development workflow automation using LangGraph and Gemini.

## What It Does

Automates your TDD workflow: write code → run tests → review changes → create PR.

## Install

```bash
pip install -e .
export NTFY_CHANNEL="your-channel-name"  # For notifications
```

**Requirements**: Python 3.10+, `gemini` CLI, `gh` CLI, Node.js, Git

## Usage

```bash
# Basic
copium-loop "implement user authentication"

# Options
copium-loop --start reviewer --verbose "check code"
```

**Start nodes**: `coder` (default), `test_runner`, `reviewer`, `pr_creator`

## How It Works

1. **Coder** → Implements using Gemini
2. **Test Runner** → Runs `npm test` or `pnpm test` (automatically detects package manager)
3. **Reviewer** → Reviews commits/diffs
4. **PR Creator** → Pushes & creates PR

Loops on failures (max 3 retries/phase).

## Development

```bash
# Run tests
pytest

# Lint and format
ruff check .
ruff format .
```


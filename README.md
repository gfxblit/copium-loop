# Copium Loop

AI-powered development workflow automation using LangGraph and Gemini.

## What It Does

Automates your TDD workflow: write code → run tests → review changes → create PR. It supports both Node.js and Python projects.

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
copium-loop --node reviewer --verbose "check code"

# Monitor sessions
copium-loop --monitor

# Resume the session for the current branch
copium-loop --continue
```

### CLI Arguments

- `prompt`: The development task to perform.
- `--node`, `-n`: Starting node (`coder`, `tester`, `architect`, `reviewer`, `pr_pre_checker`, `pr_creator`).
- `--monitor`, `-m`: Start the Textual-based TUI monitor (Dashboard).
- `--continue`, `-c`: Continue from the last incomplete workflow session. Sessions are locked to your current git branch. If no prompt is provided and a session exists for the branch, it resumes automatically.
- `--engine`: The LLM engine to use (`gemini` or `jules`, default: `gemini`). Resumed sessions default to the engine they were started with.
- `--verbose`, `-v`: Enable verbose output (default: True).

## Branch-Locked Sessions

Sessions are automatically named based on your repository and current branch (e.g., `owner-repo/branch-name`). This ensures that your work is always organized by the feature you are working on.

When you switch branches, `copium-loop` will naturally find or create the session associated with that branch.

## How It Works

1. **Coder** → Implements using Gemini or Jules API.
2. **Test Runner** → Runs `npm test`, `pnpm test`, or `pytest`. Automatically detects the project type and package manager.
3. **Reviewer** → Reviews commits/diffs using Gemini Pro or Jules API.
4. **PR Creator** → Pushes to a feature branch & creates a Pull Request via `gh` CLI. If a GitHub issue URL is found in the prompt, it automatically links the PR to that issue.

Loops on failures (max 10 retries total).

### Custom Commands

You can override the automatically detected commands using environment variables:
- `COPIUM_TEST_CMD`: Custom test command (e.g., `vitest run`)
- `COPIUM_BUILD_CMD`: Custom build command
- `COPIUM_LINT_CMD`: Custom lint command

## Multi-Monitor Dashboard

The Matrix-style dashboard (`--monitor`) allows you to visualize multiple `copium-loop` sessions side-by-side.

- **Navigation**: Use `TAB` or `ARROW` keys to switch between pages of sessions.
- **Tmux Integration**: Press `1-9` to switch to the tmux session associated with a running workflow.
- **Quit**: Press `q` to exit the monitor.

## Development

```bash
# Run tests
pytest

# Lint and format
ruff check .
ruff format .
```
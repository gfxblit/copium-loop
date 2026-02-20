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

### Continuation and Resumption

Sessions are tied to your current branch and repository. `copium-loop` allows you to resume work seamlessly.

- **Implicit Resumption**: If you run `copium-loop` without a prompt on a branch that has an active session, it will automatically resume from the last node it reached.
  ```bash
  # Automatically resumes the current branch's session
  copium-loop
  ```
- **Explicit Resumption**: Use `--continue` or `-c` to explicitly request resumption.
  ```bash
  copium-loop --continue
  ```
- **Prompt Overriding**: You can resume a session but provide a *new* prompt to guide the AI differently for the remaining nodes.
  ```bash
  copium-loop --continue "now focus on fixing the login bug specifically"
  ```
- **Node Selection**: Combine with `--node` to restart from a specific phase while keeping the existing context.
  ```bash
  # Restart from the testing phase
  copium-loop --continue --node tester
  ```

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
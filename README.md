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

## Architecture

Copium Loop is built on a robust architecture leveraging **LangGraph** for state management and **Gemini** (or **Jules**) for intelligent decision-making.

Key components include:
- **Workflow Graph**: Defined in `graph.py`, this state machine orchestrates the development lifecycle.
- **Nodes**: specialized agents performing distinct tasks:
  - **Coder**: Implements features and fixes bugs.
  - **Tester**: Validates changes using the project's test suite.
  - **Architect**: Reviews changes for high-level design compliance.
  - **Reviewer**: Performs detailed code reviews.
  - **PR Pre-Checker**: Ensures the environment is ready for a PR.
  - **PR Creator**: Handles git operations and PR creation.
- **Engine**: The LLM interface (`src/copium_loop/engine/`) managing interactions with Gemini/Jules models.
- **UI**: A **Textual**-based TUI dashboard (`src/copium_loop/ui/`) for real-time monitoring and interaction.

## Flows

The workflow follows a rigorous TDD loop:

1. **Coder**: Receives the user prompt and modifies the codebase.
2. **Tester** (Test Runner): Runs tests (`pytest`, `npm test`, etc.).
   - *Pass*: Advances to **Architect**.
   - *Fail*: Returns to **Coder** for remediation (up to `MAX_RETRIES`).
3. **Architect**: Analyzes the structural impact of changes.
   - *Approved*: Proceed to **Reviewer**.
   - *Rejected*: Sent back to **Coder**.
4. **Reviewer**: Conducts a line-by-line code review.
   - *Approved*: Moves to **PR Pre-Checker**.
   - *Rejected*: Returns to **Coder**.
5. **PR Pre-Checker**: Ensures the environment is clean and ready for a PR.
   - *Pass*: Triggers **PR Creator**.
   - *Fail*: Returns to **Coder**.
6. **PR Creator**: Pushes the branch and opens a Pull Request. If a GitHub issue URL is found in the prompt, it automatically links the PR to that issue.

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
# Default models to try in order. Gemini-3 and 2.5
# share the same quota, so no point in add those as
# fallbacks.
MODELS = [
    "gemini-3.1-pro-preview",
    "gemini-3-pro-preview",
    "gemini-3-flash-preview",
]

# Valid workflow nodes
VALID_NODES = [
    "coder",
    "tester",
    "architect",
    "reviewer",
    "pr_pre_checker",
    "pr_creator",
    "journaler",
]

# Lean nodes that should occupy minimal space in the UI
LEAN_NODES = {"tester", "pr_pre_checker", "pr_creator"}

# Max retries for the workflow
MAX_RETRIES = 10

# Inactivity timeout in seconds (10 minutes)
INACTIVITY_TIMEOUT = 600

# Node-level hard timeout in seconds (60 minutes)
NODE_TIMEOUT = 3600

# Command execution total timeout in seconds (30 minutes)
COMMAND_TIMEOUT = 1800

# Max output size in bytes (1MB) to prevent memory exhaustion
MAX_OUTPUT_SIZE = 1024 * 1024

# Default minimum test coverage percentage
DEFAULT_MIN_COVERAGE = 80

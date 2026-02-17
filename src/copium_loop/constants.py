# Default models to try in order. Gemeni-3 and 2.5
# share the same quota, so no point in add those as
# fallbacks.
MODELS = [
    "gemini-3-pro-preview",
    "gemini-3-flash-preview",
]

# Node Names
NODE_CODER = "coder"
NODE_TESTER = "tester"
NODE_ARCHITECT = "architect"
NODE_REVIEWER = "reviewer"
NODE_PR_PRE_CHECKER = "pr_pre_checker"
NODE_PR_CREATOR = "pr_creator"
NODE_JOURNALER = "journaler"

# Valid workflow nodes
VALID_NODES = [
    NODE_CODER,
    NODE_TESTER,
    NODE_ARCHITECT,
    NODE_REVIEWER,
    NODE_PR_PRE_CHECKER,
    NODE_PR_CREATOR,
    NODE_JOURNALER,
]

# Node Statuses
STATUS_ACTIVE = "active"
STATUS_SUCCESS = "success"
STATUS_FAILED = "failed"

# Max retries for the workflow
MAX_RETRIES = 10

# Inactivity timeout in seconds (5 minutes)
INACTIVITY_TIMEOUT = 300

# Node-level hard timeout in seconds (30 minutes)
NODE_TIMEOUT = 1800

# Command execution total timeout in seconds (20 minutes)
COMMAND_TIMEOUT = 1200

# Max output size in bytes (1MB) to prevent memory exhaustion
MAX_OUTPUT_SIZE = 1024 * 1024

# Default minimum test coverage percentage
DEFAULT_MIN_COVERAGE = 80

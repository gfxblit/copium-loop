# Default models to try in order
DEFAULT_MODELS = [
    "gemini-3-pro-preview",
    "gemini-3-flash-preview",
    "gemini-2.5-pro",
    "gemini-2.5-flash",
]

# Reviewer node models (starts with gemini-2.5-pro)
REVIEWER_MODELS = [
    "gemini-2.5-pro",
    "gemini-2.5-flash",
]

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

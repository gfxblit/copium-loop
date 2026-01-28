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

# Total timeout in seconds (10 minutes)
TOTAL_TIMEOUT = 600

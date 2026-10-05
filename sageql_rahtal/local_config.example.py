"""Copy to local_config.py and edit these local Rahtal test options.

Keep database and LLM credentials in .env, not in this file.
"""

# Write the question here. Set to "" to read QUESTION_FILE instead.
QUESTION = (
    "For all available data, show one row per activity date with the sum of "
    "activity hours across all users. Do not group by user or compare periods."
)
QUESTION_FILE = None  # Example: "questions/daily_hours.txt"

# "validate" stops after SQL validation; "execute" also queries SQL Server.
# Execution requires a database login that can read the approved report tables.
RUN_MODE = "validate"

# Paths are relative to this file. None uses the runner's defaults.
ENV_FILE = None
REPORTS_DIR = None

# Dates use ISO format. End dates are exclusive. Fill in both fields of a pair.
PERIOD_START = None
PERIOD_END = None
COMPARISON_START = None
COMPARISON_END = None

MAX_ROWS = 100
TIMEOUT_SECONDS = 10
LLM_TIMEOUT_SECONDS = 60  # Each model request; automatic retries are disabled.

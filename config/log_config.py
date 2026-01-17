"""
Log config values for logging logs
"""

import os


class LogConfig:
    DEFAULT_LOG_DOMAIN = "foobar"
    VERBOSE = True
    ENABLED = os.environ.get("DAGONET_ENABLE_LOGGING", "1") != "0"
    # Maximum size of a log file before a new one is created
    MAX_LOG_FILE_BYTES = 10 * 1024 * 1024  # 10 MB


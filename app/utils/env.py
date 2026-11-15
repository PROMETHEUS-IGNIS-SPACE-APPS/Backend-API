"""Minimal ``.env`` loader so secrets such as GEMINI_API_KEY stay out of the code.

Only ``KEY=VALUE`` lines are read; existing environment variables always win.
No third-party dependency is needed for this.
"""

import os
from pathlib import Path

_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
_loaded = False


def load_env_file(path: Path = _ENV_FILE) -> None:
    """Load ``path`` into ``os.environ`` once, without overriding existing values."""
    global _loaded
    if _loaded:
        return
    # Not latched while the file is missing, so creating .env later works without a restart.
    if not path.is_file():
        return
    _loaded = True
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value

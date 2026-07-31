"""Git client abstraction.

Wraps the system ``git`` executable through subprocess. Kept deliberately thin
and side-effect free so callers can inject a fake during tests. All commands
run with a timeout and capture output rather than inheriting the terminal.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from app.core.errors import ValidationError
from app.core.logging import StructuredLogger, get_logger

logger = get_logger(__name__)


class GitClient:
    """Execute git operations with a bounded timeout and no interactive input."""

    def __init__(
        self,
        *,
        timeout_seconds: int,
        executable: str = "git",
        logger: StructuredLogger = logger,
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._executable = executable
        self._logger = logger

    def clone(self, url: str, destination: Path) -> None:
        """Clone ``url`` into ``destination`` as a shallow single-branch clone."""
        command = [
            self._executable,
            "clone",
            "--depth",
            "1",
            "--single-branch",
            url,
            str(destination),
        ]
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=self._timeout_seconds,
            check=False,
        )
        if result.returncode != 0:
            self._logger.structured(
                logging.ERROR,
                "git clone failed",
                url=url,
                exit_code=result.returncode,
                stderr=result.stderr.strip(),
            )
            raise ValidationError(
                reason="Failed to clone repository",
                module="Repository Manager",
                detail={
                    "exit_code": result.returncode,
                    "stderr": result.stderr.strip(),
                },
            )

from __future__ import annotations

import shlex
import subprocess

from home_network_guardian.config import Settings


class Blocker:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def block_source(self, source: str) -> tuple[bool, str]:
        cmd = self.settings.block_command.format(source=source)
        if self.settings.mode == "safe":
            return True, f"[SAFE MODE] Would run: {cmd}"

        args = shlex.split(cmd)
        proc = subprocess.run(args, capture_output=True, text=True, check=False)
        if proc.returncode == 0:
            return True, f"Blocked source {source}"
        err = proc.stderr.strip() or proc.stdout.strip() or "unknown error"
        return False, f"Failed to block {source}: {err}"

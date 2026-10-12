from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    runtime_root = project_root / "runtime-data"
    runtime_root.mkdir(parents=True, exist_ok=True)
    stdout_path = runtime_root / "platform-api.stdout.log"
    stderr_path = runtime_root / "platform-api.stderr.log"
    pid_path = runtime_root / "platform-api.pid"

    creation_flags = 0
    if os.name == "nt":
        creation_flags = subprocess.CREATE_NO_WINDOW

    with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open(
        "w", encoding="utf-8"
    ) as stderr:
        process = subprocess.Popen(
            [sys.executable, "-m", "platform_api.main"],
            cwd=project_root,
            env=os.environ.copy(),
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            creationflags=creation_flags,
        )

    pid_path.write_text(str(process.pid), encoding="ascii")
    print(process.pid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "windows" if os.name == "nt" else "offscreen")

from ai_desktop.app import create_application  # noqa: E402
from ai_desktop.main_window import MainWindow  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render the main window to PNG")
    parser.add_argument("--width", type=int, default=1440)
    parser.add_argument("--height", type=int, default=900)
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "artifacts" / "main-window.png",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    app = create_application(["render_main_window"])
    window = MainWindow()
    window.set_user_profile({"display_name": "开发用户"})
    window.resize(args.width, args.height)
    window.show()
    app.processEvents()
    image = window.grab()
    if not image.save(str(output), "PNG"):
        raise RuntimeError(f"Unable to save screenshot: {output}")
    print(output)
    print(f"{image.width()}x{image.height()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import logging
from logging.handlers import RotatingFileHandler
import signal
import sys
import time
from pathlib import Path

from automation_tool.controller import AutomationController
from automation_tool.gui import AutomationGUI

if getattr(sys, "frozen", False):
    LOG_FILE = Path(sys.executable).with_name("automation.log")
else:
    LOG_FILE = Path(__file__).with_name("automation.log")


def configure_logging(level: str = "INFO") -> None:
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(level=numeric_level, format=log_format)

    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=1_048_576, backupCount=3)
    file_handler.setFormatter(logging.Formatter(log_format))
    logging.getLogger().addHandler(file_handler)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Automate trade clicks via image detection")
    parser.add_argument("--config", default="config.json", help="Path to config file (JSON or YAML)")
    parser.add_argument("--no-gui", action="store_true", help="Run without Tkinter GUI")
    parser.add_argument("--log-level", default="INFO", help="Logging level")
    return parser.parse_args()


def _resolve_config_path(raw_config: str) -> Path:
    candidate = Path(raw_config).expanduser()

    search_paths = [candidate]
    if not candidate.is_absolute():
        search_paths.extend(
            [
                Path.cwd() / candidate,
                Path(__file__).resolve().parent / candidate,
                Path(sys.executable).resolve().parent / candidate,
            ]
        )

    bundle_dir = getattr(sys, "_MEIPASS", None)
    if bundle_dir:
        bundle_candidate = Path(bundle_dir) / candidate
        search_paths.append(bundle_candidate)
        if candidate.name != candidate.as_posix():
            search_paths.append(Path(bundle_dir) / candidate.name)

    seen = set()
    for path in search_paths:
        norm = str(path)
        if norm in seen:
            continue
        seen.add(norm)
        try:
            if path.exists():
                return path.resolve()
        except OSError:
            continue

    return candidate.resolve()


def main() -> int:
    args = parse_args()
    configure_logging(args.log_level)
    config_path = _resolve_config_path(args.config)

    controller = AutomationController(config_path)

    def handle_shutdown(_signum=None, _frame=None):
        logging.getLogger(__name__).info("Shutting down automation")
        controller.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, handle_shutdown)

    if not args.no_gui:
        try:
            gui = AutomationGUI(controller)
            gui.run()
            return 0
        except Exception as exc:
            logging.getLogger(__name__).exception("Failed to start GUI: %s", exc)
            print("GUI unavailable, falling back to headless mode", file=sys.stderr)

    controller.start()
    logging.getLogger(__name__).info("Automation running in headless mode. Use %s to pause/resume.", controller.config.hotkeys.pause_resume)
    try:
        while True:
            if controller.shutdown_requested():
                break
            if not controller.engine.is_running():
                logging.getLogger(__name__).warning("Automation engine stopped; exiting main loop")
                break
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        controller.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

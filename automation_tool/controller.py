from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import List, Optional

from .automation_engine import AutomationEngine
from .config_loader import AppConfig, ConfigLoader
from .hotkeys import HotkeyListener

LOGGER = logging.getLogger(__name__)


class AutomationController:
    def __init__(self, config_path: Path):
        self._config_path = config_path
        self._config_loader = ConfigLoader(config_path)
        self._engine: Optional[AutomationEngine] = None
        self._hotkeys: List[HotkeyListener] = []
        self._config: Optional[AppConfig] = None
        self._shutdown_event = threading.Event()
        self.reload_config()

    @property
    def engine(self) -> AutomationEngine:
        if not self._engine:
            raise RuntimeError("Automation engine not initialized")
        return self._engine

    @property
    def config(self) -> AppConfig:
        if not self._config:
            raise RuntimeError("Config not loaded")
        return self._config

    def start(self) -> None:
        self._shutdown_event.clear()
        self.engine.start()

    def stop(self) -> None:
        if self._engine:
            self._engine.stop()

    def shutdown(self) -> None:
        self._shutdown_event.set()
        self._stop_hotkeys()
        if self._engine:
            self._engine.shutdown()

    def reload_config(self) -> None:
        LOGGER.info("Loading configuration from %s", self._config_path)
        config = self._config_loader.load()
        if self._engine:
            self._engine.shutdown()
        self._stop_hotkeys()
        self._config = config
        self._engine = AutomationEngine(config)
        self._setup_hotkeys(config)

    def toggle_pause(self) -> bool:
        return self.engine.toggle_pause()

    def request_shutdown(self) -> None:
        LOGGER.info("Shutdown hotkey triggered; stopping automation")
        self.shutdown()

    def shutdown_requested(self) -> bool:
        return self._shutdown_event.is_set()

    def _on_pause_hotkey(self) -> None:
        paused = self.engine.toggle_pause()
        LOGGER.info("Hotkey toggled pause; paused=%s", paused)

    def _stop_hotkeys(self) -> None:
        for listener in self._hotkeys:
            listener.stop()
        self._hotkeys.clear()

    def _setup_hotkeys(self, config: AppConfig) -> None:
        self._hotkeys = []
        pause_hotkey = (config.hotkeys.pause_resume or "").strip()
        if pause_hotkey:
            pause_listener = HotkeyListener(pause_hotkey, self._on_pause_hotkey)
            pause_listener.start()
            self._hotkeys.append(pause_listener)
        shutdown_hotkey = (config.hotkeys.shutdown or "").strip()
        if shutdown_hotkey:
            shutdown_listener = HotkeyListener(shutdown_hotkey, self.request_shutdown)
            shutdown_listener.start()
            self._hotkeys.append(shutdown_listener)

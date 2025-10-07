from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional

LOGGER = logging.getLogger(__name__)

try:  # pragma: no cover - optional
    import keyboard  # type: ignore
except Exception:
    keyboard = None

try:  # pragma: no cover - optional fallback
    from pynput import keyboard as pynput_keyboard  # type: ignore
except Exception:
    pynput_keyboard = None


class HotkeyListener:
    def __init__(self, hotkey: str, callback: Callable[[], None]):
        self._hotkey = hotkey
        self._callback = callback
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._listener = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="hotkey-listener", daemon=True)
        self._thread.start()
        LOGGER.info("Hotkey listener active on %s", self._hotkey)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._detach()
        LOGGER.info("Hotkey listener stopped")

    def _run(self) -> None:  # pragma: no cover - hardware interaction
        if keyboard:
            handle = keyboard.add_hotkey(self._hotkey, self._safe_callback)
            self._listener = ("keyboard", handle)
            try:
                while not self._stop_event.is_set():
                    time.sleep(0.1)
            finally:
                keyboard.remove_hotkey(handle)
                self._listener = None
            return
        if pynput_keyboard:
            def on_press(key):
                try:
                    key_name = key.char.lower() if key.char else str(key).split(".")[-1]
                except AttributeError:
                    key_name = str(key)
                if key_name.lower() == self._hotkey.lower() and not self._stop_event.is_set():
                    self._safe_callback()
                return not self._stop_event.is_set()

            listener = pynput_keyboard.Listener(on_press=on_press)
            self._listener = ("pynput", listener)
            listener.start()
            while not self._stop_event.is_set():
                time.sleep(0.1)
            listener.stop()
            listener.join()
            self._listener = None
            return
        LOGGER.warning("No hotkey backend available; hotkey %s disabled", self._hotkey)

    def _safe_callback(self) -> None:
        try:
            self._callback()
        except Exception as exc:
            LOGGER.exception("Hotkey callback failed: %s", exc)

    def _detach(self) -> None:
        if self._listener and self._listener[0] == "keyboard" and keyboard:
            keyboard.remove_hotkey(self._listener[1])
        if self._listener and self._listener[0] == "pynput":
            # pynput listener is already stopped in _run
            pass
        self._listener = None

from __future__ import annotations

import logging
import time
from typing import Optional

try:
    import pyautogui
except Exception as exc:  # pragma: no cover - import guard
    pyautogui = None

try:  # pragma: no cover - optional dependency
    import win32api
    import win32con
except Exception:
    win32api = None
    win32con = None

from .config_loader import ClickConfig, Point

LOGGER = logging.getLogger(__name__)


class ClickExecutor:
    def __init__(self, config: ClickConfig):
        self._config = config
        self._win32_available = bool(win32api and win32con)
        self._use_win32 = self._config.use_win32 and self._win32_available
        if self._config.use_win32 and not self._win32_available:
            LOGGER.warning("Win32 click mode requested but dependencies missing; falling back to pyautogui")
        if pyautogui:
            pyautogui.FAILSAFE = False

    def click(self, point: Point, pause: Optional[float] = None) -> None:
        if self._use_win32:
            self._win32_click(point)
        else:
            self._pyautogui_click(point)
        if pause:
            time.sleep(pause)

    def _pyautogui_click(self, point: Point) -> None:
        if not pyautogui:
            raise RuntimeError("pyautogui is required for click simulation but is not installed")
        pyautogui.click(x=point.x, y=point.y)

    def _win32_click(self, point: Point) -> None:
        if not self._win32_available:
            raise RuntimeError("Win32 click simulation unavailable")
        current_pos = win32api.GetCursorPos()
        try:
            win32api.SetCursorPos((point.x, point.y))
            time.sleep(max(self._config.win32_press_duration / 1000.0, 0.01))
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            time.sleep(max(self._config.win32_press_duration / 1000.0, 0.01))
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        finally:
            if self._config.move_cursor_back:
                win32api.SetCursorPos(current_pos)

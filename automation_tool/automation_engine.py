from __future__ import annotations

import logging
import threading
import time
from typing import List, Optional

from .clicker import ClickExecutor
from .config_loader import AppConfig, Point
from .detection import DetectionManager, TradeStatus

LOGGER = logging.getLogger(__name__)


class AutomationEngine:
    def __init__(self, config: AppConfig):
        self._config = config
        self._detection = DetectionManager(config)
        self._clicker = ClickExecutor(config.clicks)
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()  # start unpaused
        self._lock = threading.Lock()
        self._last_statuses: List[TradeStatus] = []
        self._last_collect_ts = 0.0
        self._last_refresh_ts = 0.0

    @property
    def statuses(self) -> List[TradeStatus]:
        with self._lock:
            return list(self._last_statuses)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            LOGGER.debug("Automation already running")
            return
        self._stop_event.clear()
        self._pause_event.set()
        self._thread = threading.Thread(target=self._run_loop, name="trade-automation", daemon=True)
        self._thread.start()
        LOGGER.info("Automation loop started")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        LOGGER.info("Automation loop stopped")

    def pause(self) -> None:
        self._pause_event.clear()
        LOGGER.info("Automation paused")

    def resume(self) -> None:
        self._pause_event.set()
        LOGGER.info("Automation resumed")

    def toggle_pause(self) -> bool:
        if self._pause_event.is_set():
            self.pause()
            return True
        self.resume()
        return False

    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def is_paused(self) -> bool:
        return not self._pause_event.is_set()

    def last_frames(self):
        return self._detection.last_frames

    def _update_statuses(self, statuses: List[TradeStatus]) -> None:
        with self._lock:
            self._last_statuses = statuses

    def _run_loop(self) -> None:  # pragma: no cover - run loop difficult to unit test
        cycle_delay = max(self._config.cycle_delay, 0.05)
        while not self._stop_event.is_set():
            if not self._pause_event.is_set():
                time.sleep(0.1)
                continue
            cycle_start = time.time()
            statuses = self._detection.evaluate_all()
            self._update_statuses(statuses)
            click_performed = self._handle_trades(statuses)
            self._handle_collect()
            self._handle_refresh(statuses, click_performed)
            elapsed = time.time() - cycle_start
            time.sleep(max(cycle_delay - elapsed, 0.01))

    def _handle_trades(self, statuses: List[TradeStatus]) -> bool:
        any_click = False
        for trade, status in zip(self._config.trades, statuses):
            if status.has_red_gem:
                if status.start_active is None or status.start_active:
                    LOGGER.info("Red gem detected for %s (ratio %.3f) -> clicking start", trade.name, status.red_ratio)
                    self._click(trade.start_button)
                    any_click = True
                    time.sleep(self._config.timing.post_click_delay)
                else:
                    LOGGER.debug("Red gem detected but start button inactive for %s", trade.name)
        return any_click

    def _click(self, point: Point) -> None:
        self._clicker.click(point)

    def _handle_collect(self) -> None:
        now = time.time()
        interval = self._config.timing.collect_interval
        if interval <= 0:
            return
        if now - self._last_collect_ts >= interval:
            LOGGER.info("Collect interval reached -> clicking collect button")
            self._click(self._config.collect_button)
            self._last_collect_ts = now
            time.sleep(self._config.timing.post_click_delay)

    def _handle_refresh(self, statuses: List[TradeStatus], click_performed: bool) -> None:
        now = time.time()
        refresh_interval = self._config.timing.refresh_interval
        refresh_due = refresh_interval > 0 and (now - self._last_refresh_ts >= refresh_interval)
        no_red = not any(status.has_red_gem for status in statuses)
        disabled_flags = [status.start_disabled for status in statuses if status.start_disabled is not None]
        all_disabled = len(disabled_flags) > 0 and all(disabled_flags)

        if (no_red or all_disabled or refresh_due) and not click_performed:
            LOGGER.info(
                "Triggering refresh (no_red=%s, all_disabled=%s, refresh_due=%s)",
                no_red,
                all_disabled,
                refresh_due,
            )
            self._click(self._config.refresh_button)
            self._last_refresh_ts = now
            time.sleep(self._config.timing.post_click_delay)

    def shutdown(self) -> None:
        self.stop()

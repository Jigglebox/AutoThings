from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional, Tuple

import cv2
import mss
import numpy as np

from .config_loader import AppConfig, HSVRange, Region, TemplateConfig, TradeConfig

LOGGER = logging.getLogger(__name__)


@dataclass
class TradeStatus:
    name: str
    red_ratio: float
    has_red_gem: bool
    start_active: Optional[bool]
    start_disabled: Optional[bool]
    template_score: Optional[float]


class ScreenGrabber:
    def __init__(self, monitor_region: Region):
        self._monitor = monitor_region
        self._sct = mss.mss()
        self._lock = Lock()

    def grab(self, region: Region) -> np.ndarray:
        bounded = self._bounded_region(region)
        with self._lock:
            raw = self._sct.grab(bounded)
        frame = np.array(raw)
        return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

    def grab_monitor(self) -> np.ndarray:
        with self._lock:
            raw = self._sct.grab(self._monitor.to_monitor())
        return cv2.cvtColor(np.array(raw), cv2.COLOR_BGRA2BGR)

    def _bounded_region(self, region: Region) -> Dict[str, int]:
        left = max(self._monitor.left, region.left)
        top = max(self._monitor.top, region.top)
        right = min(self._monitor.left + self._monitor.width, region.left + region.width)
        bottom = min(self._monitor.top + self._monitor.height, region.top + region.height)
        width = max(1, right - left)
        height = max(1, bottom - top)
        return {"left": left, "top": top, "width": width, "height": height}


class ColorDetector:
    def __init__(self, hsv_ranges: List[HSVRange], minimum_ratio: float = 0.01):
        self._ranges = hsv_ranges
        self._minimum_ratio = minimum_ratio

    def red_ratio(self, frame_bgr: np.ndarray) -> float:
        hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
        mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
        for hsv_range in self._ranges:
            section = cv2.inRange(hsv, np.array(hsv_range.lower), np.array(hsv_range.upper))
            cv2.bitwise_or(mask, section, mask)
        ratio = float(np.count_nonzero(mask)) / float(mask.size)
        return ratio

    def has_red(self, frame_bgr: np.ndarray, threshold: float) -> bool:
        return self.red_ratio(frame_bgr) >= threshold


class TemplateMatcher:
    def __init__(self, template_configs: Dict[str, TemplateConfig]):
        self._templates = template_configs
        self._cache: Dict[str, Tuple[np.ndarray, float]] = {}

    def is_configured(self) -> bool:
        return bool(self._templates)

    def _load_template(self, name: str) -> Tuple[np.ndarray, float]:
        if name not in self._templates:
            raise KeyError(f"Template {name} not defined in configuration")
        if name in self._cache:
            return self._cache[name]
        config = self._templates[name]
        if not config.path.exists():
            raise FileNotFoundError(f"Template image not found: {config.path}")
        image = cv2.imread(str(config.path), cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise RuntimeError(f"Failed to load template image: {config.path}")
        self._cache[name] = (image, config.threshold)
        return self._cache[name]

    def match(self, frame_bgr: np.ndarray, template_name: str) -> Tuple[bool, float]:
        template, threshold = self._load_template(template_name)
        frame_gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        if frame_gray.shape[0] < template.shape[0] or frame_gray.shape[1] < template.shape[1]:
            LOGGER.warning("Frame smaller than template %s; skipping match", template_name)
            return False, 0.0
        res = cv2.matchTemplate(frame_gray, template, cv2.TM_CCOEFF_NORMED)
        _min_val, max_val, _min_loc, _max_loc = cv2.minMaxLoc(res)
        return max_val >= threshold, float(max_val)


class DetectionManager:
    def __init__(self, config: AppConfig):
        self._config = config
        self._grabber = ScreenGrabber(config.monitor)
        self._color_detector = ColorDetector(config.hsv_ranges)
        self._template_matcher = TemplateMatcher(config.templates)
        self._last_frames: Dict[str, np.ndarray] = {}

    @property
    def last_frames(self) -> Dict[str, np.ndarray]:
        return self._last_frames

    def evaluate_trade(self, trade: TradeConfig) -> TradeStatus:
        frame = self._grabber.grab(trade.region)
        self._last_frames[trade.name] = frame
        ratio = self._color_detector.red_ratio(frame)
        has_red = ratio >= trade.red_ratio_threshold

        start_active = None
        start_disabled = None
        score = None
        if trade.start_template and self._template_matcher.is_configured():
            active, score_val = self._template_matcher.match(frame, trade.start_template)
            start_active = bool(active)
            score = score_val
        if trade.start_gray_template and self._template_matcher.is_configured():
            disabled, score_val = self._template_matcher.match(frame, trade.start_gray_template)
            start_disabled = bool(disabled)
            score = max(score or 0.0, score_val)

        return TradeStatus(
            name=trade.name,
            red_ratio=ratio,
            has_red_gem=has_red,
            start_active=start_active,
            start_disabled=start_disabled,
            template_score=score,
        )

    def capture_monitor(self) -> np.ndarray:
        return self._grabber.grab_monitor()

    def evaluate_all(self) -> List[TradeStatus]:
        statuses: List[TradeStatus] = []
        for trade in self._config.trades:
            try:
                status = self.evaluate_trade(trade)
            except Exception as exc:
                LOGGER.exception("Failed to evaluate trade %s: %s", trade.name, exc)
                status = TradeStatus(
                    name=trade.name,
                    red_ratio=0.0,
                    has_red_gem=False,
                    start_active=None,
                    start_disabled=None,
                    template_score=None,
                )
            statuses.append(status)
        return statuses

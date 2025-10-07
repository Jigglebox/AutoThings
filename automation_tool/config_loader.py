from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    yaml = None

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class Point:
    x: int
    y: int

    @staticmethod
    def from_mapping(mapping: Dict[str, int], label: str = "point") -> "Point":
        try:
            return Point(x=int(mapping["x"]), y=int(mapping["y"]))
        except KeyError as exc:  # pragma: no cover - validation guard
            raise ValueError(f"Missing key {exc!s} for {label}") from exc


@dataclass(frozen=True)
class Region:
    left: int
    top: int
    width: int
    height: int

    @staticmethod
    def from_mapping(mapping: Dict[str, int], label: str = "region") -> "Region":
        required_keys = {"left", "top", "width", "height"}
        missing = required_keys.difference(mapping)
        if missing:
            raise ValueError(f"Missing keys {missing} for {label}")
        return Region(
            left=int(mapping["left"]),
            top=int(mapping["top"]),
            width=int(mapping["width"]),
            height=int(mapping["height"]),
        )

    def to_monitor(self) -> Dict[str, int]:
        return {"left": self.left, "top": self.top, "width": self.width, "height": self.height}


@dataclass(frozen=True)
class HSVRange:
    lower: Tuple[int, int, int]
    upper: Tuple[int, int, int]

    @staticmethod
    def from_sequence(values: Sequence[Sequence[int]]) -> List["HSVRange"]:
        ranges: List[HSVRange] = []
        for pair in values:
            if len(pair) != 2:
                raise ValueError("HSV ranges require two triplets: lower and upper")
            lower, upper = pair
            ranges.append(
                HSVRange(
                    lower=(int(lower[0]), int(lower[1]), int(lower[2])),
                    upper=(int(upper[0]), int(upper[1]), int(upper[2])),
                )
            )
        return ranges


@dataclass(frozen=True)
class TemplateConfig:
    name: str
    path: Path
    threshold: float


@dataclass(frozen=True)
class TradeConfig:
    name: str
    region: Region
    start_button: Point
    start_template: Optional[str] = None
    start_gray_template: Optional[str] = None
    red_ratio_threshold: float = 0.01


@dataclass(frozen=True)
class TimingConfig:
    cycle_delay: float = 0.5
    collect_interval: float = 300.0
    refresh_interval: float = 60.0
    post_click_delay: float = 0.15


@dataclass(frozen=True)
class ClickConfig:
    use_win32: bool = False
    win32_press_duration: int = 40
    move_cursor_back: bool = True


@dataclass(frozen=True)
class HotkeyConfig:
    pause_resume: str = "f9"
    shutdown: str = "f10"


@dataclass
class AppConfig:
    monitor: Region
    trades: List[TradeConfig]
    collect_button: Point
    refresh_button: Point
    hsv_ranges: List[HSVRange]
    templates: Dict[str, TemplateConfig] = field(default_factory=dict)
    timing: TimingConfig = field(default_factory=TimingConfig)
    clicks: ClickConfig = field(default_factory=ClickConfig)
    hotkeys: HotkeyConfig = field(default_factory=HotkeyConfig)
    cycle_delay: float = 0.5


class ConfigLoader:
    def __init__(self, path: Path):
        self.path = path

    def load(self) -> AppConfig:
        if not self.path.exists():
            raise FileNotFoundError(f"Config file not found: {self.path}")
        data = self._read_raw()
        return self._parse(data)

    def _read_raw(self) -> Dict[str, object]:
        suffix = self.path.suffix.lower()
        if suffix in {".yaml", ".yml"}:
            if yaml is None:
                raise RuntimeError("PyYAML required for YAML configs but is not installed")
            with self.path.open("r", encoding="utf-8") as handle:
                return yaml.safe_load(handle)
        with self.path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _parse(self, data: Dict[str, object]) -> AppConfig:
        monitor_data = data.get("monitor") or data.get("region")
        if not isinstance(monitor_data, dict):
            raise ValueError("`monitor` section missing or invalid")
        monitor = Region.from_mapping(monitor_data, "monitor")

        trades_raw = data.get("trades")
        if not isinstance(trades_raw, list):
            raise ValueError("`trades` must be a list")
        trades: List[TradeConfig] = []
        for entry in trades_raw:
            if not isinstance(entry, dict):
                raise ValueError("Each trade entry must be a mapping")
            name = str(entry.get("name") or f"trade_{len(trades)+1}")
            region = Region.from_mapping(entry.get("region", {}), f"trade {name} region")
            start_button = Point.from_mapping(entry.get("start_button", {}), f"trade {name} start_button")
            start_template = entry.get("start_template")
            start_gray_template = entry.get("start_gray_template")
            red_ratio_threshold = float(entry.get("red_ratio_threshold", 0.01))
            trades.append(
                TradeConfig(
                    name=name,
                    region=region,
                    start_button=start_button,
                    start_template=start_template,
                    start_gray_template=start_gray_template,
                    red_ratio_threshold=red_ratio_threshold,
                )
            )

        collect_button = Point.from_mapping(data.get("collect_button", {}), "collect_button")
        refresh_button = Point.from_mapping(data.get("refresh_button", {}), "refresh_button")

        raw_hsv = data.get("hsv_ranges")
        if not isinstance(raw_hsv, list) or not raw_hsv:
            raise ValueError("`hsv_ranges` must contain at least one [lower, upper] pair")
        hsv_ranges = HSVRange.from_sequence(raw_hsv)

        templates_raw = data.get("templates", {})
        templates: Dict[str, TemplateConfig] = {}
        if isinstance(templates_raw, dict):
            base_dir = self.path.parent
            for name, template_entry in templates_raw.items():
                if not isinstance(template_entry, dict):
                    raise ValueError(f"Template {name} must be a mapping")
                rel_path = template_entry.get("path")
                if not rel_path:
                    raise ValueError(f"Template {name} requires a `path`")
                threshold = float(template_entry.get("threshold", 0.8))
                templates[name] = TemplateConfig(
                    name=name,
                    path=(base_dir / rel_path).resolve(),
                    threshold=threshold,
                )

        timing_raw = data.get("timing", {})
        timing = TimingConfig(
            cycle_delay=float(timing_raw.get("cycle_delay", 0.5)),
            collect_interval=float(timing_raw.get("collect_interval", 300.0)),
            refresh_interval=float(timing_raw.get("refresh_interval", 60.0)),
            post_click_delay=float(timing_raw.get("post_click_delay", 0.15)),
        )

        clicks_raw = data.get("clicks", {})
        clicks = ClickConfig(
            use_win32=bool(clicks_raw.get("use_win32", False)),
            win32_press_duration=int(clicks_raw.get("win32_press_duration", 40)),
            move_cursor_back=bool(clicks_raw.get("move_cursor_back", True)),
        )

        hotkeys_raw = data.get("hotkeys", {})
        hotkeys = HotkeyConfig(
            pause_resume=str(hotkeys_raw.get("pause_resume", "f9")),
            shutdown=str(hotkeys_raw.get("shutdown", "f10")),
        )

        return AppConfig(
            monitor=monitor,
            trades=trades,
            collect_button=collect_button,
            refresh_button=refresh_button,
            hsv_ranges=hsv_ranges,
            templates=templates,
            timing=timing,
            clicks=clicks,
            hotkeys=hotkeys,
            cycle_delay=float(data.get("cycle_delay", timing.cycle_delay)),
        )

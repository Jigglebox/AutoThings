from __future__ import annotations

import logging
import tkinter as tk
from pathlib import Path
from typing import Optional

import cv2
from PIL import Image, ImageTk
from tkinter import ttk

from .controller import AutomationController

LOGGER = logging.getLogger(__name__)


class AutomationGUI:
    def __init__(self, controller: AutomationController):
        self._controller = controller
        self._root = tk.Tk()
        self._root.title("Trade Automation")
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._status_var = tk.StringVar(value="Status: stopped")
        self._pause_state = tk.StringVar(value="Pause")
        self._image_label: Optional[tk.Label] = None
        self._image_handle: Optional[ImageTk.PhotoImage] = None

        self._build_layout()
        self._schedule_update()

    def _build_layout(self) -> None:
        control_frame = ttk.Frame(self._root, padding=10)
        control_frame.grid(row=0, column=0, sticky="nsew")

        start_button = ttk.Button(control_frame, text="Start", command=self._on_start)
        start_button.grid(row=0, column=0, padx=5, pady=5)

        stop_button = ttk.Button(control_frame, text="Stop", command=self._on_stop)
        stop_button.grid(row=0, column=1, padx=5, pady=5)

        pause_button = ttk.Button(control_frame, textvariable=self._pause_state, command=self._on_pause)
        pause_button.grid(row=0, column=2, padx=5, pady=5)

        reload_button = ttk.Button(control_frame, text="Reload Config", command=self._on_reload)
        reload_button.grid(row=0, column=3, padx=5, pady=5)

        ttk.Label(control_frame, textvariable=self._status_var).grid(row=1, column=0, columnspan=4, sticky="w", pady=(5, 0))

        tree_frame = ttk.Labelframe(self._root, text="Trades", padding=10)
        tree_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        self._root.grid_rowconfigure(1, weight=1)
        self._root.grid_columnconfigure(0, weight=1)

        columns = ("red", "active", "disabled", "score")
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=6)
        self._tree.heading("red", text="Red Ratio")
        self._tree.heading("active", text="Start Active")
        self._tree.heading("disabled", text="Start Disabled")
        self._tree.heading("score", text="Template Score")
        self._tree.column("red", width=100)
        self._tree.column("active", width=100)
        self._tree.column("disabled", width=110)
        self._tree.column("score", width=110)
        self._tree.pack(fill="both", expand=True)

        preview_frame = ttk.Labelframe(self._root, text="Preview", padding=10)
        preview_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)
        self._image_label = ttk.Label(preview_frame, text="No preview yet")
        self._image_label.pack(fill="both", expand=True)

    def _on_start(self) -> None:
        self._controller.start()
        self._status_var.set("Status: running")

    def _on_stop(self) -> None:
        self._controller.stop()
        self._status_var.set("Status: stopped")

    def _on_pause(self) -> None:
        paused = self._controller.toggle_pause()
        if paused:
            self._pause_state.set("Resume")
            self._status_var.set("Status: paused")
        else:
            self._pause_state.set("Pause")
            self._status_var.set("Status: running")

    def _on_reload(self) -> None:
        self._controller.reload_config()
        self._status_var.set("Status: config reloaded")

    def _schedule_update(self) -> None:
        self._update_status()
        self._root.after(1000, self._schedule_update)

    def _update_status(self) -> None:
        try:
            statuses = self._controller.engine.statuses
        except Exception:
            statuses = []
        self._tree.delete(*self._tree.get_children())
        for status in statuses:
            self._tree.insert(
                "",
                tk.END,
                values=(
                    f"{status.red_ratio:.3f}",
                    self._bool_to_text(status.start_active),
                    self._bool_to_text(status.start_disabled),
                    f"{status.template_score:.2f}" if status.template_score is not None else "-",
                ),
                text=status.name,
            )

        frames = self._controller.engine.last_frames() if self._controller.engine else {}
        if frames:
            name, frame = next(iter(frames.items()))
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(rgb)
            image = image.resize((min(320, image.width), min(240, image.height)))
            self._image_handle = ImageTk.PhotoImage(image=image)
            if self._image_label:
                self._image_label.configure(image=self._image_handle, text=f"{name} preview")
        elif self._image_label:
            self._image_label.configure(image="", text="No preview available")

    @staticmethod
    def _bool_to_text(value: Optional[bool]) -> str:
        if value is None:
            return "?"
        return "Yes" if value else "No"

    def _on_close(self) -> None:
        self._controller.shutdown()
        self._root.destroy()

    def run(self) -> None:
        self._root.mainloop()

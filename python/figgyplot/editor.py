"""The same command dispatcher serves notebook and desktop transports."""
from __future__ import annotations

import copy

from .figure import _display_texts


class EditorSession:
    def __init__(self, figure):
        self.figure = figure
        self.error = ""
        self.last_request = None
        self.handle = None
        self.image = b""
        self._image_revision = None

    def snapshot(self):
        fig = self.figure
        with fig._lock:
            settings = fig.get_settings()
            revision = fig.revision
            if revision != self._image_revision:
                try:
                    self.image = fig.to_png()
                    self._image_revision = revision
                except (RuntimeError, MemoryError) as exc:
                    self.error = f"render failed: {exc}"
            rect = settings["config"]["chart_area"]
            return {"settings": settings, "revision": revision, "image_revision": self._image_revision, "selection": fig._selection,
                    "bounds": fig.selection_bounds(), "handle": self.handle,
                    "width": rect["width"], "height": rect["height"],
                    "dpi": fig.dpi,
                    "code": fig.to_code(), "error": self.error, "last_request": self.last_request,
                    "texts": _display_texts(settings)}

    def dispatch(self, message):
        fig = self.figure
        self.last_request = message.get("request_id")
        self.error = ""
        try:
            with fig._lock:
                if message.get("revision") != fig.revision:
                    raise ValueError("stale edit: refreshed the current Figure; retry the action")
                action = message.get("action")
                if action == "pick":
                    x, y = float(message["x"]), float(message["y"])
                    self.handle = None
                    if fig._selection is not None and fig.selection_bounds() is not None:
                        self.handle = fig._native.resize_handle(fig._selection, x, y)
                    if self.handle is None:
                        fig.select(x, y, edit_area=bool(message.get("edit_area")))
                elif action == "drag":
                    if message.get("target") != fig._selection or fig._selection is None:
                        raise ValueError("selection changed during drag")
                    if fig.selection_bounds() is not None:
                        fig.drag(fig._selection, message["dx"], message["dy"], handle=message.get("handle"))
                elif action == "update":
                    fig.update(message["target"], **message["properties"])
                elif action == "select":
                    fig.select_object(message["target"])
                    self.handle = None
                elif action == "settings":
                    fig.apply_settings(message["settings"], expected_revision=message["revision"])
                elif action == "fit":
                    fig.fit()
                else:
                    raise ValueError(f"unknown editor action: {action}")
        except (ValueError, RuntimeError, MemoryError, KeyError, TypeError) as exc:
            self.error = str(exc)
        return self.snapshot()

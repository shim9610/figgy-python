from pathlib import Path

try:
    import anywidget
    import traitlets
except ImportError as exc:
    raise ImportError("Notebook editing requires: pip install 'figgy-python[notebook]'") from exc

from .editor import EditorSession


class FigureWidget(anywidget.AnyWidget):
    _esm = Path(__file__).with_name("editor.js")
    _css = Path(__file__).with_name("editor.css")
    state = traitlets.Dict().tag(sync=True)
    image = traitlets.Bytes().tag(sync=True)

    def __init__(self, figure):
        self.figure = figure
        self._editor = EditorSession(figure)
        self._handling = False
        super().__init__()
        self.refresh()
        self.on_msg(self._command)

    def refresh(self):
        if self._handling:
            return
        with self.hold_sync():
            self.state = self._editor.snapshot()
            self.image = self._editor.image

    def _command(self, widget, content, buffers):
        self._handling = True
        try:
            state = self._editor.dispatch(content)
            with self.hold_sync():
                self.state = state
                self.image = self._editor.image
        finally:
            self._handling = False

    def close(self):
        self.figure._widgets.discard(self)
        super().close()

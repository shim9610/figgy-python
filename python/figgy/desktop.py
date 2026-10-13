"""A desktop window uses the exact same editor as the notebook widget."""
import base64
import json
from pathlib import Path
import threading

from .editor import EditorSession


def show(figure, *, block=True):
    try:
        from PySide6.QtCore import QObject, Signal, Slot, QUrl
        from PySide6.QtWidgets import QApplication, QMainWindow, QFileDialog
        from PySide6.QtWebEngineWidgets import QWebEngineView
        from PySide6.QtWebChannel import QWebChannel
    except ImportError as exc:
        raise ImportError("Desktop windows require: pip install 'figgy-python[desktop]'") from exc
    if threading.current_thread() is not threading.main_thread():
        raise RuntimeError("show() must run on the main thread")
    app = QApplication.instance()
    owns_loop = app is None
    if app is None:
        app = QApplication([])

    class Bridge(QObject):
        changed = Signal(str)

        @Slot(result=str)
        def initial(self):
            return window.payload()

        @Slot(str)
        def command(self, message):
            window._handling = True
            try:
                window.editor.dispatch(json.loads(message))
                self.changed.emit(window.payload())
            finally:
                window._handling = False

        @Slot(str)
        def copy(self, text):
            app.clipboard().setText(text)

        @Slot()
        def save(self):
            filename, _ = QFileDialog.getSaveFileName(window, "Save PNG", "figure.png", "PNG images (*.png)")
            if filename:
                figure.savefig(filename)

    class Window(QMainWindow):
        def __init__(self):
            super().__init__()
            self.editor = EditorSession(figure)
            self._handling = False
            self.bridge = Bridge(self)
            self.setWindowTitle("Figgy")
            self.resize(1200, 780)
            self.view = QWebEngineView(self)
            self.channel = QWebChannel(self.view.page())
            self.channel.registerObject("bridge", self.bridge)
            self.view.page().setWebChannel(self.channel)
            self.setCentralWidget(self.view)
            here = Path(__file__).parent
            source = base64.b64encode((here / "editor.js").read_bytes()).decode()
            css = (here / "editor.css").read_text()
            html = '''<!doctype html><meta charset="utf-8"><style>CSS</style><div id="editor"></div>
              <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
              <script type="module">
              import {render} from "data:text/javascript;base64,SOURCE";
              new QWebChannel(qt.webChannelTransport, channel => {
                const bridge = channel.objects.bridge;
                let values = {}, callbacks = new Map();
                const receive = json => {
                  const next = JSON.parse(json); values.state = next.state;
                  values.image = Uint8Array.from(atob(next.image), c => c.charCodeAt(0));
                  for (const key of ["change:state", "change:image"]) for (const cb of callbacks.get(key) || []) cb();
                };
                const model = {get: key => values[key], send: message => bridge.command(JSON.stringify(message)),
                  on: (key, cb) => {if (!callbacks.has(key)) callbacks.set(key, new Set()); callbacks.get(key).add(cb);},
                  off: (key, cb) => callbacks.get(key)?.delete(cb)};
                globalThis.figgyDesktopCopy = text => bridge.copy(text);
                globalThis.figgyDesktopSave = () => bridge.save();
                bridge.changed.connect(receive);
                bridge.initial(json => {receive(json); render({model, el: document.getElementById("editor")});});
              });</script>'''.replace("CSS", css).replace("SOURCE", source)
            self.view.setHtml(html, QUrl("qrc:///"))

        def payload(self):
            state = self.editor.snapshot()
            return json.dumps({"state": state, "image": base64.b64encode(self.editor.image).decode()})

        def refresh(self):
            if not self._handling:
                self.bridge.changed.emit(self.payload())

        def closeEvent(self, event):
            if self in figure._windows:
                figure._windows.remove(self)
            self.view.page().deleteLater()
            super().closeEvent(event)

    window = Window()
    figure._windows.append(window)
    # Retain the QApplication for non-blocking use; callers integrate its loop.
    window._application = app
    window.show()
    if block:
        if owns_loop:
            app.exec()
        else:
            from PySide6.QtCore import QEventLoop
            loop = QEventLoop()
            window.destroyed.connect(loop.quit)
            from PySide6.QtCore import Qt
            window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            loop.exec()
    return window

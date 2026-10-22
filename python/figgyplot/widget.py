from pathlib import Path

try:
    import anywidget
    import traitlets
except ImportError as exc:
    raise ImportError("Notebook editing requires: pip install 'figgyplot[notebook]'") from exc

from .editor import EditorSession
from .figure import _display_texts


class PNGFigureWidget(anywidget.AnyWidget):
    _esm = Path(__file__).with_name("editor.js")
    _css = Path(__file__).with_name("editor.css")
    state = traitlets.Dict().tag(sync=True)
    image = traitlets.Bytes().tag(sync=True)

    def __init__(self, figure):
        self.figure = figure
        figure._ensure_edit_baseline()
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

import asyncio
import json
import uuid

class _AsyncSignal:
    """One-shot notification whose waiters belong to their running loops.

    Python 3.8 asyncio.Event binds at construction, before a widget's async
    request loop may exist. Futures are instead created only when awaited.
    """
    def __init__(self):
        self._set = False
        self._waiters = set()

    @staticmethod
    def _resolve(future):
        if not future.done():
            future.set_result(None)

    def set(self):
        self._set = True
        for future in tuple(self._waiters):
            if not future.done():
                future.get_loop().call_soon_threadsafe(self._resolve, future)

    async def wait(self):
        if self._set:
            return
        future = asyncio.get_running_loop().create_future()
        self._waiters.add(future)
        try:
            await future
        finally:
            self._waiters.discard(future)


class FigureWidget(anywidget.AnyWidget):
    """Browser WebGPU host. Comm carries assets, binary columns and settings only."""
    _esm = Path(__file__).with_name("webgpu.js")
    _css = Path(__file__).with_name("editor.css")
    state = traitlets.Dict().tag(sync=True)
    manifest = traitlets.List().tag(sync=True)
    columns = traitlets.List(traitlets.Bytes()).tag(sync=True)
    wasm = traitlets.Bytes().tag(sync=True)
    wasm_js = traitlets.Unicode().tag(sync=True)
    status = traitlets.Unicode("initializing").tag(sync=True)
    browser_info = traitlets.Dict().tag(sync=True)
    draw_styles = traitlets.Dict().tag(sync=True)
    auto_prepare = traitlets.Bool(True).tag(sync=True)
    review = traitlets.Dict().tag(sync=True)
    review_font_data = traitlets.Bytes().tag(sync=True)

    def __init__(self, figure, *, auto_prepare=True):
        self.figure = figure
        figure._ensure_edit_baseline()
        self._handling = False
        self._pending = {}
        self._clients = {}
        self._ready_event = _AsyncSignal()
        self._mounted_event = _AsyncSignal()
        self._closed = False
        manifest, buffers = figure._native.payload()
        assets = Path(__file__).with_name("assets")
        from ._native import draw_style_specs_json
        super().__init__(auto_prepare=auto_prepare, manifest=manifest, columns=buffers,
                         draw_styles=json.loads(draw_style_specs_json()),
                         wasm=(assets / "figgy_bg.wasm").read_bytes(),
                         wasm_js=(assets / "figgy.js").read_text(encoding="utf-8"))
        self.refresh()
        self.on_msg(self._command)

    def refresh(self):
        if not self._handling:
            settings = self.figure.get_settings()
            from ._native import object_outline_json, bounded_view_json
            catalog=self.figure._editor_catalog_transport()
            self.state = {"settings": settings, "revision": self.figure.revision, "code": self.figure.to_code(),
                          "edit_history": self.figure.edit_history,
                          "property_catalog": catalog['objects'],
                          "property_columns": catalog['columns'],
                          "outline": json.loads(object_outline_json(json.dumps(settings))),
                          "bounded_view": json.loads(bounded_view_json(json.dumps(settings))),
                          "texts": _display_texts(settings),
                          "log_bounds": {axis: self.figure._native.log_bounds(axis) for axis in ("x", "y", "z")}}

    def _command(self, widget, content, buffers):
        action = content.get("action")
        if action == "review_comment":
            session = getattr(self.figure, '_review_session', None)
            if session is not None and self.review.get('enabled'):
                try:
                    if session._figures.get(self.figure.id) is not self.figure:raise RuntimeError('Stale review view from a previous round')
                    session._set_comment_text(self.figure.id, content.get('comments', ''))
                    if 'target_comments' in content:session._set_target_comments(self.figure.id,content['target_comments'])
                except Exception as exc:self.send(dict(action='review_result',error=str(exc)))
        elif action == "review_submit":
            try:
                session = getattr(self.figure, '_review_session', None)
                if session is None or not self.review.get('enabled'):
                    raise RuntimeError('This Figure is not in a review session')
                if session._figures.get(self.figure.id) is not self.figure:
                    raise RuntimeError('Stale review view from a previous round')
                # The browser submits only after its input queue and accepted
                # edit acknowledgements are drained. Verify that revision in the
                # common commit path; do not start another barrier inside a comm.
                session._set_target_comments(self.figure.id,content.get('target_comments',[]))
                session._submit(self.figure.id, content['disposition'],
                    content.get('comments'), content['revision'], content.get('intent','revise'))
            except Exception as exc:
                self.send(dict(action='review_result',error=str(exc)))
        elif action == "mounted":
            self._clients[content["client"]] = True
            self._mounted_event.set()
        elif action == "ready":
            self.status = "ready"
            self._clients[content.get("client")] = True
            self._ready_event.set()
            self.browser_info = content.get("info", {})
            self.figure._native.acknowledged()
            if not self.figure._native.retain:
                with self.hold_sync():
                    self.columns = []
                    self.wasm = b""
                    self.wasm_js = ""
        elif action == "failed":
            self.status = "WebGPU error: " + str(content.get("error"))
            self._ready_event.set()
        elif action == "unmounted":
            self._clients.pop(content.get("client"), None)
        elif action == "fit":
            if content.get("revision") == self.figure.revision:
                self.figure.fit()
            self.refresh()
        elif action in ('undo', 'redo', 'reset_edits', 'property'):
            error = ''
            try:
                if action=='property':
                    self.figure.edit_property(content['object_id'],content['property_id'],content['value'],expected_revision=content.get('revision'))
                else:
                    getattr(self.figure, action)(expected_revision=content.get('revision'))
            except (ValueError, RuntimeError) as exc:
                error = str(exc)
            self.refresh()
            self.send({'action':'history_result','operation':action,'object_id':content.get('object_id'),'client':content.get('client'),'state':self.state,'error':error})
        elif action == "edit":
            self._handling = True
            error = ""
            try:
                self.figure.apply_settings(content["settings"], expected_revision=content["revision"])
            except Exception as exc:
                error = str(exc)
            finally:
                self._handling = False
            self.refresh()
            self.send({"action": "ack", "client": content.get("client"), "sequence": content["sequence"], "state": self.state, "error": error})
        elif action == "rejected":
            if content["revision"] == self.figure.revision:
                self.figure.apply_settings(content["settings"], expected_revision=content["revision"])
            self.browser_info = dict(self.browser_info, settings_error=content["error"])
        elif action == "result":
            pending = self._pending.pop(content.get("id"), None)
            if pending is None:
                return
            future, expected_action = pending
            if not future.done():
                if content.get("error"):
                    future.set_exception(RuntimeError(content["error"]))
                elif expected_action == "prepare":
                    future.set_result(content["result"])
                elif expected_action == "export" and not buffers:
                    future.set_exception(RuntimeError("Browser PNG export returned no binary buffer"))
                else:
                    future.set_result(bytes(buffers[0]) if buffers else self.figure.get_settings())
        elif action == "stats":
            self.browser_info = content["info"]

    async def request(self, action, *, timeout, **kwargs):
        from .figure import _timeout
        timeout = _timeout(timeout)
        try:
            if action == "prepare":
                await asyncio.wait_for(self._mounted_event.wait(), timeout)
            elif self.status == "initializing":
                if not self.auto_prepare:
                    raise RuntimeError("Browser GPU is not prepared; await fig.prepare_async() first")
                await asyncio.wait_for(self._ready_event.wait(), timeout)
        except asyncio.TimeoutError:
            raise TimeoutError(f"Browser {action} initialization timed out after {timeout:g} seconds; display the widget in a WebGPU browser") from None
        if self._closed:
            raise RuntimeError("Figure widget closed")
        if self.status.startswith("WebGPU error"):
            raise RuntimeError(self.status)
        loop = asyncio.get_running_loop()
        id = uuid.uuid4().hex
        future = loop.create_future()
        self._pending[id] = (future, action)
        self.send({"action": action, "id": id, "client": next(reversed(self._clients), None), **kwargs})
        try:
            return await asyncio.wait_for(future, timeout)
        except asyncio.TimeoutError:
            raise TimeoutError(f"Browser {action} timed out after {timeout:g} seconds; check that the viewer is connected and prepared") from None
        finally:
            self._pending.pop(id, None)

    def close(self):
        self._closed = True
        self._ready_event.set()
        self._mounted_event.set()
        for future, _ in self._pending.values():
            if not future.done():
                future.set_exception(RuntimeError("Figure widget closed"))
        self._pending.clear()
        self.figure._widgets.discard(self)
        super().close()

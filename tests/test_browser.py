"""Exercise the actual shared ES module with a live native-renderer transport.

The transport is HTTP in this harness; anywidget's comm is separately tested.
This does not pretend to be a JupyterLab browser compatibility test.
"""
import base64
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import shutil
import threading

import numpy as np
from PIL import Image
import pytest

from figgy import Figure
from figgy.editor import EditorSession


def test_live_editor_select_drag_copy_and_png(tmp_path):
    pytest.importorskip("playwright")
    from playwright.sync_api import sync_playwright
    import figgy
    source = Path(figgy.__file__).parent
    with Figure(figsize=(8, 5), dpi=120, pool_bytes=8 * 1024**2) as fig:
        ax = fig.axes[0]
        ax.plot(np.linspace(0, 10, 1000), np.sin(np.linspace(0, 10, 1000)), id="signal")
        ax.set_title("Editable title")
        editor = EditorSession(fig)

        def payload():
            return json.dumps({"state": editor.snapshot(), "image": base64.b64encode(editor.image).decode()}).encode()

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_GET(self):
                if self.path == "/state":
                    data, mime = payload(), "application/json"
                elif self.path in ("/editor.js", "/editor.css"):
                    data = (source / self.path[1:]).read_bytes()
                    mime = "text/javascript" if self.path.endswith(".js") else "text/css"
                elif self.path == "/":
                    data = b'''<!doctype html><link rel="stylesheet" href="/editor.css"><div id="editor"></div>
                    <script type="module">
                    import {render} from '/editor.js';
                    let values={}, callbacks=new Map();
                    function receive(data) {values.state=data.state;values.image=Uint8Array.from(atob(data.image),c=>c.charCodeAt(0));
                      for(const key of ['change:state','change:image']) for(const cb of callbacks.get(key)||[]) cb();}
                    const model={get:key=>values[key],send:async message=>receive(await(await fetch('/command',{method:'POST',body:JSON.stringify(message)})).json()),
                      on:(key,cb)=>{if(!callbacks.has(key))callbacks.set(key,new Set());callbacks.get(key).add(cb);},
                      off:(key,cb)=>callbacks.get(key)?.delete(cb)};
                    window.editorModel=model;
                    receive(await(await fetch('/state')).json());render({model,el:document.getElementById('editor')});
                    </script>'''
                    mime = "text/html"
                else:
                    self.send_error(404); return
                self.send_response(200); self.send_header("Content-Type", mime); self.end_headers(); self.wfile.write(data)
            def do_POST(self):
                content = self.rfile.read(int(self.headers["Content-Length"]))
                editor.dispatch(json.loads(content))
                data = payload()
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(data)

        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            with sync_playwright() as playwright:
                executable = os.environ.get("BROWSER_EXECUTABLE_PATH") or shutil.which("chromium") or shutil.which("google-chrome")
                if not executable and not Path(playwright.chromium.executable_path).exists():
                    pytest.skip("install Chromium with playwright install chromium to run browser integration")
                browser = playwright.chromium.launch(**({"executable_path": executable} if executable else {}), args=["--no-sandbox"])
                context = browser.new_context(viewport={"width": 1280, "height": 800}, permissions=["clipboard-read", "clipboard-write"], accept_downloads=True)
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(f"http://127.0.0.1:{server.server_port}")
                page.locator("[data-fields] input[type=text]").fill("Browser edited title")
                page.locator("[data-fields] input[type=text]").press("Tab")
                page.wait_for_function("editorModel.get('state').code.includes('Browser edited title')")
                bounds = json.loads(fig._native.bounds_json("chart_title"))["rect"]
                rect = page.locator("canvas").bounding_box()
                x = rect["x"] + (bounds[0] + bounds[2] / 2) * rect["width"] / 960
                y = rect["y"] + (bounds[1] + bounds[3] / 2) * rect["height"] / 600
                page.mouse.move(x, y); page.mouse.down()
                page.wait_for_function("editorModel.get('state').selection === 'chart_title'")
                page.mouse.move(x + 15, y + 5, steps=3); page.mouse.up()
                page.wait_for_function("editorModel.get('state').settings.config.chart_title.offset_x > 0")
                page.locator("[data-copy]").click()
                page.wait_for_function("document.querySelector('[data-status]').textContent === 'Python code copied'")
                copied = page.evaluate("navigator.clipboard.readText()")
                assert "ax.set_title(" in copied and "Browser edited title" in copied
                assert "json.loads" not in copied
                with page.expect_download() as event:
                    page.locator("[data-save]").click()
                download = event.value
                path = tmp_path / "download.png"; download.save_as(path)
                assert Image.open(path).size == (960, 600)
                page.screenshot(path=str(tmp_path / "editor-browser.png"))
                assert not errors
                browser.close()
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=5)

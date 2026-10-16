"""A real Jupyter comm/kernel/browser fixture shared by interaction contract tests."""
from contextlib import contextmanager
from pathlib import Path
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import uuid


@contextmanager
def notebook(tmp_path, source):
    import nbformat
    from playwright.sync_api import sync_playwright
    from jupyter_client import BlockingKernelClient
    tmp_path.mkdir(parents=True, exist_ok=True)
    runtime = tmp_path / 'runtime'
    runtime.mkdir()
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    nbformat.write(nbformat.v4.new_notebook(cells=[nbformat.v4.new_code_cell(source)], metadata={
        'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'}}), tmp_path / 'check.ipynb')
    env = dict(os.environ, JUPYTER_RUNTIME_DIR=str(runtime))
    log = open(tmp_path / 'server.log', 'w')
    server = subprocess.Popen([sys.executable, '-m', 'jupyterlab', '--no-browser', '--expose-app-in-browser',
        '--ip=127.0.0.1', f'--port={port}', f'--ServerApp.root_dir={tmp_path}', '--IdentityProvider.token='],
        env=env, stdout=log, stderr=subprocess.STDOUT)
    base = f'http://127.0.0.1:{port}'
    client = None
    try:
        deadline = time.monotonic()+40
        while True:
            try:
                urllib.request.urlopen(base+'/api/status', timeout=1).close()
                break
            except Exception:
                if time.monotonic() > deadline:
                    raise RuntimeError((tmp_path/'server.log').read_text())
                time.sleep(.1)
        with sync_playwright() as p:
            browser_env = dict(os.environ)
            if os.environ.get('FIGGY_BROWSER_VK_DRIVER'):
                browser_env['VK_DRIVER_FILES'] = os.environ['FIGGY_BROWSER_VK_DRIVER']
            browser = p.chromium.launch(headless=os.environ.get('FIGGY_TEST_HEADFUL') != '1', env=browser_env,
                executable_path=os.environ.get('BROWSER_EXECUTABLE_PATH') or shutil.which('chromium'),
                args=['--no-sandbox', '--enable-unsafe-webgpu', '--use-angle=vulkan', '--enable-features=Vulkan', '--disable-vulkan-surface'])
            context = browser.new_context(viewport={'width': 1500, 'height': 1000}, permissions=['clipboard-read', 'clipboard-write'], accept_downloads=True)
            context.route('https://**/*', lambda route: route.abort())
            page = context.new_page()
            errors = []
            page.on('pageerror', lambda e: errors.append(str(e)))
            try:
                page.goto(base+'/lab/workspaces/'+uuid.uuid4().hex+'/tree/check.ipynb')
                page.locator('.jp-CodeCell .cm-content').wait_for(timeout=45000)
                page.wait_for_function('!!window.jupyterapp')
                page.evaluate('window.jupyterapp.restored')
                page.wait_for_function('!!window.jupyterapp.shell.currentWidget?.sessionContext')
                page.evaluate("""async()=>{const app=window.jupyterapp;await app.restored;const panel=app.shell.currentWidget;await panel.context.ready;await panel.sessionContext.ready;await app.commands.execute('notebook:run-all-cells');}""")
                page.wait_for_function("document.querySelector('.figgy-editor [data-status]')?.textContent==='Ready'", timeout=45000)
                with urllib.request.urlopen(base+'/api/sessions') as response:
                    session = next(s for s in json.load(response) if s['path'] == 'check.ipynb')
                # Dismiss Jupyter's first-run news prompt before canvas gestures.
                notice = page.get_by_role('button', name='No', exact=True)
                if notice.is_visible():
                    notice.click()
                client = BlockingKernelClient(connection_file=str(runtime/f"kernel-{session['kernel']['id']}.json"))
                client.load_connection_file()
                client.start_channels()

                def execute(code):
                    mid = client.execute(code)
                    messages = []
                    while True:
                        message = client.get_iopub_msg(timeout=180)
                        if message.get('parent_header', {}).get('msg_id') != mid:
                            continue
                        if message['msg_type'] == 'error':
                            raise AssertionError(message['content']['evalue'])
                        if message['msg_type'] == 'stream':
                            messages.append(message['content']['text'])
                        if message['msg_type'] == 'status' and message['content']['execution_state'] == 'idle':
                            return ''.join(messages)
                yield page, execute
                assert not errors
                assert page.locator('.figgy-error').inner_text() == ''
            except Exception:
                import traceback
                (tmp_path/'failure.txt').write_text(traceback.format_exc())
                (tmp_path/'browser-errors.json').write_text(json.dumps(errors))
                try:
                    page.screenshot(path=str(tmp_path/'failure.png'), timeout=5000)
                except Exception:
                    pass
                raise
            finally:
                context.close()
                browser.close()
    finally:
        if client:
            client.stop_channels()
        server.terminate()
        try:
            server.wait(timeout=15)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait()
        log.close()
        shutil.rmtree(runtime, ignore_errors=True)

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
    # Configure first-run announcements before Jupyter starts. Clicking the
    # transient news toast races its animation/expiry and can fail an otherwise
    # healthy chart interaction test (or leave the toast over the canvas).
    settings = tmp_path / 'settings'
    notifications = settings / '@jupyterlab' / 'apputils-extension' / 'notification.jupyterlab-settings'
    notifications.parent.mkdir(parents=True)
    notifications.write_text(json.dumps({'fetchNews': 'false', 'checkForUpdates': False}))
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    nbformat.write(nbformat.v4.new_notebook(cells=[nbformat.v4.new_code_cell(source)], metadata={
        'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'}}), tmp_path / 'check.ipynb')
    env = dict(os.environ, JUPYTER_RUNTIME_DIR=str(runtime), JUPYTERLAB_SETTINGS_DIR=str(settings))
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
                args=['--no-sandbox', '--enable-unsafe-webgpu', '--use-angle=vulkan', '--enable-features=Vulkan', '--disable-vulkan-surface',
                      '--enable-logging', f'--log-file={tmp_path / "chromium.log"}'])
            context = browser.new_context(viewport={'width': 1500, 'height': 1000}, permissions=['clipboard-read', 'clipboard-write'], accept_downloads=True)
            context.route('https://**/*', lambda route: route.abort())
            page = context.new_page()
            errors = []
            console_errors = []
            page.on('pageerror', lambda e: errors.append(e.stack or str(e)))
            page.on('console', lambda m: console_errors.append(m.text) if m.type == 'error' else None)
            page.add_init_script("""if(navigator.gpu){
                const requestAdapter=navigator.gpu.requestAdapter.bind(navigator.gpu);
                navigator.gpu.requestAdapter=async(...args)=>{
                    const adapter=await requestAdapter(...args);
                    if(adapter){const requestDevice=adapter.requestDevice.bind(adapter);
                        adapter.requestDevice=async(...args)=>{
                            const device=await requestDevice(...args);
                            device.lost.then(info=>console.error('WebGPU device lost:',info.reason,info.message));
                            return device;
                        };
                    }return adapter;
                };
            }""")
            try:
                page.goto(base+'/lab/workspaces/'+uuid.uuid4().hex+'/tree/check.ipynb')
                page.locator('.jp-CodeCell .cm-content').wait_for(timeout=45000)
                page.wait_for_function('!!window.jupyterapp')
                page.evaluate('window.jupyterapp.restored')
                page.wait_for_function('!!window.jupyterapp.shell.currentWidget?.sessionContext')
                page.evaluate("""async()=>{const app=window.jupyterapp;await app.restored;const panel=app.shell.currentWidget;await panel.context.ready;await panel.sessionContext.ready;await app.commands.execute('notebook:run-all-cells');}""")
                # Ready includes async pipeline compilation and GPU completion.
                # Cold software-GPU startup has its own budget; gesture checks
                # keep Playwright's normal timeout and strict result assertions.
                page.wait_for_function("['Ready','WebGPU failed'].includes(document.querySelector('.figgy-editor [data-status]')?.textContent)", timeout=180000)
                assert page.locator('.figgy-editor [data-status]').inner_text() == 'Ready', page.locator('.figgy-error').inner_text()
                with urllib.request.urlopen(base+'/api/sessions') as response:
                    session = next(s for s in json.load(response) if s['path'] == 'check.ipynb')
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
                (tmp_path/'console-errors.json').write_text(json.dumps(console_errors))
                try:
                    (tmp_path/'widget-state.json').write_text(json.dumps(page.evaluate("""()=>{
                        const f=document.querySelector('.figgy-editor')?.figgy;
                        return f?{stats:f.stats,state:f.snapshot()}:null;
                    }""")))
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

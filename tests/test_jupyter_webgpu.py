"""Real JupyterLab/comm/WASM/WebGPU integration. Opt in with FIGGY_TEST_JUPYTER=1."""
import json,os,shutil,socket,subprocess,sys,time,urllib.request,uuid,io
from pathlib import Path
import numpy as np
import pytest

@pytest.mark.skipif(os.environ.get('FIGGY_TEST_JUPYTER')!='1',reason='set FIGGY_TEST_JUPYTER=1 for real JupyterLab/WebGPU integration')
@pytest.mark.parametrize('auto_prepare', [True, False])
def test_jupyter_webgpu_binary_edit_sync_export(tmp_path, auto_prepare):
    pytest.importorskip('playwright');nbformat=pytest.importorskip('nbformat')
    from playwright.sync_api import sync_playwright
    from jupyter_client import BlockingKernelClient
    from PIL import Image
    runtime=tmp_path/'runtime';runtime.mkdir()
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    source='''import importlib
import numpy as np
import figgyplot as figgy
# Prove that Figure creation never initializes the kernel's native GPU.
module = importlib.import_module("figgyplot.figure")
module.NativeFigure = lambda *a: (_ for _ in ()).throw(RuntimeError("kernel GPU forbidden"))
fig, ax = figgy.subplots(backend="webgpu")
x = np.linspace(0, 10, 100_000, dtype=np.float32)
ax.plot(x, np.sin(x), id="signal")
ax.set_title("WASM title")
widget = fig.widget()
display(widget)'''.replace('widget = fig.widget()', f'widget = fig.widget(auto_prepare={auto_prepare!r})')
    samples=256 if os.environ.get('FIGGY_FUZZ_BROWSER')=='1' else 100_000
    source=source.replace('100_000',str(samples))
    nbformat.write(nbformat.v4.new_notebook(cells=[nbformat.v4.new_code_cell(source)],metadata={'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'}}),tmp_path/'check.ipynb')
    env=dict(os.environ,JUPYTER_RUNTIME_DIR=str(runtime))
    log=open(tmp_path/'server.log','w')
    server=subprocess.Popen([sys.executable,'-m','jupyterlab','--no-browser','--expose-app-in-browser','--ip=127.0.0.1',f'--port={port}',f'--ServerApp.root_dir={tmp_path}',"--IdentityProvider.token="],env=env,stdout=log,stderr=subprocess.STDOUT)
    base=f'http://127.0.0.1:{port}'
    client=None
    try:
        deadline=time.monotonic()+40
        while True:
            try:urllib.request.urlopen(base+'/api/status',timeout=1).close();break
            except Exception:
                if time.monotonic()>deadline:raise RuntimeError((tmp_path/'server.log').read_text())
                time.sleep(.1)
        with sync_playwright() as p:
            browser_env=dict(os.environ)
            if os.environ.get('FIGGY_BROWSER_VK_DRIVER'):
                browser_env['VK_DRIVER_FILES']=os.environ['FIGGY_BROWSER_VK_DRIVER']
            browser=p.chromium.launch(headless=os.environ.get('FIGGY_TEST_HEADFUL')!='1',env=browser_env,executable_path=os.environ.get('BROWSER_EXECUTABLE_PATH') or shutil.which('chromium'),args=['--no-sandbox','--enable-unsafe-webgpu','--use-angle=vulkan','--enable-features=Vulkan','--disable-vulkan-surface'])
            context=browser.new_context(viewport={'width':1500,'height':1000},permissions=['clipboard-read','clipboard-write'],accept_downloads=True)
            context.route('https://**/*',lambda route:route.abort())
            page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            page.add_init_script('''if(navigator.gpu){window.figgyAdapterRequests=0;const original=navigator.gpu.requestAdapter.bind(navigator.gpu);navigator.gpu.requestAdapter=(...args)=>{window.figgyAdapterRequests++;return original(...args);};}''')
            page.goto(base+'/lab/workspaces/'+uuid.uuid4().hex+'/tree/check.ipynb')
            page.locator('.jp-CodeCell .cm-content').filter(has_text='kernel GPU forbidden').wait_for(timeout=45000)
            page.wait_for_function('!!window.jupyterapp')
            page.evaluate('''async()=>{const app=window.jupyterapp;await app.restored;const panel=app.shell.currentWidget;await panel.context.ready;await panel.sessionContext.ready;await app.commands.execute('notebook:run-all-cells');}''')
            try:
                page.wait_for_function("document.querySelector('.figgy-editor [data-status]')?.textContent.includes(" + ("'Ready'" if auto_prepare else "'Not prepared'") + ")",timeout=30000)
            except Exception:
                page.screenshot(path=str(tmp_path/'failed.png'))
                raise AssertionError(str(page.locator('.jp-OutputArea').all_text_contents()) + str(errors))
            with urllib.request.urlopen(base+'/api/sessions') as response:session=next(s for s in json.load(response) if s['path']=='check.ipynb')
            client=BlockingKernelClient(connection_file=str(runtime/f"kernel-{session['kernel']['id']}.json"));client.load_connection_file();client.start_channels()
            def execute(code):
                id=client.execute(code);messages=[]
                while True:
                    message=client.get_iopub_msg(timeout=180)
                    if message.get('parent_header',{}).get('msg_id')!=id:continue
                    if message['msg_type']=='error':raise AssertionError(message['content']['evalue'])
                    if message['msg_type']=='stream':messages.append(message['content']['text'])
                    if message['msg_type']=='status' and message['content']['execution_state']=='idle':return ''.join(messages)
            if not auto_prepare:
                assert page.evaluate('window.figgyAdapterRequests') == 0
                assert page.locator('[data-fit]').is_disabled()
                page.locator('.figgy-editor canvas').dispatch_event('wheel', {'deltaY':10})
                assert page.locator('.figgy-error').inner_text() == ''
                # Settings can change while GPU preparation is deferred.
                execute("ax.set_title('Deferred title')")
            report=json.loads(execute("import json; print(json.dumps(await fig.prepare_async()))"))
            assert report['ready'] and report['backend']=='webgpu' and report['stages']
            assert report['persistent_cache_supported'] is False and report['elapsed_ms'] > 0
            page.wait_for_function("document.querySelector('.figgy-editor [data-status]')?.textContent.includes('Ready')")
            assert page.evaluate('window.figgyAdapterRequests') >= 1
            root="document.querySelector('.figgy-editor').figgy"
            if not auto_prepare:
                assert page.evaluate(root+".snapshot().config.chart_title.text.segments.map(s=>s.text).join('')") == 'Deferred title'
            stats=page.evaluate(root+'.stats')
            assert stats['binary_upload_bytes']==samples*8 and stats['column_uploads']==2 and stats['png_exports']==0
            assert 'True' in execute("print(widget.status == 'ready' and not fig._native.columns and not widget.columns)")
            page.locator('[data-properties]').click()
            page.locator('[data-fields] input[data-property=text]').fill('WebGPU edited title');page.locator('[data-fields] input[data-property=text]').press('Tab')
            page.wait_for_function(root+".snapshot().config.chart_title.text.segments.map(s=>s.text).join('') === 'WebGPU edited title'")
            assert 'WebGPU edited title' in execute("await fig.sync(); print(fig.to_code())")
            # Range edits cross the Python/browser boundary as plain SSOT
            # fields; they preserve ticks and never introduce a lock marker.
            execute("fig.configure(config={'bottom_x': {'major_spacing': 1.25, 'minor_count': 1}})")
            page.wait_for_function(root+".snapshot().config.bottom_x.major_spacing === 1.25")
            before_range=page.evaluate(root+'.snapshot().config')
            page.locator('[data-target]').select_option('axis_bottom')
            page.locator('[data-fields] input[data-property=min]').fill('2')
            page.locator('[data-fields] input[data-property=min]').press('Tab')
            page.wait_for_function(root+".snapshot().config.bottom_x.min === 2")
            after_range=json.loads(execute("await fig.sync(); print(json.dumps(fig.get_settings()['config']))"))
            before_range['bottom_x']['min']=2
            assert after_range == before_range
            # The explicit Fit helper still derives all bounds and ticks.
            page.locator('[data-fit]').click()
            page.wait_for_function(root+".snapshot().config.bottom_x.min < 0")
            execute("await fig.sync(); c=fig.get_settings()['config']['bottom_x']; assert c['min'] < 0 and c['minor_count'] == 4 and c['major_spacing'] != 1.25")
            # GPU picker and layout/drag stay inside the browser. The kernel has no GPU.
            canvas=page.locator('.figgy-editor canvas');rect=canvas.bounding_box()
            page.mouse.move(rect['x']+rect['width']/2,rect['y']+12);page.mouse.down()
            page.mouse.move(rect['x']+rect['width']/2+20,rect['y']+18,steps=4);page.mouse.up()
            page.wait_for_function(root+'.snapshot().config.chart_title.offset_x > 0')
            execute("await fig.sync(); assert fig.get_settings()['config']['chart_title']['offset_x'] > 0")
            page.locator('[data-target]').select_option('signal');page.locator('[data-fields] input[type=color]').fill('#ff0000');page.locator('[data-fields] input[type=color]').dispatch_event('change')
            execute("await fig.sync(); assert fig.get_settings()['series'][0]['render_type']['Line']['line']['line_color']['r'] == 1")
            # Inspect the actual composited canvas, not only export output.
            page.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
            canvas_pixels=np.asarray(Image.open(io.BytesIO(canvas.screenshot())).convert('RGB'))
            assert np.count_nonzero((canvas_pixels[:,:,0]>150)&(canvas_pixels[:,:,1]<100)&(canvas_pixels[:,:,2]<100))>100
            # Initial picker hit at a real line point, through the actual browser GPU API.
            picked=page.evaluate('''async()=>{const f=document.querySelector('.figgy-editor').figgy,c=f.snapshot().config,r=(await f.decorations()).data_area.rect;return await f.pick(r[0]+(0-c.bottom_x.min)/(c.bottom_x.max-c.bottom_x.min)*r[2],r[1]+c.left_y.max/(c.left_y.max-c.left_y.min)*r[3],12);}''')
            assert picked is not None
            if auto_prepare and os.environ.get('FIGGY_FUZZ_BROWSER') == '1':
                from scripts.check_randomized import mutate
                import random
                rng=random.Random(9610)
                rejected=accepted=0
                page.locator('.figgy-properties details').first.evaluate('(el)=>el.open=true')
                before_stats=page.evaluate(root+'.stats')
                for index in range(300):
                    original=page.evaluate(root+'.snapshot()')
                    mutation, detail=mutate(original,rng)
                    (tmp_path/'fuzz-last.json').write_text(json.dumps({'index':index,'mutation':detail,'settings':mutation}))
                    page.evaluate("document.querySelector('.figgy-error').textContent='' ")
                    page.locator('[data-settings]').fill(json.dumps(mutation))
                    page.locator('[data-apply]').click()
                    page.evaluate('''async()=>{const f=document.querySelector('.figgy-editor').figgy;await Promise.race([(async()=>{await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));await f.flush();})(),new Promise((_,reject)=>setTimeout(()=>reject(Error('fuzz synchronization timed out')),5000))]);}''')
                    actual=page.evaluate(root+'.snapshot()')
                    message=page.locator('.figgy-error').inner_text()
                    if message:
                        rejected+=1
                        assert actual==original,(index,detail,message)
                    else:accepted+=1
                    # Restore through the real JSON editor + kernel revision handshake.
                    page.locator('[data-settings]').fill(json.dumps(original));page.locator('[data-apply]').click()
                    page.evaluate('''async()=>{const f=document.querySelector('.figgy-editor').figgy;await Promise.race([f.flush(),new Promise((_,reject)=>setTimeout(()=>reject(Error('fuzz restore timed out')),5000))]);}''')
                    assert page.locator('.figgy-error').inner_text()=='',(index,detail,'error survived a successful restore')
                    assert not errors,(index,detail,errors)
                after_stats=page.evaluate(root+'.stats')
                assert rejected>200 and accepted>0
                assert after_stats['column_uploads']==before_stats['column_uploads']==2
                assert after_stats['binary_upload_bytes']==before_stats['binary_upload_bytes']==samples*8
                assert after_stats['png_exports']==before_stats['png_exports']==0
                expected=page.evaluate(root+'.snapshot()')
                actual=json.loads(execute("await fig.sync(); print(json.dumps(fig.get_settings()))"))
                assert actual==expected
                (tmp_path/'fuzz-browser.json').write_text(json.dumps({'seed':9610,'mutations':300,'rejected':rejected,'accepted':accepted,'browser_errors':errors,'before':before_stats,'after':after_stats},indent=2))
            expected_code=execute("await fig.sync(); print(fig.to_code(), end='')")
            page.locator('[data-copy]').click()
            page.wait_for_function("expected=>document.querySelector('.figgy-editor [data-code]').value===expected",arg=expected_code)
            copied=page.evaluate('navigator.clipboard.readText()')
            assert copied==expected_code and 'ax.set_title(' in copied
            execute('exec('+repr(copied)+')')
            assert page.evaluate(root+'.stats.png_exports')==0
            assert page.evaluate(root+'.stats.column_uploads')==2
            with page.expect_download() as download:page.locator('[data-save]').click()
            download.value.save_as(tmp_path/'download.png');assert Image.open(tmp_path/'download.png').size==(960,600)
            path=tmp_path/'kernel-export.png';execute(f"await fig.savefig_async({str(path)!r})")
            assert Image.open(path).size==(960,600)
            # A Python edit updates browser state without replaying the columns.
            execute("ax.set_title('Python title')")
            page.wait_for_function(root+".snapshot().config.chart_title.text.segments.map(s=>s.text).join('') === 'Python title'")
            final=page.evaluate(root+'.stats');assert final['column_uploads']==2 and final['png_exports']==2
            (tmp_path/'browser-stats.json').write_text(json.dumps(final,indent=2))
            page.screenshot(path=str(tmp_path/'webgpu.png'));assert not errors
            assert page.locator('.figgy-error').inner_text()==''
            if not auto_prepare:
                count=page.evaluate('window.figgyAdapterRequests')
                # Display messages from a direct kernel client have no notebook
                # cell parent. Execute this new output through JupyterLab itself.
                page.evaluate('''async()=>{const app=window.jupyterapp,panel=app.shell.currentWidget;panel.content.model.sharedModel.insertCell(1,{cell_type:'code',source:"other, other_ax = figgy.subplots(backend='webgpu'); other_ax.plot([0, 1], [1, 0]); other_widget = other.widget(auto_prepare=False); display(other_widget)",metadata:{}});panel.content.activeCellIndex=1;await app.commands.execute('notebook:run-cell');}''')
                page.wait_for_function("document.querySelectorAll('.figgy-editor').length === 2")
                execute("other.close()")
                page.wait_for_function("document.querySelectorAll('.figgy-editor').length === 1")
                assert page.evaluate('window.figgyAdapterRequests') == count
            browser.close()
    finally:
        if client:client.stop_channels()
        server.terminate()
        try:server.wait(timeout=15)
        except subprocess.TimeoutExpired:server.kill();server.wait()
        log.close()

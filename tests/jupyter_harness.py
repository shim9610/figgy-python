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


# Diagnostic observers wrap only GPU operations already requested by the host.
# A completed submission is one observed through an existing fence; mapAsync
# completion alone does not advance that counter or prove later work is idle.
GPU_TRACE_INIT = r"""(() => {
    const limit=400, events=[], queues=new WeakMap(), buffers=new WeakMap();
    const work=window.figgyGPUWork={submitted:0,completed:0,completedCanvas:null};
    const trace=window.figgyBrowserTrace={events,hostStages:[],dropped:0,adapters:[],devices:[],queues:[],limit};
    const record=(kind,details={})=>{
        try { events.push({t:performance.now(),kind,...details});
            if(events.length>limit){events.shift();trace.dropped++;}
        } catch (_) { /* Diagnostics must never change host behavior. */ }
    };
    window.__figgyTrace=(stage,details={})=>{
        record('host',{stage,...details});
        if(/^(request|prepare|ready_frame|display_wait|export|response|surface)\./.test(stage)){
            trace.hostStages.push({t:performance.now(),stage,...details});
            if(trace.hostStages.length>100)trace.hostStages.shift();
        }
    };
    window.figgyDiagnosticEvent=record;
    record('instrumented',{timeOrigin:performance.timeOrigin});
    if(!navigator.gpu){record('gpu-unavailable');return;}
    const submit=GPUQueue.prototype.submit,done=GPUQueue.prototype.onSubmittedWorkDone;
    let fenceId=0,bufferId=0,deviceId=0,adapterId=0;
    GPUQueue.prototype.submit=function(...args){
        const q=queues.get(this),start=performance.now();
        try {const value=submit.apply(this,args);
            if(q){q.submitted++;work.submitted++;
                const canvas=document.querySelector('.figgy-editor canvas');
                q.canvas=canvas?[canvas.width,canvas.height]:null;
                q.globalSubmitted=work.submitted;
                record('submit',{queue:q.id,submission:q.submitted,globalSubmission:work.submitted,canvas:q.canvas,cpuMs:performance.now()-start});
            }return value;
        }catch(error){record('submit-error',{queue:q?.id,error:String(error)});throw error;}
    };
    GPUQueue.prototype.onSubmittedWorkDone=function(...args){
        const q=queues.get(this),id=++fenceId,submission=q?.submitted,globalSubmission=q?.globalSubmitted,canvas=q?.canvas;
        record('fence-start',{id,queue:q?.id,submission});
        let promise;try{promise=done.apply(this,args);}catch(error){record('fence-error',{id,error:String(error)});throw error;}
        if(q)q.pendingFences++;
        return promise.then(value=>{
            if(q){q.pendingFences--;q.completed=Math.max(q.completed,submission);work.completed=Math.max(work.completed,globalSubmission||0);work.completedCanvas=canvas;}
            record('fence-end',{id,queue:q?.id,submission});return value;
        },error=>{if(q)q.pendingFences--;record('fence-error',{id,queue:q?.id,error:String(error)});throw error;});
    };
    const map=GPUBuffer.prototype.mapAsync;
    GPUBuffer.prototype.mapAsync=function(...args){
        let id=buffers.get(this);if(!id){id=++bufferId;buffers.set(this,id);}
        record('map-start',{id,size:this.size,label:this.label,mode:args[0]});
        let promise;try{promise=map.apply(this,args);}catch(error){record('map-error',{id,error:String(error)});throw error;}
        return promise.then(value=>{record('map-end',{id});return value;},error=>{record('map-error',{id,error:String(error)});throw error;});
    };
    for(const name of ['getMappedRange','unmap']){
        const original=GPUBuffer.prototype[name];
        GPUBuffer.prototype[name]=function(...args){
            record(name,{id:buffers.get(this),size:this.size});
            try{return original.apply(this,args);}catch(error){record(name+'-error',{id:buffers.get(this),error:String(error)});throw error;}
        };
    }
    const requestAdapter=navigator.gpu.requestAdapter.bind(navigator.gpu);
    navigator.gpu.requestAdapter=async(...args)=>{
        record('adapter-request',{options:args[0]});
        let adapter;try{adapter=await requestAdapter(...args);}catch(error){record('adapter-error',{error:String(error)});throw error;}
        if(!adapter){record('adapter-missing');return adapter;}
        const id=++adapterId,info=adapter.info;
        const description={id,vendor:info?.vendor,architecture:info?.architecture,device:info?.device,description:info?.description,
            isFallbackAdapter:info?.isFallbackAdapter??adapter.isFallbackAdapter};
        if(trace.adapters.length<16)trace.adapters.push(description);record('adapter-ready',description);
        const requestDevice=adapter.requestDevice.bind(adapter);
        adapter.requestDevice=async(...args)=>{
            record('device-request',{adapter:id,requiredFeatures:args[0]?.requiredFeatures,requiredLimits:args[0]?.requiredLimits});
            let device;try{device=await requestDevice(...args);}catch(error){record('device-error',{adapter:id,error:String(error)});throw error;}
            const q={id:++deviceId,submitted:0,completed:0,pendingFences:0,canvas:null,globalSubmitted:0};queues.set(device.queue,q);
            const metadata={id:q.id,adapter:id,label:device.label,features:Array.from(device.features)};
            if(trace.devices.length<16)trace.devices.push(metadata);if(trace.queues.length<16)trace.queues.push(q);record('device-ready',metadata);
            device.addEventListener('uncapturederror',event=>record('gpu-error',{device:q.id,error:String(event.error)}));
            device.lost.then(info=>{record('device-lost',{device:q.id,reason:info.reason,message:info.message});console.error('WebGPU device lost:',info.reason,info.message);},error=>record('device-lost-error',{device:q.id,error:String(error)}));
            return device;
        };return adapter;
    };
})()"""

DIAGNOSTIC_SNAPSHOT = r"""()=>{
    const now=performance.now(),root=document.querySelector('.figgy-editor'),f=root?.figgy;
    const canvas=root?.querySelector('canvas'),rect=canvas?.getBoundingClientRect(),gate=window.figgyPreparationGate;
    const result={now,timeOrigin:performance.timeOrigin,visibility:document.visibilityState,focused:document.hasFocus(),
        status:root?.querySelector('[data-status]')?.textContent,gpu_work:window.figgyGPUWork,trace:window.figgyBrowserTrace,
        canvas:canvas?{width:canvas.width,height:canvas.height,css:{x:rect.x,y:rect.y,width:rect.width,height:rect.height},dpr:devicePixelRatio}:null,
        preparation_gate:gate?{armedAt:gate.armedAt,entered:gate.entered,enteredAt:gate.enteredAt,enteredCount:gate.enteredCount,
            releasedAt:gate.releasedAt,gpuCompletedAt:gate.gpuCompletedAt,durationMs:(gate.releasedAt??now)-gate.armedAt}:null};
    if(window.figgyTiming)result.timing=window.figgyTiming.snapshot();
    // Each independent read survives a borrowed/unavailable WASM snapshot.
    for(const [key,read] of Object.entries({stats:()=>f?.stats,host:()=>typeof f?.diagnostics==='function'?f.diagnostics():f?.diagnostics,state:()=>f?.snapshot()})){
        try{result[key]=read();}catch(error){result[key+'_error']=String(error);}
    }return result;
}"""


def save_browser_diagnostics(page, folder, browser_info, outcome, errors, console_errors, kernel_executions=None):
    """Best effort, including success paths; never replace the test exception."""
    result = {'outcome': outcome, 'browser': browser_info, 'kernel_executions': kernel_executions or []}
    try:
        result.update(page.evaluate(DIAGNOSTIC_SNAPSHOT))
    except Exception as error:
        result['collection_error'] = repr(error)
    result['browser_errors'] = errors
    result['console_errors'] = console_errors
    for name, value in [('diagnostics.json', result), ('widget-state.json', result),
                        ('browser-errors.json', errors), ('console-errors.json', console_errors)]:
        try:
            (folder/name).write_text(json.dumps(value, default=str))
        except Exception as error:
            print(f'Figgy diagnostic write failed ({name}): {error}', file=sys.stderr)
    if result.get('timing'):
        from browser_timing import timing_summary
        print('FIGGY TIMING DIAGNOSTICS '+json.dumps({'outcome':outcome,'browser':browser_info,'timing':timing_summary(result['timing'])}),flush=True)
    if outcome == 'failed':
        trace = result.get('trace') or {}
        summary = {key: result.get(key) for key in ('browser', 'status', 'host', 'gpu_work', 'preparation_gate', 'state_error', 'collection_error')}
        summary.update(queues=trace.get('queues'), adapters=trace.get('adapters'),
                       last_host_stages=(trace.get('hostStages') or [])[-12:],
                       last_events=(trace.get('events') or [])[-16:], kernel_executions=(kernel_executions or [])[-5:])
        if result.get('timing'):
            timing=result['timing'];summary['timing']={key:timing.get(key) for key in ('raf','timer','geometry','pipelines','fences')}
            summary['timing']['last_samples']=(timing.get('samples') or [])[-8:]
        try:
            print('FIGGY FAILURE DIAGNOSTICS ' + json.dumps(summary, default=str), flush=True)
        except Exception:
            pass
    return result


def button_point_without_frames(page, selector):
    """Validate a stable, unobscured button using DOM timers, independent of RAF."""
    page.locator(selector).evaluate("button=>button.scrollIntoView({behavior:'instant',block:'nearest',inline:'nearest'})")
    point = page.wait_for_function("""(()=>{
        let previous;
        return selector=>{
            const button=document.querySelector(selector);
            if(!button || !button.matches('button') || button.disabled)return false;
            const rect=button.getBoundingClientRect(),style=getComputedStyle(button);
            const geometry=[rect.x,rect.y,rect.width,rect.height];
            const stable=previous && geometry.every((value,i)=>Math.abs(value-previous[i])<.01);
            previous=geometry;
            if(!stable || rect.width<=0 || rect.height<=0 || style.visibility!=='visible' ||
                style.display==='none' || rect.left<0 || rect.top<0 || rect.right>innerWidth || rect.bottom>innerHeight)return false;
            const points=[[rect.x+rect.width/2,rect.y+rect.height/2],
                [rect.x+rect.width/2,rect.top+1],[rect.x+rect.width/2,rect.bottom-1],
                [rect.left+1,rect.y+rect.height/2],[rect.right-1,rect.y+rect.height/2]];
            return points.every(([x,y])=>document.elementFromPoint(x,y)?.closest('button')===button)?points[0]:false;
        };
    })()""", arg=selector, polling=100)
    try:
        return point.json_value()
    finally:
        point.dispose()


def click_button(page, selector):
    """Use real mouse input after DOM actionability checks, without awaiting RAF.

    Slow GPU presentation may withhold RAF while the UI and timers remain live.
    The same 30 s default deadline, disabled/visibility/obstruction checks and
    post-input behavioral assertions still apply.
    """
    x, y = button_point_without_frames(page, selector)
    page.evaluate("selector=>window.figgyDiagnosticEvent?.('button.actionable',{selector})", selector)
    page.mouse.click(x, y)
    page.evaluate("selector=>window.figgyDiagnosticEvent?.('button.input_sent',{selector})", selector)


@contextmanager
def notebook(tmp_path, source, *, allow_closed=False, initial_views=1):
    import nbformat
    from playwright.sync_api import sync_playwright
    from jupyter_client import BlockingKernelClient
    tmp_path.mkdir(parents=True, exist_ok=True)
    started=time.monotonic();timeline=[]
    def phase(stage):
        timeline.append({'stage':stage,'elapsed_seconds':time.monotonic()-started})
        try:(tmp_path/'harness-timing.json').write_text(json.dumps(timeline))
        except OSError:pass  # A diagnostic must never replace a test failure.
    phase('start')
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
    phase('server-started')
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
        phase('server-ready')
        with sync_playwright() as p:
            browser_env = dict(os.environ)
            browser_args = ['--no-sandbox', '--enable-unsafe-webgpu', '--use-angle=vulkan', '--enable-features=Vulkan', '--disable-vulkan-surface',
                            '--enable-logging', f'--log-file={tmp_path / "chromium.log"}']
            if os.environ.get('FIGGY_BROWSER_VK_DRIVER'):
                browser_env['VK_DRIVER_FILES'] = os.environ['FIGGY_BROWSER_VK_DRIVER']
                # Cold SwiftShader compilation can exceed Chromium's GPU watchdog
                # budget on CI (raw POSIX exit 512 = RESULT_CODE_HUNG). Keep the
                # watchdog enabled, aligned with the existing startup deadline.
                browser_args.append('--gpu-watchdog-timeout-seconds=180')
            executable = os.environ.get('BROWSER_EXECUTABLE_PATH') or shutil.which('chromium')
            phase('browser-launch')
            browser = p.chromium.launch(headless=os.environ.get('FIGGY_TEST_HEADFUL') != '1', env=browser_env,
                executable_path=executable, args=browser_args)
            phase('browser-launched')
            driver = os.environ.get('FIGGY_BROWSER_VK_DRIVER')
            browser_info = {
                'version': browser.version,
                'executable': executable or p.chromium.executable_path,
                'vulkan_driver': Path(driver).name if driver else None,
                'headless': os.environ.get('FIGGY_TEST_HEADFUL') != '1',
                'args': browser_args,
            }
            if os.environ.get('FIGGY_TEST_TIMING') == '1':
                quota=Path('/sys/fs/cgroup/cpu.max')
                browser_info['host']={'cpus':os.cpu_count(),'affinity':len(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else None,
                    'cpu_quota':quota.read_text().strip() if quota.exists() else None}
            (tmp_path/'browser-info.json').write_text(json.dumps(browser_info))
            context = browser.new_context(viewport={'width': 1500, 'height': 1000}, permissions=['clipboard-read', 'clipboard-write'], accept_downloads=True)
            context.route('https://**/*', lambda route: route.abort())
            page = context.new_page()
            errors = []
            console_errors = []
            page.on('pageerror', lambda e: errors.append(e.stack or str(e)))
            page.on('console', lambda m: console_errors.append(m.text) if m.type == 'error' else None)
            page.add_init_script(GPU_TRACE_INIT)
            if os.environ.get('FIGGY_TEST_TIMING') == '1':
                from browser_timing import TIMING_INIT
                page.add_init_script(TIMING_INIT)
            outcome = 'failed'
            diagnostics_saved = False
            kernel_executions = []
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
                page.wait_for_function("(count)=>{const states=Array.from(document.querySelectorAll('.figgy-editor [data-status]'));return states.length===count && states.every(s=>['Ready','WebGPU failed'].includes(s.textContent));}", arg=initial_views, timeout=180000)
                assert page.locator('.figgy-editor [data-status]').all_text_contents() == ['Ready']*initial_views, page.locator('.figgy-error').all_text_contents()
                phase('views-ready')
                with urllib.request.urlopen(base+'/api/sessions') as response:
                    session = next(s for s in json.load(response) if s['path'] == 'check.ipynb')
                client = BlockingKernelClient(connection_file=str(runtime/f"kernel-{session['kernel']['id']}.json"))
                client.load_connection_file()
                client.start_channels()

                def execute(code):
                    started = time.monotonic()
                    entry = {'started_unix': time.time(), 'characters': len(code), 'outcome': 'pending'}
                    kernel_executions.append(entry)
                    del kernel_executions[:-40]
                    try:
                        mid = client.execute(code)
                        entry['message_id'] = mid
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
                                entry['outcome'] = 'passed'
                                return ''.join(messages)
                    except Exception:
                        entry['outcome'] = 'failed'
                        raise
                    finally:
                        entry['duration_ms'] = (time.monotonic()-started)*1000
                phase('test-start')
                yield page, execute
                phase('test-end')
                assert not errors
                if allow_closed:
                    assert all(value=='' for value in page.locator('.figgy-error').all_text_contents())
                else:
                    assert page.locator('.figgy-error').inner_text() == ''
                outcome = 'passed'
            except Exception:
                import traceback
                try:
                    (tmp_path/'failure.txt').write_text(traceback.format_exc())
                except Exception as error:
                    print(f'Figgy failure traceback write failed: {error}', file=sys.stderr)
                save_browser_diagnostics(page, tmp_path, browser_info, outcome, errors, console_errors, kernel_executions)
                diagnostics_saved = True
                # Preserve failure-time metadata before attempting a screenshot,
                # which can itself time out while rendering is stalled.
                try:
                    page.screenshot(path=str(tmp_path/'failure.png'), timeout=5000)
                except Exception:
                    pass
                raise
            finally:
                phase('diagnostics-start')
                if not diagnostics_saved:
                    save_browser_diagnostics(page, tmp_path, browser_info, outcome, errors, console_errors, kernel_executions)
                phase('diagnostics-end')
                context.close()
                phase('context-closed')
                browser.close()
                phase('browser-closed')
    finally:
        if client:
            client.stop_channels()
        phase('server-stop')
        server.terminate()
        try:
            server.wait(timeout=15)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait()
        phase('server-stopped')
        if os.environ.get('FIGGY_TEST_TIMING')=='1':
            print('FIGGY HARNESS TIMING '+json.dumps(timeline),flush=True)
        log.close()
        shutil.rmtree(runtime, ignore_errors=True)

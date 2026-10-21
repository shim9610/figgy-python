"""Measure strict local layout bounds without changing production code or CI.

Run against an installed wheel on a real X11 display. Failures are observations,
not a retry-to-pass gate. JSONL preserves every sample before summarization.
"""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'tests'))


def margins(rect, clip):
    x, y, w, h = rect
    a, b, cw, ch = clip
    values = dict(left=x-a, top=y-b, right=a+cw-x-w, bottom=b+ch-y-h)
    return dict(margins=values, strict_inside=min(values.values()) >= 0,
                original_1px_inside=min(values.values()) >= -1)


def xywh(rect):
    return [rect[k] for k in ('x', 'y', 'width', 'height')]


def emit(output, row):
    with (output / 'measurements.jsonl').open('a') as stream:
        stream.write(json.dumps(row, default=str) + '\n')


def provenance(output):
    import figgyplot
    installed = Path(figgyplot.__file__).parent
    assets = {}
    for name in ('webgpu.js', 'editor.css', '_native.abi3.so'):
        path = installed / name
        if path.exists():
            source = REPO / 'python' / 'figgyplot' / name
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            assets[name] = dict(sha256=digest, bytes=path.stat().st_size,
                               source_matches=source.exists() and source.read_bytes() == path.read_bytes())
    data = dict(commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip(),
                measurement_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                platform=platform.platform(), python=sys.version, package=str(installed),
                package_version=importlib.metadata.version('figgyplot'),
                playwright=importlib.metadata.version('playwright'), assets=assets,
                display=os.environ.get('DISPLAY'), native_scale_override=os.environ.get('WINIT_X11_SCALE_FACTOR'),
                contract='No bounds-based waiting, tolerance change, functional fix or CI change.')
    (output / 'environment.json').write_text(json.dumps(data, indent=2))


BROWSER_SNAPSHOT = r"""() => {
    const root=document.querySelector('.figgy-editor');
    const nodes=Object.fromEntries(['canvas','.figgy-stage','.figgy-inline-text','[data-inline-text]','.figgy-inline-text small'].map(k=>{
        const e=root.querySelector(k),r=e.getBoundingClientRect(),s=getComputedStyle(e);
        return [k,{rect:r.toJSON(),display:s.display,fontSize:s.fontSize,lineHeight:s.lineHeight,
            hidden:e.hidden,clientHeight:e.clientHeight,scrollHeight:e.scrollHeight,
            position:s.position,left:s.left,top:s.top,width:s.width,height:s.height,
            offsetParent:e.offsetParent?.className}];
    }));
    const canvas=root.querySelector('canvas'),input=root.querySelector('[data-inline-text]');
    const c=nodes.canvas.rect,dpr=devicePixelRatio;
    return {now:performance.now(),wall:Date.now(),viewport:[innerWidth,innerHeight,dpr],nodes,
        backing:[canvas.width,canvas.height],backingMatches:canvas.width===Math.max(1,Math.round(c.width*dpr))&&canvas.height===Math.max(1,Math.round(c.height*dpr)),
        focus:document.activeElement===input,value:input.value,selection:[input.selectionStart,input.selectionEnd],
        resizeEvents:window.figgyValidityResizeEvents,
        documentWidth:root.figgy.snapshot().config.chart_area.width,
        modelFont:root.figgy.snapshot().config.annotations.items[0]?.kind.Text.text.font_size,
        host:root.figgy.diagnostics(),stats:root.figgy.stats};
}"""


def browser_settle(page, requested, changed):
    """Record the transition; settle on geometry, never on passing bounds.

    Requires the new viewport resize event when its dimensions changed, matching
    physical backing size, and three equal geometry observations on DOM timers.
    Invalid geometry is allowed to stabilize and is then reported as invalid.
    """
    start = time.monotonic()
    history, previous, stable = [], None, 0
    while time.monotonic()-start < 30:  # Existing Playwright default, unchanged.
        row = page.evaluate(BROWSER_SNAPSHOT)
        row['elapsed_ms'] = (time.monotonic()-start)*1000
        history.append(row)
        signature = (row['viewport'], row['backing'],
                     [n['rect'] for n in row['nodes'].values()])
        stable = stable+1 if signature == previous else 1
        previous = signature
        event_seen = not changed or bool(row['resizeEvents'])
        if row['viewport'] == list(requested) and row['backingMatches'] and event_seen and stable >= 3:
            return dict(settled=True, elapsed_ms=row['elapsed_ms'], history=history, final=row)
        page.wait_for_timeout(20)
    return dict(settled=False, elapsed_ms=(time.monotonic()-start)*1000, history=history, final=history[-1])


def browser_measure(output):
    from jupyter_harness import notebook
    source = """import figgyplot as fg
fig,ax=fg.subplots(backend='webgpu')
ax.plot([0,1,2],[1,3,2])
ax.text(.5,.5,'Probe',coords='ratio',fontsize=12,id='probe')
display(fig.widget())
"""
    payloads = {'one': 'Short', 'two': 'First\nSecond',
                'eight': '\n'.join(f'Line {n}' for n in range(1, 9)),
                'wrapped': 'Pressure 10⁻⁶ Torr / μm °C ' * 8}
    sizes = [(1500, 1000), (1200, 900), (980, 820), (800, 600), (640, 600)]
    with notebook(output / 'notebook', source) as (page, execute):
        session = page.context.new_cdp_session(page)
        page.evaluate("""()=>{
            window.figgyValidityResizeEvents=[];
            addEventListener('resize',()=>window.figgyValidityResizeEvents.push({now:performance.now(),viewport:[innerWidth,innerHeight]}));
        }""")
        failures_saved = set()
        for dpr in (1, 1.25, 2):
            fonts = (10, 16, 32, 72) if dpr == 1 else (16,)
            for font in fonts:
                for anchor in ((.5, .5), (.95, .95)):
                    # Begin each independent draft in the same large viewport.
                    session.send('Emulation.setDeviceMetricsOverride', dict(width=1500, height=1000, deviceScaleFactor=dpr, mobile=False))
                    execute("state=fig.get_settings();item=state['config']['annotations']['items'][0];"
                            f"item['kind']['Text']['anchor']={{'Ratio':{{'x':{anchor[0]},'y':{anchor[1]}}}}};"
                            f"item['kind']['Text']['text']['font_size']={font};fig.apply_settings(state);print('updated')")
                    page.wait_for_function(f"(()=>{{const t=document.querySelector('.figgy-editor').figgy.snapshot().config.annotations.items[0].kind.Text;return t.text.font_size==={font}&&t.anchor.Ratio.x==={anchor[0]}&&t.anchor.Ratio.y==={anchor[1]};}})()", polling=20)
                    page.locator('canvas').scroll_into_view_if_needed()
                    entries = page.evaluate("document.querySelector('.figgy-editor').figgy.annotations()")
                    if not entries:
                        emit(output, dict(host='browser', phase='open', dpr=dpr, font=font, anchor=anchor,
                                          error='No annotation geometry after document update', annotations=entries))
                        continue
                    r = entries[0]['rect']
                    point = page.locator('canvas').evaluate("(c,p)=>{const r=c.getBoundingClientRect();return [r.x+p[0]*r.width/c.width,r.y+p[1]*r.height/c.height]}", [r[0]+8, r[1]+6])
                    page.mouse.dblclick(*point)
                    entry = page.locator('[data-inline-text]')
                    try:
                        entry.wait_for(state='visible', timeout=5000)
                    except Exception as error:
                        emit(output, dict(host='browser', phase='open', dpr=dpr, font=font, anchor=anchor,
                                          error=str(error), annotations=entries, point=point))
                        continue
                    for payload_name, payload in payloads.items():
                        entry.fill(payload)
                        for width, height in sizes:
                            before = page.evaluate('[innerWidth,innerHeight,devicePixelRatio]')
                            page.evaluate('window.figgyValidityResizeEvents=[]')
                            requested = [width, height, dpr]
                            session.send('Emulation.setDeviceMetricsOverride', dict(width=width, height=height, deviceScaleFactor=dpr, mobile=False))
                            result = browser_settle(page, requested, before[:2] != requested[:2])
                            final = result['final']
                            canvas = xywh(final['nodes']['canvas']['rect'])
                            tests = {name: margins(xywh(final['nodes'][selector]['rect']), canvas)
                                     for name, selector in [('input', '[data-inline-text]'), ('box', '.figgy-inline-text'), ('hint', '.figgy-inline-text small')]}
                            row = dict(host='browser', phase='bounds', dpr=dpr, font=font, anchor=anchor,
                                       payload=payload_name, requested=requested, tests=tests, **result)
                            emit(output, row)
                            key = 'pass' if tests['box']['strict_inside'] else 'fail'
                            if key not in failures_saved:
                                page.screenshot(path=str(output / f'browser-{key}.png'), timeout=5000)
                                failures_saved.add(key)
                    entry.press('Escape')
                    print(json.dumps(dict(host='browser', dpr=dpr, font=font, anchor=anchor, phase='draft_complete')), flush=True)


NATIVE_SETUP = """
ax=fig.axes[0]
ax.plot([1,5,9],[2,8,4],id='signal',label='Signal')
twin=ax.twinx(id='pressure_axis')
twin.plot([1,5,9],[85,60,25],id='pressure',label='Pressure',color='red')
twin.set_ylabel('Pressure')
ax.set_xlim(0,10);ax.set_ylim(0,10);twin.set_ylim(0,100)
state=fig.get_settings()
state['config']['right_y']['out_margin']=160
state['config']['overlays'][0]['y_axis']['line_offset']=45
state['config']['overlays'][0]['y_axis']['title_option']['visible']=True
fig.apply_settings(state)
ax.activate()
"""


def native_measure(output):
    import figgyplot as fg
    from test_radial_desktop import Inputs
    from test_interaction_parity import drag_native
    with fg.Figure(backend='native') as fig:
        exec(NATIVE_SETUP, {'fig': fig})
        handle = fig.show(block=False)
        try:
            inputs = Inputs(handle)
            initial = inputs.info()
            area = initial['decorations']['data_area']
            scale = initial['chart_panel'][2]/960
            inputs.click_rect([area[0]+area[2]-2+45*scale, area[1]+area[3]*.4, 0, 0])
            title = inputs.info()['decorations']['overlay_0:axis_title_right']
            inputs.click_rect(initial['decorations']['axis_left'])
            drag_native(inputs, (title[0]+title[2]/2, title[1]+title[3]/2), (16*scale, 12*scale))
            assert inputs.info()['selected'] == 'overlay_0:axis_title_right'
            dpr = inputs.info()['scale_factor']
            rows = []

            def wheel(button, count):
                view = inputs.info()['controls']['properties_viewport']
                inputs.xdo('mousemove', '--window', inputs.wid, round(view[0]+view[2]/2), round(view[1]+view[3]/2))
                inputs.xdo('click', '--repeat', count, '--delay', 2, button)
                inputs.pump()

            def observe(width, height, phase):
                inputs.xdo('windowsize', inputs.wid, width, height)
                history, previous, stable = [], None, 0
                started = time.monotonic()
                while time.monotonic()-started < 5:  # Existing native input budget.
                    inputs.pump()
                    info = inputs.info()
                    history.append(info)
                    geometry = [info['surface_size'], info['controls'].get('properties_viewport'), info['controls'].get('text')]
                    stable = stable+1 if geometry == previous else 1
                    previous = geometry
                    if stable >= 3:
                        break
                wheel(4, 12)  # Explicitly measure the form at its top every time.
                info = inputs.info()
                view = info['controls']['properties_viewport']
                w, h = info['surface_size']
                clip = [max(0, view[0]), max(0, view[1]),
                        max(0, min(w, view[0]+view[2])-max(0, view[0])),
                        max(0, min(h, view[1]+view[3])-max(0, view[1]))]
                tests = {name: margins(info['controls'][name], clip)
                         for name in ('font', 'font_size', 'color', 'text') if name in info['controls']}
                revision = fig.revision
                after = info
                scrolls = 0
                while not margins(after['controls']['text'], clip)['strict_inside'] and scrolls < 35:
                    wheel(4 if after['controls']['text'][1] < clip[1] else 5, 1)
                    after = inputs.info()
                    scrolls += 1
                    if after['surface_frames'] == info['surface_frames']:
                        break
                row = dict(host='native', phase=phase, requested=[width, height], dpr=dpr,
                           settled=stable >= 3, elapsed_ms=(time.monotonic()-started)*1000,
                           actual=info['surface_size'], effective_viewport=clip, tests=tests,
                           scroll_steps=scrolls, reachable=margins(after['controls']['text'], clip),
                           reachability_method='At most 35 ordinary wheel notches, reversing direction after overshoot; not a proof that every input method fails.',
                           scroll_changed_revision=fig.revision != revision,
                           initial=info, after_scroll=after, resize_history=history)
                # Accessibility is an independent experiment. Preserve the
                # initial and ordinary-wheel failures above even if a precision
                # scrollbar operation or explicit edit succeeds below.
                if width == round(1312*dpr) and height in [round(h*dpr) for h in (520,744,845,1200)]:
                    if not row['reachable']['strict_inside']:
                        wheel(4,12)
                        top = inputs.info()
                        view = top['controls']['properties_viewport']
                        frame = top['layout_probe'][-1]
                        content_height = frame['content_size'][1]*top['scale_factor']
                        text_rect = top['controls']['text']
                        desired_offset = text_rect[1]-view[1]+text_rect[3]/2-view[3]/2
                        bar_y = view[1]+(desired_offset+view[3]/2)*view[3]/content_height
                        inputs.click_rect([view[0]+view[2]-3*dpr,bar_y,0,0])
                        after = inputs.info()
                        row['after_scrollbar'] = after
                        row['scrollbar_reachable'] = margins(after['controls']['text'],clip)
                    if margins(after['controls']['text'],clip)['strict_inside']:
                        original_document = fig.get_settings()
                        inputs.click_rect(after['controls']['text'])
                        inputs.key('ctrl+a')
                        inputs.xdo('type','--clearmodifiers','Pressure probe')
                        inputs.pump()
                        inputs.key('Return')
                        edited = fig.get_settings()['config']['overlays'][0]['y_axis']['title_option']['text']['segments']
                        actual_text = ''.join(s['text'] for s in edited)
                        row['edit_probe'] = dict(expected='Pressure probe',actual=actual_text,passed=actual_text=='Pressure probe')
                        fig.apply_settings(original_document)
                        inputs.pump()
                    else:
                        row['edit_probe'] = dict(performed=False,reason='Field not wholly visible after observed input methods')
                emit(output, row)
                rows.append(row)
                print(json.dumps({k:row[k] for k in ('host','phase','requested','actual','dpr','tests','scroll_steps','reachable')}), flush=True)
                return row

            for width in (900, 1312, 1600):
                for height in (520, 590, 700, 744, 800, 840, 844, 845, 900, 1000, 1200):
                    observe(round(width*dpr), round(height*dpr), 'matrix')
            # Find adjacent *physical* heights bracketing the observed change.
            low, high = round(520*dpr), round(1200*dpr)
            while high-low > 1:
                middle = (low+high)//2
                row = observe(round(1312*dpr), middle, 'boundary')
                if row['tests']['text']['strict_inside']:
                    high = middle
                else:
                    low = middle
            for height in (low, high):
                observe(round(1312*dpr), height, 'boundary_confirm')
            (output / 'native-boundary.json').write_text(json.dumps(dict(dpr=dpr, last_invalid_height=low, first_valid_height=high), indent=2))
            from PIL import ImageGrab
            ImageGrab.grab(xdisplay=os.environ['DISPLAY']).save(output / 'native-final.png')
        finally:
            handle.close()
            Inputs.pump()


def browser_focus(output):
    """Separate persistent invalid layout from measurement-order artifacts."""
    from jupyter_harness import notebook
    source = """import figgyplot as fg
fig,ax=fg.subplots(backend='webgpu')
ax.plot([0,1,2],[1,3,2])
ax.text(.95,.95,'Probe',coords='ratio',fontsize=16*72/fig.dpi,id='probe')
display(fig.widget())
"""
    with notebook(output / 'notebook', source) as (page, execute):
        session = page.context.new_cdp_session(page)
        page.evaluate("""()=>{
            window.figgyValidityResizeEvents=[];
            addEventListener('resize',()=>window.figgyValidityResizeEvents.push({now:performance.now(),viewport:[innerWidth,innerHeight]}));
        }""")
        entries = page.evaluate("document.querySelector('.figgy-editor').figgy.annotations()")
        r = entries[0]['rect']
        point = page.locator('canvas').evaluate("(c,p)=>{const r=c.getBoundingClientRect();return [r.x+p[0]*r.width/c.width,r.y+p[1]*r.height/c.height]}", [r[0]+8,r[1]+6])
        page.mouse.dblclick(*point)
        entry = page.locator('[data-inline-text]')
        entry.wait_for(state='visible', timeout=5000)

        def record(label, result=None):
            snapshot = result['final'] if result else page.evaluate(BROWSER_SNAPSHOT)
            canvas = xywh(snapshot['nodes']['canvas']['rect'])
            tests = {name:margins(xywh(snapshot['nodes'][selector]['rect']),canvas)
                     for name,selector in [('input','[data-inline-text]'),('box','.figgy-inline-text')]}
            emit(output, dict(host='browser', phase=label, snapshot=snapshot, tests=tests, transition=result))
            print(json.dumps(dict(phase=label, backing=snapshot['backing'],
                                  css_font=snapshot['nodes']['[data-inline-text]']['fontSize'], tests=tests)), flush=True)

        def resize(width, height, dpr=1):
            before = page.evaluate('[innerWidth,innerHeight,devicePixelRatio]')
            page.evaluate('window.figgyValidityResizeEvents=[]')
            session.send('Emulation.setDeviceMetricsOverride', dict(width=width,height=height,deviceScaleFactor=dpr,mobile=False))
            return browser_settle(page, [width,height,dpr], before[:2] != [width,height])

        entry.fill('Short')
        record('short_baseline', resize(1500,1000))
        entry.fill('\n'.join(f'Line {i}' for i in range(1,9)))
        record('eight_lines_immediate')
        for delay in (100,400,1500):
            page.wait_for_timeout(delay)
            record(f'eight_lines_after_{delay}_additional_ms')
        # Diagnostic intervention: re-run the existing input handler without
        # changing text, settings, CSS, source or the renderer.
        entry.dispatch_event('input')
        record('eight_lines_unchanged_input_intervention')
        entry.fill('First\nSecond')
        record('shrink_640', resize(640,600))
        record('grow_1500', resize(1500,1000))
        for delay in (100,400,1500):
            page.wait_for_timeout(delay)
            record(f'grow_after_{delay}_additional_ms')
        entry.dispatch_event('input')
        record('grow_unchanged_input_intervention')
        for dpr in (1.25,2):
            record(f'dpr_{dpr}_before_input', resize(1500,1000,dpr))
            entry.dispatch_event('input')
            record(f'dpr_{dpr}_after_input')
        entry.press('Escape')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', choices=['browser', 'native', 'browser-focus'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    os.environ['FIGGY_LAYOUT_PROBE'] = '1'
    provenance(args.output)
    {'browser':browser_measure,'native':native_measure,'browser-focus':browser_focus}[args.host](args.output)


if __name__ == '__main__':
    main()

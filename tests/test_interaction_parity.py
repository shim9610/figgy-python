from object_navigation import ObjectNavigator
"""Same input scenarios must work on native surfaces and real notebook WebGPU."""
import json
import base64
import subprocess
import os
import shutil
import time
import numpy as np
import pytest
import figgyplot as figgy
from test_radial_desktop import Inputs
from native_input import set_clipboard
from jupyter_harness import notebook, button_point_without_frames, click_button
from browser_timing import screenshot_editor

ROOT = "document.querySelector('.figgy-editor').figgy"
CASES = {
    'radial': "ax.donut([40, 30, 30], labels=['A','B','C'], material='ceramic')",
    'categorical': "ax.bar(['A','B','C'], [4, 3, 5])",
    'boxplot': "ax.boxplot([[1,2,3],[2,4,6],[3,5,8]])",
    'radar': "ax.radar(['A','B','C'], [[4,3,5],[2,5,3]])",
}


@pytest.mark.parametrize('backend', ['native', 'webgpu'])
def test_legacy_settings_and_heatmap_legend_preserve_shared_host_model(backend):
    """The migration keeps saved edits, current stamps and colormap symbols aligned."""
    with figgy.Figure(backend=backend) as figure:
        ax = figure.axes[0]
        ax.imshow([[0, 1], [1, 0]], id='field')
        figure.update('field', label='Temperature')
        ax.legend()
        before = figure.get_settings()
        saved = json.loads(json.dumps(before))
        saved['renderer_version'] = '0.17.0'
        saved['config']['colorbar']['colormap'] = 'Magma'
        figure.apply_settings(saved)
        current = figure.get_settings()
        assert current['renderer_version'] == '0.18.1'
        assert current['config']['legend']['content'] != before['config']['legend']['content']
        assert 'Temperature' in ''.join(s['text'] for s in current['config']['legend']['content']['segments'])
        revision = figure.revision
        figure.apply_settings(current)
        assert figure.revision == revision

NEEDS_UI = not os.environ.get('DISPLAY') or not all(shutil.which(p) for p in ['xdotool','xclip','wmctrl']) or os.environ.get('FIGGY_TEST_JUPYTER') != '1'


@pytest.mark.skipif(NEEDS_UI, reason='requires actual native/Jupyter copy controls')
def test_compact_python_copy_in_both_hosts_replays_the_complete_document(tmp_path):
    scene = '''
fig.set_layout([['first','second']])
fig.subplots['first'].plot([0,1],[1,2],id='signal',label='Signal')
fig.subplots['first'].set_title('Comparison\\nTwo lines')
fig.subplots['first'].text(.2,.3,'한글 note',coords='ratio',id='note')
fig.subplots['second'].imshow([[1,2],[3,4]],id='field')
'''
    with figgy.Figure(backend='native') as fig:
        exec(scene, {'fig':fig})
        handle = fig.show(block=False)
        try:
            inputs = Inputs(handle)
            inputs.click('copy')
            code = subprocess.check_output(['xclip','-selection','clipboard','-o'],text=True,timeout=3)
            assert code == fig.to_code() and 'batch_update' in code
            assert len(code) < len(fig.to_code(compact=False)) * .55
            with figgy.Figure(backend='native') as other:
                exec(scene, {'fig':other})
                exec(code, {'fig':other})
                assert other.get_settings()['config'] == fig.get_settings()['config']
                assert other.get_settings()['series'] == fig.get_settings()['series']
                np.testing.assert_array_equal(other.render_rgba(), fig.render_rgba())
            (tmp_path/'native-copy.py').write_text(code)
        finally:
            handle.close(); Inputs.pump()
    source = (f'import figgyplot as fg\nassert fg.__file__ == {figgy.__file__!r}\n'
              "fig=fg.Figure(backend='webgpu')\n"+scene+'\ndisplay(fig.widget())')
    with notebook(tmp_path/'browser',source) as (page,execute):
        click_button(page,'[data-copy]')
        page.evaluate(ROOT+'.flush()')
        execute('await fig.sync()')
        code=page.locator('textarea[data-code]').input_value()
        assert code and 'batch_update' in code
        (tmp_path/'browser-copy.py').write_text(code)
        execute(f"code={code!r}\nassert code==fig.to_code()\nother=fg.Figure(backend='webgpu')\n"+
                f"exec({scene!r},{{'fig':other}})\nexec(code,{{'fig':other}})\nassert other.get_settings()['config']==fig.get_settings()['config']\nassert other.get_settings()['series']==fig.get_settings()['series']\nother.close()")


def assert_blind_trial_title_pixels(image):
    assert image.shape == (500,700,4)
    rgb = image[..., :3].astype(int)
    ink = (rgb[:,:,0] > 130) & (rgb[:,:,1] < 90) & (rgb[:,:,2] < 90)
    rows = np.flatnonzero(ink.sum(axis=1) >= 2)
    bands = np.split(rows, np.flatnonzero(np.diff(rows) > 1) + 1)
    assert len(bands) == 2 and all(len(b) >= 10 for b in bands), [b.tolist() for b in bands]
    assert ink.sum() > 150
    return dict(title_bands=[b.tolist() for b in bands], colored_pixels=int(ink.sum()))


def test_blind_trial_title_oracle_rejects_black_and_missing_second_line():
    with pytest.raises(AssertionError):
        assert_blind_trial_title_pixels(np.zeros((500,700,4), dtype=np.uint8))
    with figgy.Figure(backend='native', figsize=(7,5), dpi=100) as fig:
        fig.axes[0].bar(['A','B'],[2,4])
        fig.axes[0].set_title('FIRST',fontsize=18,color='#b42020')
        with pytest.raises(AssertionError):
            assert_blind_trial_title_pixels(fig.render_rgba())


@pytest.mark.parametrize('backend', ['native', 'webgpu'])
@pytest.mark.skipif(NEEDS_UI, reason='requires native/Jupyter GPU environment')
def test_blind_trial_titles_render_two_real_lines_in_both_hosts(tmp_path, backend):
    """Ready is insufficient: both title lines must be present on the image."""
    from browser_timing import DISPLAY_SETTLED
    from PIL import Image
    import io
    scene = '''
ax=fig.axes[0]
ax.set_xlabel('Requested X')
ax.set_ylabel('Requested Y')
ax.set_title('FIRST\\nSECOND',fontsize=18,color='#b42020')
ax.bar(['A','B'],[2,4])
'''
    if backend == 'native':
        with figgy.Figure(backend=backend, figsize=(7,5), dpi=100) as fig:
            exec(scene, {'fig': fig})
            image = fig.render_rgba()
            fig.savefig(tmp_path/'native.png')
            state = fig.get_settings()
    else:
        source = (f"import figgyplot as fg\nassert fg.__file__ == {figgy.__file__!r}\n"
                  "fig=fg.Figure(backend='webgpu',figsize=(7,5),dpi=100)\n" + scene + "\ndisplay(fig.widget())")
        with notebook(tmp_path, source) as (page, execute):
            page.wait_for_function(DISPLAY_SETTLED, polling=100, timeout=180000)
            canvas = page.locator('.figgy-editor canvas')
            canvas.evaluate('''c=>{const r=c.getBoundingClientRect();c.closest('.figgy-editor').style.transform=`translate(${Math.ceil(r.x)-r.x}px,${Math.ceil(r.y)-r.y}px)`;}''')
            image = np.asarray(Image.open(io.BytesIO(canvas.screenshot(path=str(tmp_path/'browser.png')))).convert('RGBA'))
            state = page.evaluate(ROOT + '.snapshot()')
    chart = state['categorical']
    assert chart['category_title'] == 'Requested X' and chart['value_title'] == 'Requested Y'
    assert ''.join(s['text'] for s in chart['chart_title']['text']['segments']) == 'FIRST\nSECOND'
    result = assert_blind_trial_title_pixels(image)
    (tmp_path/'contract.json').write_text(json.dumps(dict(backend=backend,**result,settings=state),indent=2))


@pytest.mark.parametrize('backend',['native','webgpu'])
@pytest.mark.parametrize('panel',['main','child'])
def test_marker_size_changes_keep_legend_symbols_owned_by_labelled_series(backend,panel):
    from figgyplot._native import rebuild_legend_json
    with figgy.Figure(backend=backend) as fig:
        if panel=='child':fig.set_layout([['main','child']])
        ax=fig.subplots[panel].axes
        ax.plot([0,1],[1,2],marker='^',id='not_in_legend')
        ax.scatter([0,1],[2,1],marker='o',label='Same label',id='circle')
        ax.scatter([0,1],[3,2],marker='D',label='Same label',id='diamond')
        ax.legend()
        before=fig.get_settings();cfg=ax._config(before)
        expected=json.loads(rebuild_legend_json(json.dumps(ax._owned_series(before)),json.dumps(cfg['legend']['content']),None))
        assert cfg['legend']['content']==expected
        fig.configure(series={'diamond':{'render_type':{'Scatter':{'scatter':{'point_size':5.6}}}}})
        after=fig.get_settings()
        assert ax._config(after)['legend']['content']==expected
        assert after['series'][1]['render_type']['Scatter']['scatter']['point_shape']=='CircleFilled'
        assert after['series'][2]['render_type']['Scatter']['scatter']['point_shape']=='DiamondFilled'

@pytest.mark.parametrize('backend',['native','webgpu'])
@pytest.mark.parametrize('change',['unlabelled_size','labelled_width','all_labelled'])
def test_offscreen_legend_keys_keep_their_symbols_after_configure(backend,change,tmp_path):
    """Style edits preserve the labelled subset, including offscreen legend keys."""
    from figgyplot._native import rebuild_legend_json
    with figgy.Figure(figsize=(6,4),dpi=120,backend=backend) as fig:
        ax=fig.axes[0];x=np.linspace(0,10,11)
        ax.plot(x,x,color='#c44536',linestyle='--',marker='o',markersize=4,
                label='red data' if change=='all_labelled' else None,id='data_red')
        ax.plot(x,x+3,color='#0b6e99',linestyle=':',marker='s',markersize=4,
                label='blue data' if change=='all_labelled' else None,id='data_blue')
        ax.plot([-1e9,-.9e9],[1,1],color='#2a9d8f',linewidth=3,label='key green line',id='key_line')
        ax.scatter([-1e9],[1],color='#57606a',marker='^',s=16,label='key grey triangle',id='key_tri')
        ax.set_xlim(0,10);ax.set_ylim(0,15);ax.legend(True)
        before=fig.get_settings();legend=before['config']['legend']['content']
        expected=json.loads(rebuild_legend_json(json.dumps(before['series']),json.dumps(legend),None))
        assert legend==expected
        if backend=='native':fig.savefig(tmp_path/'before.png')
        if change=='labelled_width':
            patch={'key_line':{'render_type':{'Line':{'line':{'line_width':5.6}}}}}
        else:
            patch={'data_red':{'render_type':{'ScatterLine':{'scatter':{'point_size':5.6}}}}}
        fig.configure(series=patch)
        after=fig.get_settings()
        expected=json.loads(rebuild_legend_json(json.dumps(after['series']),json.dumps(legend),None))
        assert after['config']['legend']['content']==expected
        if change!='labelled_width':assert expected==legend
        if backend=='native':
            fig.savefig(tmp_path/'after.png')
            pixels=fig.render_rgba()[...,:3].astype(int)
            # These keys are outside the axes: their colors can appear only in
            # the legend, so this also checks the actual rendered symbols.
            for color in ([42,157,143],[87,96,106]):
                ink=255-np.array(color)
                coverage=((255-pixels)@ink)/(ink@ink)
                error=np.max(np.abs(pixels-(255-coverage[...,None]*ink)),axis=2)
                assert np.count_nonzero((coverage>.35)&(coverage<=1.01)&(error<=2))>3
        assert [s['label'] for s in after['series']]==[s['label'] for s in before['series']]
        assert [s['render_type'].keys() for s in after['series']]==[s['render_type'].keys() for s in before['series']]


if os.environ.get('FIGGY_REQUIRE_INTERACTION_PARITY') == '1' and NEEDS_UI:
    raise RuntimeError('Required interaction parity cannot be skipped: install X11 tools, set DISPLAY and FIGGY_TEST_JUPYTER=1')


def offset(chart, target):
    return next((v['offset'] for v in chart['decorations']['offsets'] if v['element'] == target), [0, 0])


def drag_native(inputs, start, delta):
    for args in [('mousemove','--window',inputs.wid,*map(round,start)),('mousedown',1),
                 ('mousemove','--window',inputs.wid,*map(round,(start[0]+delta[0],start[1]+delta[1]))),('mouseup',1)]:
        inputs.input_frame(*args)


def native_point(info, logical):
    p=info['chart_panel']
    return p[0]+logical[0]*p[2]/960, p[1]+logical[1]*p[3]/600


def browser_point(page, logical):
    r=page.locator('.figgy-editor canvas').bounding_box()
    return r['x']+logical[0]*r['width']/960, r['y']+logical[1]*r['height']/600


def browser_surface_point(page, point):
    return page.evaluate("""p=>{const c=document.querySelector('.figgy-editor canvas'),r=c.getBoundingClientRect();return [r.x+p[0]*r.width/c.width,r.y+p[1]*r.height/c.height];}""", point)


def check_bounded_menus_during_preparation(page, execute, kind):
    """Hold actual GPU completion so toolbar clicks overlap an async WASM borrow."""
    menu_points = []
    for selector in ('button[data-style]', 'button[data-visibility]'):
        # GPU presentation can delay RAF even before this artificial gate.
        x, y = button_point_without_frames(page, selector)
        menu_points.append((selector, x, y))
    page.evaluate("""()=>{
        const prototype=GPUQueue.prototype;
        const original=prototype.onSubmittedWorkDone;
        let release;
        const gate=new Promise(resolve=>{release=resolve;});
        window.figgyPreparationGate={entered:false,enteredCount:0,armedAt:performance.now(),release:()=>{
            const state=window.figgyPreparationGate;state.releasedAt=performance.now();
            window.figgyDiagnosticEvent?.('preparation-gate-released',{durationMs:state.releasedAt-state.armedAt,enteredCount:state.enteredCount});
            prototype.onSubmittedWorkDone=original;release();
        }};
        window.figgyDiagnosticEvent?.('preparation-gate-armed',{armedAt:window.figgyPreparationGate.armedAt});
        prototype.onSubmittedWorkDone=function(...args){
            const completion=original.apply(this,args);
            const state=window.figgyPreparationGate;state.entered=true;state.enteredCount++;
            state.enteredAt??=performance.now();
            window.figgyDiagnosticEvent?.('preparation-gate-entered',{count:state.enteredCount,elapsedMs:performance.now()-state.armedAt});
            return completion.then(()=>{state.gpuCompletedAt=performance.now();
                window.figgyDiagnosticEvent?.('preparation-gate-gpu-completed',{elapsedMs:state.gpuCompletedAt-state.armedAt,releasedAt:state.releasedAt});
                return gate;});
        };
    }""")
    try:
        # Preparation includes the original and resized surface. Use the public
        # API's 180-second default; export keeps its separate 60-second budget.
        execute('import asyncio; preparation=asyncio.create_task(fig.prepare_async())')
        try:
            # This is a GPU-fence handshake, not a visual condition. Poll on a
            # timer so delayed software-GPU presentation cannot stall RAF polling.
            page.wait_for_function('window.figgyPreparationGate.entered', polling=100)
        except Exception:
            # The fixture saves full diagnostics independently; avoid masking
            # the original handshake timeout if the page cannot be evaluated.
            try:
                print('Preparation gate diagnostic:', page.evaluate("""()=>({
                    gate:window.figgyPreparationGate,now:performance.now(),
                    status:document.querySelector('.figgy-editor [data-status]')?.textContent,
                    stats:document.querySelector('.figgy-editor')?.figgy?.stats
                })"""))
            except Exception as error:
                print('Preparation gate diagnostic unavailable:', repr(error))
            raise
        execute('assert not preparation.done()')
        for selector, x, y in menu_points:
            # Keep real mouse input and verify the hit rather than forcing a
            # locator click or waiting for presentation while its fence is held.
            assert page.evaluate("""([selector,x,y])=>{
                const button=document.querySelector(selector);
                return !button.disabled && document.elementFromPoint(x,y)?.closest('button')===button;
            }""", [selector, x, y])
            page.mouse.click(x, y)
        # Both menus read the chart document. They must wait for the pending
        # renderer call, rather than borrowing the WASM chart a second time.
        assert page.locator('.figgy-menu').is_hidden()
        assert page.locator('.figgy-properties').is_hidden()
        assert page.locator('.figgy-error').inner_text()==''
        # The display may resize while preparation owns the WASM chart. Ready
        # must cover the new surface even if ResizeObserver is queued behind it.
        before_size = page.locator('.figgy-editor canvas').evaluate('canvas=>[canvas.width,canvas.height]')
        requested_size = page.locator('.figgy-editor canvas').evaluate("""canvas=>{
            const before=[canvas.width,canvas.height];
            canvas.style.width='90%';const r=canvas.getBoundingClientRect(),dpr=devicePixelRatio||1;
            const requested=[Math.round(r.width*dpr),Math.round(r.height*dpr)];
            window.figgyDiagnosticEvent?.('preparation-gate-resize',{before,requested,css:[r.width,r.height],dpr});
            return requested;
        }""")
        assert requested_size != before_size
    finally:
        # Preserve an existing assertion/timeout if browser cleanup also fails.
        import sys
        active_error = sys.exc_info()[0] is not None
        try:
            page.evaluate('window.figgyPreparationGate.release()')
        except Exception as error:
            if not active_error:
                raise
            print('Preparation gate release failed:', repr(error))
    report=json.loads(execute('print(json.dumps(await preparation))'))
    assert report['ready'] and report['backend']=='webgpu'
    page.evaluate(ROOT+'.flush()')
    # Queued toolbar actions open the docked inspector after preparation. Its
    # new canvas size is a subsequent layout change, not the prepared surface.
    check_display_frame_ready(page, after_layout_change=True)
    assert page.locator('.figgy-properties').is_visible()
    if kind=='radial':
        assert ObjectNavigator(page).selected()=='chart_title'
    else:
        grid=page.locator('input[data-visibility="grid"]')
        assert grid.is_visible()
        original=grid.is_checked()
        grid.set_checked(not original);page.evaluate(ROOT+'.flush()')
        assert page.evaluate(ROOT+f'.snapshot().{kind}.grid')==(not original)
        grid.set_checked(original);page.evaluate(ROOT+'.flush()')
        assert page.evaluate(ROOT+f'.snapshot().{kind}.grid')==original
        click_button(page, 'button[data-visibility]');page.evaluate(ROOT+'.flush()')
    click_button(page, '[data-close-properties]')
    assert page.locator('.figgy-menu').is_hidden()
    assert page.locator('.figgy-error').inner_text()==''


def check_display_frame_ready(page, after_layout_change=False):
    if after_layout_change:
        page.wait_for_function("""()=>{
            const root=document.querySelector('.figgy-editor'),canvas=root.querySelector('canvas'),r=canvas.getBoundingClientRect(),dpr=devicePixelRatio||1;
            const expected=[Math.round(r.width*dpr),Math.round(r.height*dpr)],work=window.figgyGPUWork,host=root.figgy.diagnostics();
            return canvas.width===expected[0]&&canvas.height===expected[1]&&JSON.stringify(work.completedCanvas)===JSON.stringify(expected)&&work.submitted===work.completed&&!host.dirty&&!host.frame_pending&&!host.busy&&!host.queued;
        }""", polling=100, timeout=180000)
    initial = page.evaluate("""()=>{
        const canvas=document.querySelector('.figgy-editor canvas'),r=canvas.getBoundingClientRect(),dpr=devicePixelRatio||1;
        const work=window.figgyGPUWork;
        return {size:[canvas.width,canvas.height],display:[Math.round(r.width*dpr),Math.round(r.height*dpr)],
            completed:work.completedCanvas,pending:work.submitted-work.completed,
            frames:document.querySelector('.figgy-editor').figgy.stats.surface_frames};
    }""")
    assert initial['size'] == initial['display'] == initial['completed']
    assert initial['pending'] == 0
    assert initial['frames'] >= 1
    # Ready must not leave a redundant/resized frame to submit on the next RAF.
    page.evaluate("window.figgyReadyFrames=0;requestAnimationFrame(()=>{window.figgyReadyFrames++;requestAnimationFrame(()=>window.figgyReadyFrames++);})")
    page.wait_for_function('window.figgyReadyFrames===2', polling=100)
    assert page.evaluate(ROOT+'.stats.surface_frames') == initial['frames']
    assert page.evaluate('window.figgyGPUWork.submitted-window.figgyGPUWork.completed') == 0


@pytest.mark.skipif(NEEDS_UI, reason='requires X11 input tools and FIGGY_TEST_JUPYTER=1')
@pytest.mark.parametrize('kind', CASES)
def test_bounded_hosts_share_drag_resize_pick_hover_and_export(tmp_path, kind):
    with figgy.figure(backend='native') as fig:
        ax=fig.axes[0]
        exec(CASES[kind], {'ax':ax})
        ax.set_title('Shared interaction')
        handle=fig.show(block=False)
        try:
            inputs=Inputs(handle)
            assert not inputs.info()['properties_open']
            # Measured renderer bounds determine the hit, independent of display size.
            box=inputs.info()['decorations']['chart_title']
            point=(box[0]+box[2]/2,box[1]+box[3]/2)
            before=offset(fig.get_settings()[kind], 'ChartTitle')
            scale=inputs.info()['chart_panel'][2]/960
            drag_native(inputs,native_point(inputs.info(),point),(12*scale,6*scale))
            after=offset(fig.get_settings()[kind], 'ChartTitle')
            assert np.subtract(after,before)==pytest.approx([12,6], abs=1.2)
            # Area resize uses the upstream SE handle; do not distort data or labels.
            inputs.click('layout_mode')
            box=inputs.info()['decorations']['data_area']
            inputs.click_rect([*native_point(inputs.info(),(box[0]+box[2]/2,box[1]+box[3]/2)),0,0])
            assert inputs.info()['decoration_selected']=='DataArea'
            original_area=inputs.info()['decorations']['data_area']
            handles=json.loads(fig._native.bounds_json('data_area'))['handles']
            end=max(handles,key=lambda r:r[0]+r[1])
            point=(end[0]+end[2]/2,end[1]+end[3]/2)
            drag_native(inputs,native_point(inputs.info(),point),(-16*scale,-12*scale))
            native_area=fig.get_settings()[kind]['decorations']['data_area']
            assert native_area is not None
            assert [native_area['width'],native_area['height']]==pytest.approx([original_area[2]-16,original_area[3]-12],abs=1.2)
            # Restore auto layout before comparing the same hit in both hosts.
            fig.fit();inputs.pump();inputs.click('select_mode')
            hit=None
            for y in range(160,500,50):
                for x in range(180,800,50):
                    hit=fig.select(x,y)
                    if hit:break
                if hit:break
            assert hit is not None
            fig._native.clear_data_selection();inputs.pump()
            pos=native_point(inputs.info(),(x,y))
            inputs.xdo('mousemove','--window',inputs.wid,*map(round,pos));inputs.pump()
            native_hover=fig.get_settings()[kind]
            assert (native_hover['interaction']['hovered'] if kind=='radial' else native_hover['hovered']) is not None
            inputs.click_rect([*pos,0,0])
            assert inputs.info()['selected'] is not None
            assert inputs.info()['properties_open']
            inputs.key('Right')
            native_selected=inputs.info()['selected']
            inputs.key('Escape')
            assert inputs.info()['selected'] is None
            assert fig.info['rgba_readbacks']==fig.info['png_encodes']==0
            native_data=fig.get_settings()[kind]['slices' if kind=='radial' else 'series']
        finally:
            handle.close();Inputs.pump()
    source="import json\nimport figgyplot as figgy\nfig,ax=figgy.subplots(backend='webgpu')\n"+CASES[kind]+"\nax.set_title('Shared interaction')\ndisplay(fig.widget())"
    with notebook(tmp_path/kind, source) as (page,execute):
        check_display_frame_ready(page)
        panel=page.locator('.figgy-properties')
        assert panel.is_hidden()
        check_bounded_menus_during_preparation(page,execute,kind)
        assert panel.is_hidden()
        assert page.locator('[data-layout] svg').count()==1
        for selector in ['data-fit','data-copy','data-save','data-properties']:
            assert page.locator(f'[{selector}] svg').count()==1
        box=page.evaluate("async()=> (await "+ROOT+".decorations()).find(v=>v.id==='chart_title').rect")
        start=browser_point(page,(box[0]+box[2]/2,box[1]+box[3]/2))
        end=browser_point(page,(box[0]+box[2]/2+12,box[1]+box[3]/2+6))
        page.mouse.move(*start);page.mouse.down();page.mouse.move(*end,steps=5);page.mouse.up()
        execute('await fig.sync()')
        state=json.loads(execute('print(json.dumps(fig.get_settings()))'))
        assert offset(state[kind],'ChartTitle')==pytest.approx([12,6],abs=1.2)
        click_button(page, '[data-layout]')
        box=page.evaluate("async()=> (await "+ROOT+".decorations()).find(v=>v.id==='data_area').rect")
        page.mouse.click(*browser_point(page,(box[0]+box[2]/2,box[1]+box[3]/2)))
        if panel.is_visible():click_button(page, '[data-close-properties]')
        handles=page.evaluate("async()=> (await "+ROOT+".decorations()).find(v=>v.id==='data_area').handles")
        h=max(handles,key=lambda r:r[0]+r[1]);pos=(h[0]+h[2]/2,h[1]+h[3]/2)
        click_at=browser_point(page,pos)
        (tmp_path/'resize-before.json').write_text(json.dumps({'logical':pos,'screen':click_at,'handles':handles,'state':page.evaluate(ROOT+'.snapshot()'),'element':page.evaluate('(p)=>document.elementFromPoint(...p)?.outerHTML.slice(0,500)',click_at)}))
        assert page.evaluate('(p)=>document.elementFromPoint(...p)?.tagName',click_at)=='CANVAS'
        page.mouse.move(*click_at);page.mouse.down();page.mouse.move(*browser_point(page,(pos[0]-16,pos[1]-12)),steps=5);page.mouse.up()
        execute('await fig.sync()')
        state=json.loads(execute('print(json.dumps(fig.get_settings()))'))
        assert state[kind]['decorations']['data_area'] == pytest.approx(native_area,abs=1.2), page.locator('.figgy-error').inner_text()
        click_button(page, '[data-fit]');click_button(page, '[data-select]');page.evaluate(ROOT+'.flush()')
        page.mouse.move(*browser_point(page,(x,y)))
        page.wait_for_function(ROOT+f".snapshot().{kind}."+('interaction.hovered' if kind=='radial' else 'hovered')+" !== null")
        page.mouse.click(*browser_point(page,(x,y)))
        # Picking and opening the editor run through the operation queue.
        panel.wait_for(state='visible')
        assert panel.is_visible()
        # Hover and click do not recreate columns or encode images.
        canvas=page.locator('.figgy-editor canvas')
        canvas.press('ArrowRight');execute('await fig.sync()')
        state=json.loads(execute('print(json.dumps(fig.get_settings()))'))
        selected=state[kind]['interaction']['selected'] if kind=='radial' else state[kind]['selected']
        assert selected==native_selected
        canvas.press('Escape');execute('await fig.sync()')
        state=json.loads(execute('print(json.dumps(fig.get_settings()))'))
        assert (state[kind]['interaction']['selected'] if kind=='radial' else state[kind]['selected']) is None
        assert state[kind]['slices' if kind=='radial' else 'series']==native_data
        assert page.evaluate(ROOT+'.stats.png_exports')==page.evaluate(ROOT+'.stats.column_uploads')==0
        path=tmp_path/'export.png'
        execute(f'await fig.savefig_async({str(path)!r})')
        from PIL import Image
        pixels=np.asarray(Image.open(path).convert('RGB'))
        assert pixels.shape==(600,960,3)
        assert np.count_nonzero(np.any(pixels<200,axis=2))>500


@pytest.mark.skipif(NEEDS_UI, reason='requires X11 input tools and FIGGY_TEST_JUPYTER=1')
@pytest.mark.parametrize('family',['categorical','boxplot','radar'])
def test_browser_coalesces_input_while_ordinary_frame_is_pending(tmp_path,family):
    """Slow GPU completion must not build a frame backlog ahead of PNG export."""
    setup={'categorical':"ax.bar(['A','B'],[3,5])",'boxplot':"ax.boxplot([[1,2,3],[2,4,6]])",'radar':"ax.radar(['A','B','C'],[2,4,3])"}[family]
    source="import json\nimport figgyplot as figgy\nfig,ax=figgy.subplots(backend='webgpu')\n"+setup+"\nax.text(.1,.1,'Probe',coords='ratio',id='probe')\nax.set_title('Frame backpressure')\ndisplay(fig.widget())"
    with notebook(tmp_path/'frame-backpressure', source) as (page,execute):
        click_button(page, '[data-properties]')
        page.locator('.figgy-properties').wait_for(state='visible')
        box=page.evaluate("async()=> (await "+ROOT+".decorations()).find(v=>v.id==='chart_title').rect")
        logical=(box[0]+box[2]/2,box[1]+box[3]/2)
        start=browser_point(page,logical)
        end=browser_point(page,(logical[0]+12,logical[1]+6))
        page.mouse.move(*start)
        page.evaluate(ROOT+'.flush()')
        baseline=page.evaluate('window.figgyGPUWork.submitted')
        page.evaluate("""()=>{
            const prototype=GPUQueue.prototype,original=prototype.onSubmittedWorkDone;
            let release;const held=new Promise(resolve=>{release=resolve;});
            window.figgyFrameGate={entered:false,release:()=>{
                prototype.onSubmittedWorkDone=original;release();
            }};
            prototype.onSubmittedWorkDone=function(...args){
                const completion=original.apply(this,args);
                window.figgyFrameGate.entered=true;
                return completion.then(()=>held);
            };
        }""")
        try:
            page.mouse.down()
            page.wait_for_function('window.figgyFrameGate.entered', polling=100)
            submitted=page.evaluate('window.figgyGPUWork.submitted')
            assert submitted == baseline+1
            # Actual input continues while the first draw owns the renderer.
            # Subsequent RAF callbacks must coalesce redraws, not submit them.
            page.mouse.move(*end, steps=5)
            page.mouse.up()
            # Changing the inspector target is pure DOM work. Its controls must
            # match the selected object immediately, even while renderer work is held.
            target=ObjectNavigator(page)
            series_id=page.evaluate(ROOT+f'.snapshot().{family}.series[0].id')
            target.choose(series_id)
            assert page.locator('[data-property=label]').count() == 1
            label=page.locator('[data-property=label]');label.fill('Edited series');label.press('Tab')
            target.choose('chart_title')
            assert page.locator('[data-property=label]').count() == 0
            # An earlier queued Arrow still belongs to the title, even when
            # the inspector has already presented the later series choice.
            page.locator('canvas').press('ArrowRight')
            target.choose(series_id)
            # Likewise an older queued canvas pick must not replace a newer
            # inspector choice when the GPU fence releases and work drains.
            page.mouse.click(*start)
            target.choose('chart_title')
            target.choose(series_id)
            assert page.locator('[data-property=label]').count() == 1
            page.evaluate("window.figgyHeldFrames=0;requestAnimationFrame(()=>{window.figgyHeldFrames++;requestAnimationFrame(()=>window.figgyHeldFrames++);})")
            page.wait_for_function('window.figgyHeldFrames===2', polling=100)
            assert page.evaluate('window.figgyGPUWork.submitted') == submitted
            # Sync acknowledges edits; it must not await display-GPU completion.
            # Keep the actual completion fence held until this barrier returns.
            execute('await fig.sync(timeout=5)')
            accepted=json.loads(execute('print(json.dumps(fig.get_settings()))'))
            assert accepted[family]['series'][0]['label']=='Edited series'
            assert offset(accepted[family],'ChartTitle') == pytest.approx([13,6],abs=.2)
            assert target.selected() == series_id
        finally:
            page.evaluate('window.figgyFrameGate.release()')
        page.wait_for_function('before=>window.figgyGPUWork.submitted>before',arg=submitted,polling=100)
        execute('await fig.sync()')
        state=json.loads(execute('print(json.dumps(fig.get_settings()))'))
        assert offset(state[family],'ChartTitle') == pytest.approx([13,6],abs=.2), target.selected()
        assert target.selected() == series_id
        path=tmp_path/'coalesced-export.png'
        execute(f'await fig.savefig_async({str(path)!r})')
        from PIL import Image
        pixels=np.asarray(Image.open(path).convert('RGB'))
        assert pixels.shape == (600,960,3)
        assert np.count_nonzero(np.any(pixels<200,axis=2)) > 500


@pytest.mark.skipif(NEEDS_UI, reason='requires X11 input tools and FIGGY_TEST_JUPYTER=1')
def test_cartesian_sync_accepts_edits_while_display_gpu_is_pending(tmp_path):
    source="import json\nimport figgyplot as figgy\nfig,ax=figgy.subplots(backend='webgpu')\nax.plot([0,1],[1,2])\nax.set_title('Before')\ndisplay(fig.widget())"
    with notebook(tmp_path/'cartesian-frame-barrier',source) as (page,execute):
        click_button(page, '[data-properties]')
        ObjectNavigator(page).choose('chart_title')
        page.evaluate(ROOT+'.flush()')
        page.evaluate("""()=>{
            const prototype=GPUQueue.prototype,original=prototype.onSubmittedWorkDone;
            let release;const held=new Promise(resolve=>{release=resolve;});
            window.figgyFrameGate={entered:false,release:()=>{
                prototype.onSubmittedWorkDone=original;release();
            }};
            prototype.onSubmittedWorkDone=function(...args){
                const completion=original.apply(this,args);
                window.figgyFrameGate.entered=true;
                return completion.then(()=>held);
            };
        }""")
        try:
            title=page.locator('[data-property=text]')
            title.fill('First edit');title.press('Tab')
            page.wait_for_function('window.figgyFrameGate.entered',polling=100)
            submitted=page.evaluate('window.figgyGPUWork.submitted')
            title.fill('Accepted during GPU work');title.press('Tab')
            execute('await fig.sync(timeout=5)')
            settings=json.loads(execute('print(json.dumps(fig.get_settings()))'))
            assert ''.join(s['text'] for s in settings['config']['chart_title']['text']['segments']) == 'Accepted during GPU work'
            assert page.evaluate('window.figgyGPUWork.submitted') == submitted
        finally:
            page.evaluate('window.figgyFrameGate.release()')
        page.wait_for_function('before=>window.figgyGPUWork.submitted>before',arg=submitted,polling=100)
        execute('await fig.sync()')
        path=tmp_path/'cartesian-after-barrier.png'
        execute(f'await fig.savefig_async({str(path)!r})')
        from PIL import Image
        pixels=np.asarray(Image.open(path).convert('RGB'))
        assert pixels.shape == (600,960,3)
        assert np.count_nonzero(np.any(pixels<200,axis=2)) > 500


@pytest.mark.skipif(NEEDS_UI, reason='requires X11 input tools and FIGGY_TEST_JUPYTER=1')
@pytest.mark.parametrize('transform', ['linear', 'log_inverted'])
def test_cartesian_hosts_share_pointer_anchored_zoom_pan_and_toolbar(tmp_path, transform):
    """The same navigation invariants apply in each real host, including modifiers."""
    import math
    setup = "ax.plot([1,10,100], [1,10,100], id='signal'); ax.set_title('Navigation')"
    if transform == 'log_inverted':
        setup += "; ax.set_xlim(1,1000); ax.set_ylim(1,1000); ax.set_xscale('log'); ax.set_yscale('log'); fig.configure(config={k:{'inverted':True} for k in ['bottom_x','top_x','left_y','right_y']})"

    def check_navigation(config, rect, move, wheel, pan):
        def mapped(axis, fraction):
            lo, hi = axis['min'], axis['max']
            if axis['inverted']: fraction=1-fraction
            if axis['scale']=='Logarithmic':
                return math.log10(lo)+(math.log10(hi)-math.log10(lo))*fraction
            return lo+(hi-lo)*fraction
        for modifier in ('Control', 'Shift', None):
            r=rect();x,y=round(r[0]+r[2]*.23),round(r[1]+r[3]*.68)
            move(x,y);before=config();wheel(modifier,-1);after=config();r2=rect()
            for key in ('bottom_x','left_y'):
                active=modifier is None or (modifier=='Control' and key=='bottom_x') or (modifier=='Shift' and key=='left_y')
                if not active: assert after[key]==before[key]
                else:
                    assert after[key]['max']-after[key]['min'] < before[key]['max']-before[key]['min']
                    f=(x-r[0])/r[2] if key=='bottom_x' else 1-(y-r[1])/r[3]
                    f2=(x-r2[0])/r2[2] if key=='bottom_x' else 1-(y-r2[1])/r2[3]
                    assert mapped(before[key],f)==pytest.approx(mapped(after[key],f2),rel=2e-5,abs=2e-5)
            wheel(modifier,1)
            for key in ('bottom_x','left_y'):
                assert config()[key]['min']==pytest.approx(before[key]['min'],rel=2e-5,abs=2e-5)
                assert config()[key]['max']==pytest.approx(before[key]['max'],rel=2e-5,abs=2e-5)
        r=rect();x,y=round(r[0]+r[2]*.4),round(r[1]+r[3]*.3)
        before=config();pan(x,y,40,20);after=config()
        for key in ('bottom_x','left_y'):
            span=lambda a: abs(mapped(a,1)-mapped(a,0))
            assert span(after[key])==pytest.approx(span(before[key]),rel=2e-5)
            assert after[key]['min']!=before[key]['min']
        assert not after.get('picked_data')
        # The plot owns wheel zoom, not titles, ticks, or canvas margins.
        r=rect()
        for x,y in [(r[0]-8,r[1]+r[3]/2),(r[0]+r[2]+8,r[1]+r[3]/2),
                    (r[0]+r[2]/2,r[1]-8),(r[0]+r[2]/2,r[1]+r[3]+8)]:
            move(round(x),round(y));before=config();wheel(None,-1)
            assert config()==before

    with figgy.figure(backend='native') as fig:
        exec(setup, {'fig':fig,'ax':fig.axes[0]})
        handle=fig.show(block=False)
        try:
            inputs=Inputs(handle)
            def move(x,y):
                inputs.xdo('mousemove','--window',inputs.wid,x,y);inputs.pump()
            def wheel(modifier,direction):
                if modifier: inputs.xdo('keydown',modifier);inputs.pump()
                inputs.xdo('click',4 if direction<0 else 5);inputs.pump()
                if modifier: inputs.xdo('keyup',modifier);inputs.pump()
            check_navigation(lambda:fig.get_settings()['config'],lambda:inputs.info()['decorations']['data_area'],move,wheel,
                             lambda x,y,dx,dy:drag_native(inputs,(x,y),(dx,dy)))
            inputs.click('visibility_menu');inputs.click('show_chart_title')
            assert not fig.get_settings()['config']['chart_title']['visible']
            inputs.key('Escape');inputs.click('draw_style_menu');inputs.click('style_sketch')
            assert fig.get_settings()['config']['draw_style']['mode']=='sketch'
            assert fig.info['column_uploads']==2
        finally:handle.close();Inputs.pump()
    source="import json\nimport figgyplot as figgy\nfig,ax=figgy.subplots(backend='webgpu')\n"+setup+"\ndisplay(fig.widget())"
    with notebook(tmp_path/transform,source) as (page,execute):
        def rect():
            # Browser measurements are physical canvas pixels; mouse input uses CSS.
            r=page.evaluate('async()=> (await '+ROOT+'.decorations()).data_area.rect');c=page.locator('.figgy-editor canvas').bounding_box()
            size=page.locator('.figgy-editor canvas').evaluate('(c)=>[c.width,c.height]')
            return [c['x']+r[0]*c['width']/size[0],c['y']+r[1]*c['height']/size[1],r[2]*c['width']/size[0],r[3]*c['height']/size[1]]
        def config():
            page.evaluate(ROOT+'.flush()')
            return page.evaluate(ROOT+'.snapshot().config')
        def wheel(modifier,direction):
            if modifier:page.keyboard.down(modifier)
            page.mouse.wheel(0,direction*40);page.wait_for_timeout(100);page.evaluate(ROOT+'.flush()')
            if modifier:page.keyboard.up(modifier)
        def pan(x,y,dx,dy):
            page.mouse.move(x,y);page.mouse.down();page.mouse.move(x+dx,y+dy,steps=5);page.mouse.up()
            page.evaluate(ROOT+'.flush()')
            (tmp_path/'pan-state.json').write_text(json.dumps({'stats':page.evaluate(ROOT+'.stats'),'state':page.evaluate(ROOT+'.snapshot()'),'error':page.locator('.figgy-error').inner_text()}))
        check_navigation(config,rect,page.mouse.move,wheel,pan)
        # A cancelable wheel outside the plot must retain its browser default.
        assert page.locator('.figgy-editor canvas').evaluate('''canvas=>{
            const r=canvas.getBoundingClientRect();
            const e=new WheelEvent('wheel',{clientX:r.x+3,clientY:r.y+3,deltaY:100,bubbles:true,cancelable:true});
            canvas.dispatchEvent(e);return !e.defaultPrevented;
        }''')
        # Verify real wheel input scrolls the notebook, not just a synthetic flag.
        page.locator('.figgy-editor').evaluate('''el=>{
            const spacer=document.createElement('div');spacer.style.height='1800px';
            spacer.dataset.wheelSpacer='';el.closest('.jp-Notebook').append(spacer);
            for(let n=el;n;n=n.parentElement){
                if(/auto|scroll/.test(getComputedStyle(n).overflowY)&&n.scrollHeight>n.clientHeight){
                    n.dataset.wheelScroll='';return;
                }
            }
            throw Error('Notebook scroll container not found');
        }''')
        scroll=page.locator('[data-wheel-scroll]')
        old_scroll=scroll.evaluate('(el)=>el.scrollTop')
        canvas=page.locator('.figgy-editor canvas').bounding_box()
        before=config();page.mouse.move(canvas['x']+5,canvas['y']+5);page.mouse.wheel(0,160)
        page.wait_for_function('(old)=>document.querySelector("[data-wheel-scroll]").scrollTop>old',arg=old_scroll)
        assert config()==before
        scroll.evaluate('(el,old)=>{el.scrollTop=old;document.querySelector("[data-wheel-spacer]").remove();}',old_scroll)
        click_button(page, 'button[data-visibility]');page.locator('[data-visibility="Chart title"]').uncheck()
        assert not config()['chart_title']['visible']
        click_button(page, '[data-style]');click_button(page, '[data-style-mode=sketch]')
        assert config()['draw_style']['mode']=='sketch'
        execute('await fig.sync(); assert fig.get_settings()["config"]["draw_style"]["mode"] == "sketch"')
        assert page.evaluate(ROOT+'.stats.column_uploads')==2


@pytest.mark.skipif(NEEDS_UI, reason='requires X11 input tools and FIGGY_TEST_JUPYTER=1')
def test_cartesian_hosts_share_ticks_and_selected_character_formatting(tmp_path):
    def assert_axis(state, tick):
        axis=state['config']['bottom_x']
        assert axis['line_visible'] is False
        assert axis['label_style']['visible'] is False
        assert axis['tick']==tick
    def assert_rich(state):
        segments=state['config']['chart_title']['text']['segments']
        assert ''.join(v['text'] for v in segments)=='a2b'
        assert segments[0]['greek'] and not segments[1]['greek'] and not segments[2]['greek']
        assert segments[1]['subscript'] and not segments[1]['superscript']
        for i in [0,2]:assert not segments[i]['subscript'] and not segments[i]['superscript']
        for v in segments:assert v['bold'] and v['italic'] and v['underline']
    with figgy.figure(backend='native') as fig:
        ax=fig.axes[0];ax.plot([0,1,2],[0,1,0],id='signal');ax.set_title('a2b')
        handle=fig.show(block=False)
        try:
            inputs=Inputs(handle);inputs.click_rect(inputs.info()['decorations']['axis_bottom'])
            inputs.click('visible');inputs.click('tick_labels_visible');inputs.click('ticks_visible')
            assert_axis(fig.get_settings(),'None')
            for tick in ['None','Inside','Both','Outside']:
                inputs.click('tick_direction');inputs.click('tick_'+tick)
                assert_axis(fig.get_settings(),tick)
            choose_native_object(inputs,'chart_title','panel/main/chart_title')
            # Select just the digit, then apply exclusive super/subscript flags.
            inputs.click('text');inputs.key('Home');inputs.key('Right');inputs.key('shift+Right')
            inputs.click('text_superscript');inputs.click('text_subscript')
            inputs.click('text');inputs.key('Home');inputs.key('shift+Right');inputs.click('text_greek')
            inputs.click('text');inputs.key('ctrl+a')
            for flag in ['bold','italic','underline']:inputs.click('text_'+flag)
            assert_rich(fig.get_settings())
            native=fig.get_settings()['config']['chart_title']['text']['segments']
            assert not inputs.info()['error']
        finally:handle.close();Inputs.pump()
    source="import json\nimport figgyplot as figgy\nfig,ax=figgy.subplots(backend='webgpu')\nax.plot([0,1,2],[0,1,0],id='signal')\nax.set_title('a2b')\ndisplay(fig.widget())"
    with notebook(tmp_path/'text',source) as (page,execute):
        click_button(page, '[data-properties]');ObjectNavigator(page).choose('axis_bottom')
        page.locator('[data-property=visible]').uncheck();page.locator('[data-property=tick_labels_visible]').uncheck();page.locator('[data-property=ticks_visible]').uncheck()
        for tick in ['None','Inside','Both','Outside']:
            page.locator('[data-property=tick_direction]').select_option(tick)
            execute('await fig.sync()');assert_axis(page.evaluate(ROOT+'.snapshot()'),tick)
        ObjectNavigator(page).choose('chart_title')
        def select_range(start,end):
            field=page.locator('[data-property=text]');field.focus()
            field.evaluate('(el,r)=>{el.setSelectionRange(...r);el.dispatchEvent(new Event("select"));}',[start,end])
        def format(flag):
            page.locator(f'[data-format={flag}][data-text-target=chart_title]').click()
            page.evaluate(ROOT+'.flush()')
        select_range(1,2);format('superscript');format('subscript')
        select_range(0,1);format('greek')
        select_range(0,3)
        for flag in ['bold','italic','underline']:format(flag)
        execute('await fig.sync()')
        state=json.loads(execute('print(json.dumps(fig.get_settings()))'))
        assert_rich(state)
        assert state['config']['chart_title']['text']['segments']==native
        # Copy/replay must preserve character formatting, not flatten it to text.
        execute("copy=fig.to_code(); other,bx=figgy.subplots(backend='webgpu'); bx.plot([0,1,2],[2,1,2],id='signal'); exec(copy,{'fig':other}); assert other.get_settings()['config']['chart_title']['text']['segments']==fig.get_settings()['config']['chart_title']['text']['segments']; other.close()")


@pytest.mark.skipif(NEEDS_UI, reason='requires X11 input tools and FIGGY_TEST_JUPYTER=1')
@pytest.mark.parametrize('family', ['nearest', 'bilinear', 'contour', 'contourf', 'matrix_overlay'])
def test_matrix_fit_is_tight_in_both_hosts(tmp_path, family):
    if family in ('nearest', 'bilinear'):
        setup=f"ax.imshow(np.arange(24,dtype=float).reshape(4,6),extent=(-3,3,-2,2),origin='lower',interpolation={family!r})"
    else:
        method='contourf' if family=='matrix_overlay' else family
        setup=f"ax.{method}(np.linspace(-3,3,6),np.linspace(-2,2,4),np.arange(24,dtype=float).reshape(4,6))"
        if family=='matrix_overlay':
            setup+="; ax.contour(np.linspace(-3,3,6),np.linspace(-2,2,4),np.arange(24,dtype=float).reshape(4,6)); ax.imshow(np.arange(24,dtype=float).reshape(4,6),extent=(-3,3,-2,2),origin='lower')"
    expected=(-2.5,2.5,-1.5,1.5) if family=='bilinear' else (-3,3,-2,2)
    def limits(state):
        c=state['config'];return tuple(c[k][b] for k in ['bottom_x','left_y'] for b in ['min','max'])
    with figgy.figure(backend='native') as fig:
        exec(setup, {'np':np,'ax':fig.axes[0]})
        colorbar=fig.get_settings()['config']['colorbar']
        fig.fit();assert limits(fig.get_settings())==pytest.approx(expected)
        fig.fit(padding=.05)
        assert limits(fig.get_settings())[0]<expected[0]
        handle=fig.show(block=False)
        try:
            inputs=Inputs(handle);inputs.click('fit')
            assert limits(fig.get_settings())==pytest.approx(expected)
            assert fig.get_settings()['config']['colorbar']==colorbar
        finally:handle.close();Inputs.pump()
    source="import json\nimport numpy as np\nimport figgyplot as figgy\nfig,ax=figgy.subplots(backend='webgpu')\n"+setup+"\nfig.fit(padding=.05)\ndisplay(fig.widget())"
    with notebook(tmp_path/family,source) as (page,execute):
        click_button(page, '[data-fit]');execute('await fig.sync()')
        state=json.loads(execute('print(json.dumps(fig.get_settings()))'))
        assert limits(state)==pytest.approx(expected)
        execute('fig.fit(padding=.05); await fig.sync()')
        assert page.evaluate(ROOT+'.snapshot().config.bottom_x.min')<expected[0]
        # Kernel metadata remains sufficient after binary transfer release.
        execute('fig.fit(); await fig.sync()')
        state=json.loads(execute('print(json.dumps(fig.get_settings()))'))
        assert limits(state)==pytest.approx(expected)
        assert state['config']['colorbar']==colorbar


@pytest.mark.skipif(NEEDS_UI, reason='requires X11 input tools and FIGGY_TEST_JUPYTER=1')
def test_axis_and_color_log_scale_editing_matches_both_hosts(tmp_path):
    setup="ax.imshow(np.array([[1.,10.],[100.,1000.]]),extent=(1,3,1,3),origin='lower',cmap='gray',vmin=1,vmax=1000,id='field')"
    def sample(pixels, rect):
        x,y,w,h=rect
        return float(np.asarray(pixels)[round(y+h*.75),round(x+w*.75),:3].mean())
    def color_min(fig, value):
        state=fig.get_settings();state['config']['colorbar']['axis']['min']=value;fig.apply_settings(state)
    def assert_scale(state, key, scale):
        axis=state['config']['colorbar']['axis'] if key=='colorbar' else state['config'][key]
        assert axis['scale']==scale
        lo,hi=(1,1000) if key=='colorbar' else (1,3)
        assert (axis['min'],axis['max'])==pytest.approx((lo,hi))
        assert axis['major_spacing']==pytest.approx(1 if scale=='Logarithmic' else (hi-lo)/5)
    with figgy.figure(backend='native') as fig:
        ax=fig.axes[0];exec(setup,{'np':np,'ax':ax});ax.set_xlim(-1,3)
        handle=fig.show(block=False)
        try:
            inputs=Inputs(handle)
            def choose(control, value):
                inputs.click(control);inputs.click(control+'_'+value)
            inputs.click_rect(inputs.info()['decorations']['axis_bottom'])
            before=fig.get_settings();choose('axis_scale','Logarithmic')
            assert_scale(fig.get_settings(),'bottom_x','Logarithmic')
            assert fig.get_settings()['config']['top_x']=={**before['config']['top_x'], **{key:fig.get_settings()['config']['bottom_x'][key] for key in ['min','max','scale','major_spacing']}}
            assert not inputs.info()['error']
            for target,key in [('axis_bottom','bottom_x'),('axis_left','left_y')]:
                inputs.click_rect(inputs.info()['decorations'][target])
                for scale in ['Logarithmic','Linear']:
                    choose('axis_scale',scale);assert_scale(fig.get_settings(),key,scale)
            inputs.click_rect(inputs.info()['decorations']['colorbar'])
            color_min(fig,0);inputs.pump()
            choose('color_scale','Logarithmic')
            assert_scale(fig.get_settings(),'colorbar','Logarithmic')
            assert not inputs.info()['error']
            choose('color_scale','Linear')
            bounds=json.loads(fig._native.bounds_json('data_area'))['rect']
            linear=sample(fig.render_rgba(),bounds)
            choose('color_scale','Logarithmic');assert_scale(fig.get_settings(),'colorbar','Logarithmic')
            logarithmic=sample(fig.render_rgba(),bounds)
            assert logarithmic>linear+30  # Value 10 moves from 9/999 to 1/3 of the colormap.
            native=fig.get_settings()['config']['colorbar']['axis']
            assert not inputs.info()['error']
        finally:handle.close();Inputs.pump()
    source="import json\nimport numpy as np\nimport figgyplot as figgy\nfig,ax=figgy.subplots(backend='webgpu')\n"+setup+"\nax.set_xlim(-1,3)\ndisplay(fig.widget())"
    with notebook(tmp_path/'scales',source) as (page,execute):
        click_button(page, '[data-properties]')
        # Saved 0.17 settings must also pass the browser's local installer,
        # before any kernel round trip can normalize the renderer stamp.
        legacy = page.evaluate(ROOT+'.snapshot()')
        legacy['renderer_version'] = '0.17.0'
        legacy['config']['chart_title']['offset_x'] = 7
        page.locator('[data-advanced]').evaluate('element=>element.open=true')
        page.locator('[data-settings]').fill(json.dumps(legacy))
        page.locator('[data-apply]').click()
        page.wait_for_function(ROOT+'.snapshot().config.chart_title.offset_x===7')
        assert page.evaluate(ROOT+'.snapshot().renderer_version') == '0.18.1'
        page.locator('[data-advanced]').evaluate('element=>element.open=false')
        target=ObjectNavigator(page)
        def choose(control, value):
            page.locator(f'[data-property={control}]').select_option(value);page.evaluate(ROOT+'.flush()')
        target.choose('axis_bottom');before=page.evaluate(ROOT+'.snapshot()')
        choose('axis_scale','Logarithmic')
        assert_scale(page.evaluate(ROOT+'.snapshot()'),'bottom_x','Logarithmic')
        current=page.evaluate(ROOT+'.snapshot()')
        assert current['config']['top_x']=={**before['config']['top_x'], **{key:current['config']['bottom_x'][key] for key in ['min','max','scale','major_spacing']}}
        assert page.locator('[data-property=axis_scale]').input_value()=='Logarithmic'
        assert not page.locator('.figgy-error').inner_text()
        for name,key in [('axis_bottom','bottom_x'),('axis_left','left_y')]:
            target.choose(name)
            for scale in ['Logarithmic','Linear']:
                choose('axis_scale',scale);assert_scale(page.evaluate(ROOT+'.snapshot()'),key,scale)
        # Both the field series and the colorbar itself expose the same controls.
        target.choose('field');assert page.locator('[data-property=color_scale]').count()==1
        target.choose('colorbar')
        execute("s=fig.get_settings(); s['config']['colorbar']['axis']['min']=0; fig.apply_settings(s); await fig.sync()")
        choose('color_scale','Logarithmic')
        assert_scale(page.evaluate(ROOT+'.snapshot()'),'colorbar','Logarithmic')
        assert page.locator('[data-property=color_scale]').input_value()=='Logarithmic'
        assert not page.locator('.figgy-error').inner_text()
        choose('color_scale','Linear')
        from PIL import Image
        path=tmp_path/'linear.png';execute(f'await fig.savefig_async({str(path)!r})')
        box=page.evaluate('async()=> (await '+ROOT+'.decorations()).data_area.rect')
        width,height=page.locator('.figgy-editor canvas').evaluate('(c)=>[c.width,c.height]')
        rect=[box[0]*960/width,box[1]*600/height,box[2]*960/width,box[3]*600/height]
        linear=sample(Image.open(path).convert('RGB'),rect)
        choose('color_scale','Logarithmic');execute('await fig.sync()')
        assert_scale(page.evaluate(ROOT+'.snapshot()'),'colorbar','Logarithmic')
        path=tmp_path/'logarithmic.png';execute(f'await fig.savefig_async({str(path)!r})')
        assert sample(Image.open(path).convert('RGB'),rect)>linear+30
        state=json.loads(execute('print(json.dumps(fig.get_settings()))'))
        assert state['config']['colorbar']['axis']==native
        execute("code=fig.to_code(); other,bx=figgy.subplots(backend='webgpu'); bx.imshow(np.ones((2,2)),id='field'); exec(code,{'fig':other}); assert other.get_settings()['config']['colorbar']['axis']['scale']=='Logarithmic'; other.close()")


@pytest.mark.skipif(NEEDS_UI, reason='requires X11 input tools and FIGGY_TEST_JUPYTER=1')
@pytest.mark.parametrize('positive_samples', [True, False])
def test_log_color_ui_masks_nonpositive_samples_in_both_hosts(tmp_path, positive_samples):
    """Noisy or entirely nonpositive data must never block the log selector."""
    values=[[-2.,0.,10.],[100.,1000.,10000.]] if positive_samples else [[-2.,0.,-1.],[-3.,0.,-4.]]
    expected=(10,10000) if positive_samples else (1,10)
    setup=f"data=np.array({values!r}); ax.imshow(data,extent=(0,3,0,2),origin='lower',cmap='gray',id='field'); ax.grid(False)"
    def check_state(state, original_series):
        axis=state['config']['colorbar']['axis']
        assert axis['scale']=='Logarithmic'
        assert (axis['min'],axis['max'])==pytest.approx(expected)
        assert state['series']==original_series
    def check_pixels(pixels, rect):
        x,y,w,h=rect
        def pixel(fx,fy):
            return np.asarray(pixels)[round(y+h*fy),round(x+w*fx),:3]
        # Negative and zero cells disappear, revealing the white chart background.
        assert np.all(pixel(1/6,.75)>245)
        assert np.all(pixel(.5,.75)>245)
        if positive_samples:
            # Value 1000 is two of three logarithmic decades above the lower bound.
            assert 150<float(pixel(.5,.25).mean())<190
        else:
            assert np.all(pixel(.5,.25)>245)
    with figgy.figure(backend='native') as fig:
        namespace={'np':np,'ax':fig.axes[0]};exec(setup,namespace)
        original_series=fig.get_settings()['series'];uploads=fig.info['column_uploads']
        handle=fig.show(block=False)
        try:
            inputs=Inputs(handle)
            inputs.click_rect(inputs.info()['decorations']['colorbar'])
            inputs.click('color_scale');inputs.click('color_scale_Logarithmic')
            check_state(fig.get_settings(),original_series)
            assert not inputs.info()['error']
            check_pixels(fig.render_rgba(),json.loads(fig._native.bounds_json('data_area'))['rect'])
            np.testing.assert_array_equal(namespace['data'],values)
            assert fig.info['column_uploads']==uploads
            native_axis=fig.get_settings()['config']['colorbar']['axis']
        finally:handle.close();Inputs.pump()
    source="import json\nimport numpy as np\nimport figgyplot as figgy\nfig,ax=figgy.subplots(backend='webgpu')\n"+setup+"\ndisplay(fig.widget())"
    with notebook(tmp_path/('noisy' if positive_samples else 'nonpositive'),source) as (page,execute):
        original_series=page.evaluate(ROOT+'.snapshot().series')
        uploads=page.evaluate(ROOT+'.stats.column_uploads')
        click_button(page, '[data-properties]')
        ObjectNavigator(page).choose('colorbar')
        page.locator('[data-property=color_scale]').select_option('Logarithmic')
        page.evaluate(ROOT+'.flush()');execute('await fig.sync()')
        state=json.loads(execute('print(json.dumps(fig.get_settings()))'))
        check_state(state,original_series)
        assert state['config']['colorbar']['axis']==native_axis
        assert not page.locator('.figgy-error').inner_text()
        from PIL import Image
        path=tmp_path/'log-masked.png';execute(f'await fig.savefig_async({str(path)!r})')
        box=page.evaluate('async()=> (await '+ROOT+'.decorations()).data_area.rect')
        width,height=page.locator('.figgy-editor canvas').evaluate('(c)=>[c.width,c.height]')
        rect=[box[0]*960/width,box[1]*600/height,box[2]*960/width,box[3]*600/height]
        check_pixels(Image.open(path).convert('RGB'),rect)
        execute(f'np.testing.assert_array_equal(data,{values!r})')
        assert page.evaluate(ROOT+'.stats.column_uploads')==uploads


@pytest.mark.skipif(NEEDS_UI, reason='requires X11 input tools and FIGGY_TEST_JUPYTER=1')
def test_log_axis_ui_breaks_lines_at_nonpositive_samples_in_both_hosts(tmp_path):
    """A log view keeps valid segments without connecting across masked samples."""
    setup="x=np.arange(1.,7.); y=np.array([1.,10.,-1.,0.,10.,100.]); ax.plot(x,y,color='blue',linewidth=3,id='noisy'); ax.set_xlim(.5,6.5); ax.set_ylim(-5,100); ax.grid(False)"
    def check_state(state, before):
        axis=state['config']['left_y']
        assert axis['scale']=='Logarithmic'
        assert (axis['min'],axis['max'])==pytest.approx((1,100))
        assert state['series']==before['series']
        # The matched Y pair shares the fitted positive minimum, scale and
        # derived tick step; every other field on each edge stays unchanged.
        for key in ('left_y','right_y'):
            assert state['config'][key]=={**before['config'][key],
                                         'min':1.,'scale':'Logarithmic','major_spacing':1.}
        for key in ('bottom_x','top_x'):
            assert state['config'][key]==before['config'][key]
    def check_pixels(pixels, rect):
        x,y,w,h=rect
        pixels=np.asarray(pixels)
        def point(vx,vy):
            return round(x+w*(vx-.5)/6),round(y+h*(1-np.log10(vy)/2))
        for vx,vy in [(1.5,np.sqrt(10)),(5.5,np.sqrt(1000))]:
            px,py=point(vx,vy)
            region=pixels[py-4:py+5,px-4:px+5,:3]
            assert np.any((region[:,:,2]>150)&(region[:,:,0]<100)), 'positive line segment disappeared'
        # The old clamp-to-tiny-positive behavior left downward strokes near
        # x=2 and x=5. This rectangle excludes both valid positive segments.
        x0,y0=point(1.9,5)
        x1,y1=point(5.1,1.5)
        gap=pixels[y0:y1,x0:x1,:3]
        assert gap.size and np.all(gap>245), 'nonpositive samples produced a false connecting stroke'
    with figgy.figure(backend='native') as fig:
        namespace={'np':np,'ax':fig.axes[0]};exec(setup,namespace)
        before=fig.get_settings();uploads=fig.info['column_uploads']
        handle=fig.show(block=False)
        try:
            inputs=Inputs(handle)
            inputs.click_rect(inputs.info()['decorations']['axis_left'])
            inputs.click('axis_scale');inputs.click('axis_scale_Logarithmic')
            check_state(fig.get_settings(),before)
            assert not inputs.info()['error']
            check_pixels(fig.render_rgba(),json.loads(fig._native.bounds_json('data_area'))['rect'])
            np.testing.assert_array_equal(namespace['x'],np.arange(1.,7.))
            np.testing.assert_array_equal(namespace['y'],[1.,10.,-1.,0.,10.,100.])
            assert fig.info['column_uploads']==uploads
            native_axis=fig.get_settings()['config']['left_y']
        finally:handle.close();Inputs.pump()
    source="import json\nimport numpy as np\nimport figgyplot as figgy\nfig,ax=figgy.subplots(backend='webgpu')\n"+setup+"\ndisplay(fig.widget())"
    with notebook(tmp_path/'line-log-gap',source) as (page,execute):
        before=page.evaluate(ROOT+'.snapshot()');uploads=page.evaluate(ROOT+'.stats.column_uploads')
        click_button(page, '[data-properties]')
        ObjectNavigator(page).choose('axis_left')
        page.locator('[data-property=axis_scale]').select_option('Logarithmic')
        page.evaluate(ROOT+'.flush()');execute('await fig.sync()')
        state=json.loads(execute('print(json.dumps(fig.get_settings()))'))
        check_state(state,before)
        assert state['config']['left_y']==native_axis
        assert not page.locator('.figgy-error').inner_text()
        from PIL import Image
        path=tmp_path/'line-log-gap.png';execute(f'await fig.savefig_async({str(path)!r})')
        box=page.evaluate('async()=> (await '+ROOT+'.decorations()).data_area.rect')
        width,height=page.locator('.figgy-editor canvas').evaluate('(c)=>[c.width,c.height]')
        rect=[box[0]*960/width,box[1]*600/height,box[2]*960/width,box[3]*600/height]
        check_pixels(Image.open(path).convert('RGB'),rect)
        execute('np.testing.assert_array_equal(x,np.arange(1.,7.)); np.testing.assert_array_equal(y,[1.,10.,-1.,0.,10.,100.])')
        assert page.evaluate(ROOT+'.stats.column_uploads')==uploads


@pytest.mark.skipif(NEEDS_UI, reason='requires X11 input tools and FIGGY_TEST_JUPYTER=1')
@pytest.mark.parametrize('orientation', ['vertical','horizontal'])
def test_histogram_selected_bin_readout_and_arrows_match_both_hosts(tmp_path, orientation):
    setup=f"samples=np.array([.25,.5,1.5,3.5]); counts,edges,artist=ax.hist(samples,bins=[0,1,2,4],density=True,orientation={orientation!r},id='bins'); ax.grid(False)"
    key='Right' if orientation=='vertical' else 'Up'
    def logical_point(state, rect):
        cfg=state['config'];x,y=(.5,.25) if orientation=='vertical' else (.25,.5)
        xaxis,yaxis=cfg['bottom_x'],cfg['left_y']
        return (rect[0]+rect[2]*(x-xaxis['min'])/(xaxis['max']-xaxis['min']),
                rect[1]+rect[3]*(1-(y-yaxis['min'])/(yaxis['max']-yaxis['min'])))
    def check(values,index):
        assert int(values['index'])==index
        assert float(values['bin_start'])==index
        assert float(values['bin_end'])==index+1
        assert float(values['value'])==pytest.approx(.5 if index==0 else .25)
        assert values['orientation']==orientation.title()
        assert 'count' not in values
    with figgy.figure(backend='native') as fig:
        namespace={'np':np,'ax':fig.axes[0]};exec(setup,namespace)
        namespace['samples'][:]=-99
        original_series=fig.get_settings()['series'];uploads=fig.info['column_uploads']
        handle=fig.show(block=False)
        try:
            inputs=Inputs(handle)
            rect=json.loads(fig._native.bounds_json('data_area'))['rect']
            point=native_point(inputs.info(),logical_point(fig.get_settings(),rect))
            inputs.click_rect([*point,0,0])
            assert inputs.info()['properties_open']
            check(inputs.info()['picked_values'],0)
            inputs.key(key);check(inputs.info()['picked_values'],1)
            native=inputs.info()['picked_values']
            assert not inputs.info()['error']
            assert fig.get_settings()['series']==original_series
            assert fig.info['column_uploads']==uploads
            assert fig.info['rgba_readbacks']==fig.info['png_encodes']==0
            inputs.key('Escape');assert inputs.info()['picked_values'] is None
        finally:handle.close();Inputs.pump()
    source="import json\nimport numpy as np\nimport figgyplot as figgy\nfig,ax=figgy.subplots(backend='webgpu')\n"+setup+"\nsamples[:]=-99\ndisplay(fig.widget())"
    with notebook(tmp_path/('histogram-'+orientation),source) as (page,execute):
        original_series=page.evaluate(ROOT+'.snapshot().series')
        uploads=page.evaluate(ROOT+'.stats.column_uploads')
        box=page.evaluate('async()=> (await '+ROOT+'.decorations()).data_area.rect')
        width,height=page.locator('.figgy-editor canvas').evaluate('(c)=>[c.width,c.height]')
        rect=[box[0]*960/width,box[1]*600/height,box[2]*960/width,box[3]*600/height]
        point=logical_point(page.evaluate(ROOT+'.snapshot()'),rect)
        page.mouse.click(*browser_point(page,point))
        page.locator('[data-selected-value=bin_start]').wait_for(state='visible')
        def readout():
            return page.locator('[data-selected-value]').evaluate_all("rows=>Object.fromEntries(rows.map(r=>[r.dataset.selectedValue,r.textContent.split(': ')[1]]))")
        check(readout(),0)
        page.locator('.figgy-editor canvas').press('Arrow'+key)
        page.wait_for_function("document.querySelector('[data-selected-value=index]')?.textContent==='Index: 1'")
        check(readout(),1)
        for name in ['index','bin_start','bin_end','value']:
            assert float(readout()[name])==pytest.approx(native[name])
        execute('await fig.sync()')
        assert page.evaluate(ROOT+'.snapshot().series')==original_series
        assert page.evaluate(ROOT+'.stats.column_uploads')==uploads
        assert page.evaluate(ROOT+'.stats.png_exports')==0
        assert not page.locator('.figgy-error').inner_text()
        page.locator('.figgy-editor canvas').press('Escape');page.evaluate(ROOT+'.flush()')
        assert page.locator('[data-selected-data]').is_hidden()


@pytest.mark.skipif(NEEDS_UI, reason='requires X11 input tools and FIGGY_TEST_JUPYTER=1')
def test_empty_titles_can_be_enabled_edited_and_restored_in_both_hosts(tmp_path):
    titles=[('chart_title','Chart title',None),('axis_title_bottom','X axis title','bottom_x'),
            ('axis_title_left','Y axis title','left_y'),('axis_title_top','Top axis title','top_x'),
            ('axis_title_right','Right axis title','right_y')]
    setup="ax.plot([0,1,2],[0,1,0]); s=fig.get_settings(); s['config']['chart_title']['top_margin']=0; s['config']['chart_title']['visible']=False; fig.apply_settings(s)"
    def title(state,axis):
        return state['config'][axis]['title_option'] if axis else state['config']['chart_title']
    def check_enabled(state,axis,label):
        value=title(state,axis)
        assert value['visible']
        assert ''.join(s['text'] for s in value['text']['segments'])==label
        if axis: assert state['config'][axis]['out_margin']>=value['text']['font_size']*2
        else: assert value['top_margin']>0
    native={}
    with figgy.figure(backend='native') as fig:
        exec(setup,{'fig':fig,'ax':fig.axes[0]})
        handle=fig.show(block=False)
        try:
            inputs=Inputs(handle)
            for target,label,axis in titles:
                assert not title(fig.get_settings(),axis)['text']['segments']
                inputs.click('visibility_menu');inputs.click('show_'+target);inputs.click('visibility_menu')
                check_enabled(fig.get_settings(),axis,label)
                assert inputs.info()['properties_open'] and 'text' in inputs.info()['controls']
                box=inputs.info()['decorations'][target]
                assert box[2]>0 and box[3]>0
                inputs.click('text');inputs.key('ctrl+a');inputs.click('text_bold')
                rich=title(fig.get_settings(),axis)['text']
                assert all(s['bold'] for s in rich['segments'])
                inputs.click('visibility_menu');inputs.click('show_'+target);inputs.click('visibility_menu')
                assert not title(fig.get_settings(),axis)['visible']
                inputs.click('visibility_menu');inputs.click('show_'+target);inputs.click('visibility_menu')
                assert title(fig.get_settings(),axis)['text']==rich
                native[target]=rich['segments']
            assert not inputs.info()['error']
        finally: handle.close();Inputs.pump()
    source="import json\nimport figgyplot as figgy\nfig,ax=figgy.subplots(backend='webgpu')\n"+setup+"\ndisplay(fig.widget())"
    with notebook(tmp_path/'empty_titles',source) as (page,execute):
        for target,label,axis in titles:
            click_button(page, 'button[data-visibility]')
            toggle=page.locator(f'input[data-visibility="{label}"]')
            assert not toggle.is_checked()
            toggle.check();page.evaluate(ROOT+'.flush()')
            click_button(page, 'button[data-visibility]')
            check_enabled(page.evaluate(ROOT+'.snapshot()'),axis,label)
            assert page.locator('.figgy-properties').is_visible()
            assert ObjectNavigator(page).selected()==target
            field=page.locator('[data-property=text]')
            assert field.input_value()==label
            field.focus();field.evaluate('(el)=>{el.select();el.dispatchEvent(new Event("select"));}')
            page.locator(f'[data-format=bold][data-text-target={target}]').click()
            page.evaluate(ROOT+'.flush()')
            rich=title(page.evaluate(ROOT+'.snapshot()'),axis)['text']
            assert rich['segments']==native[target]
            click_button(page, 'button[data-visibility]');toggle.uncheck();page.evaluate(ROOT+'.flush()')
            assert not title(page.evaluate(ROOT+'.snapshot()'),axis)['visible']
            toggle.check();page.evaluate(ROOT+'.flush()')
            assert title(page.evaluate(ROOT+'.snapshot()'),axis)['text']==rich
            click_button(page, 'button[data-visibility]')
        execute('await fig.sync()')
        assert page.locator('.figgy-error').inner_text()==''


@pytest.mark.skipif(NEEDS_UI, reason='requires X11 input tools and FIGGY_TEST_JUPYTER=1')
@pytest.mark.parametrize('dimension', ['x', 'y'])
def test_matching_opposite_axes_share_only_ui_edited_fields(tmp_path, dimension):
    """UI conveniences pair matching coordinates; raw SSOT and secondary axes remain exact."""
    import copy
    import subprocess
    primary,opposite=('bottom_x','top_x') if dimension=='x' else ('left_y','right_y')
    targets={'bottom_x':'axis_bottom','top_x':'axis_top','left_y':'axis_left','right_y':'axis_right'}
    setup="""ax.plot([1,10,100],[1,10,100],id='signal')
for key in ['bottom_x','top_x','left_y','right_y']:
    fig.configure(config={key:{'min':1.,'max':100.,'scale':'Linear','major_spacing':10.}})
for key in ['top_x','right_y']:
    fig.configure(config={key:{'label_style':{'visible':False,'font_size':11.,'significant_digits':6},'title_option':{'offset_x':3.,'offset_y':4.}}})
"""
    axes=['bottom_x','top_x','left_y','right_y']
    snapshots=[]
    def check_edit(get_state, edit, source, field, value, linked=True):
        before=get_state()['config']
        edit(targets[source],field,value)
        after=get_state()['config']
        snapshots.append({'axis':source,'field':field,'value':value,'before':before,'after':after})
        (tmp_path/'axis-state-transitions.json').write_text(json.dumps(snapshots))
        changed={'label_format':['label_style','format'],'significant_digits':['label_style','significant_digits'],
                 'tick_labels_visible':['label_style','visible'],'tick_direction':['tick'],'axis_scale':['scale']}.get(field,[field])
        destination=opposite if source==primary else primary
        expected=copy.deepcopy({key:before[key] for key in axes})
        for key in [source,destination] if linked else [source]:
            node=expected[key]
            for component in changed[:-1]: node=node[component]
            node[changed[-1]]=value
            if field=='axis_scale':
                # The scale control also derives its tick step; no other style is copied.
                expected[key]['major_spacing']=1. if value=='Logarithmic' else 20.
        assert {key:after[key] for key in axes}==expected
    def scenario(get_state,edit,apply_patch):
        check_edit(get_state,edit,primary,'major_spacing',7.)
        check_edit(get_state,edit,opposite,'tick_direction','Both')
        check_edit(get_state,edit,primary,'label_format','Scientific')
        check_edit(get_state,edit,opposite,'significant_digits',2)
        check_edit(get_state,edit,opposite,'tick_labels_visible',True)
        check_edit(get_state,edit,primary,'axis_scale','Logarithmic')
        check_edit(get_state,edit,opposite,'max',101.)
        # Raw settings can deliberately split the pair, without changing the other side.
        before=get_state()['config'];apply_patch({opposite:{'max':201.}})
        expected=copy.deepcopy(before);expected[opposite]['max']=201.
        assert get_state()['config']==expected
        check_edit(get_state,edit,primary,'major_spacing',3.,linked=False)
        check_edit(get_state,edit,primary,'axis_scale','Linear',linked=False)
        before=get_state()['config'];apply_patch({primary:{'label_style':{'format':'Power'}}})
        expected=copy.deepcopy(before);expected[primary]['label_style']['format']='Power'
        assert get_state()['config']==expected
        return {key:get_state()['config'][key] for key in axes}
    with figgy.figure(backend='native') as fig:
        exec(setup,{'fig':fig,'ax':fig.axes[0]})
        handle=fig.show(block=False)
        try:
            inputs=Inputs(handle)
            def click_control(key):
                # Inputs scrolls the actual property viewport, below the object tree.
                inputs.click(key)
            def edit(target,field,value):
                inputs.click_rect(inputs.info()['decorations'][target])
                assert inputs.info()['selected']==target
                click_control(field)
                if field in ['label_format','tick_direction','axis_scale']:
                    prefix='tick' if field=='tick_direction' else field
                    if field=='axis_scale' and value=='Linear':
                        from PIL import ImageGrab
                        ImageGrab.grab(xdisplay=os.environ['DISPLAY']).save(tmp_path/'native-linear-menu.png')
                    inputs.click(prefix+'_'+value)
                elif field!='tick_labels_visible':
                    inputs.key('ctrl+a');inputs.xdo('type','--clearmodifiers',str(value));inputs.key('Return')
                assert not inputs.info()['error']
            def patch(value):
                fig.configure(config=value);inputs.pump()
            native=scenario(fig.get_settings,edit,patch)
            inputs.click('copy')
            code=subprocess.check_output(['xclip','-selection','clipboard','-o'],text=True,timeout=3)
            assert code==fig.to_code()
            with figgy.figure(backend='native') as other:
                other.axes[0].plot([1,10,100],[1,10,100],id='signal')
                exec(code,{'fig':other})
                assert other.get_settings()['config']==fig.get_settings()['config']
        finally:
            (tmp_path/'native-axis-input-events.json').write_text(json.dumps(inputs.events))
            (tmp_path/'native-axis-settings.json').write_text(json.dumps(fig.get_settings()))
            handle.close();Inputs.pump()
    source="import json\nimport figgyplot as figgy\nfig,ax=figgy.subplots(backend='webgpu')\n"+setup+"display(fig.widget())"
    with notebook(tmp_path/('paired_'+dimension),source) as (page,execute):
        click_button(page, '[data-properties]')
        def edit(target,field,value):
            ObjectNavigator(page).choose(target)
            control=page.locator(f'[data-property={field}]')
            if field in ['label_format','tick_direction','axis_scale']: control.select_option(value)
            elif field=='tick_labels_visible': control.set_checked(value)
            else: control.fill(str(value));control.press('Tab')
            page.evaluate(ROOT+'.flush()')
            assert not page.locator('.figgy-error').inner_text()
        def patch(value):
            execute(f'fig.configure(config={value!r}); await fig.sync()')
        browser=scenario(lambda:page.evaluate(ROOT+'.snapshot()'),edit,patch)
        assert browser==native
        execute('await fig.sync()')
        kernel=json.loads(execute('print(json.dumps(fig.get_settings()))'))
        assert {key:kernel['config'][key] for key in axes}==browser
        click_button(page, '[data-copy]');page.evaluate(ROOT+'.flush()')
        code=page.locator('textarea[data-code]').input_value()
        assert code
        execute(f"code={code!r}; assert code==fig.to_code(); other,bx=figgy.subplots(backend='webgpu'); bx.plot([1,10,100],[1,10,100],id='signal'); exec(code,{{'fig':other}}); assert other.get_settings()['config']==fig.get_settings()['config']; other.close()")


FEATURE_018 = {
    'maps': "ax.scatter([0,1,2],[2,1,3],c=[1,2,4],s=[2,5,9],id='signal')",
    'child_maps': "fig.set_layout([['empty','mapped']]); ax=fig.subplots['mapped'].axes; ax.scatter([0,1,2],[2,1,3],c=[1,2,4],s=[2,5,9],id='signal')",
    'mixed_styles': "fig.set_layout([['line','field']]); ax=fig.subplots['line'].axes; ax.plot([0,1,2],[1,2,1],id='signal'); ax.set_draw_style('sketch'); fig.subplots['field'].imshow([[0,1],[1,0]],id='field')",
    'vector_points': "ax.quiver([0,1,2],[0,2,1],[1,0,-1],[0,1,1],values=[1,2,3],scale=20,id='signal')",
    'vector_grid': "ax.quiver([0,1],[0,1],[[1,0],[0,-1]],[[0,1],[1,0]],values=[[1,2],[3,4]],scale=20,id='signal')",
    'fill_steps': "ax.fill_between([0,1,2],[2,4,3],[1,1,2],id='band'); ax.step([0,1,2],[1,2,1],where='post',id='signal')",
    'polar': "ax.set_polar(); ax.plot([0,90,180,270,360],[1,2,3,2,1],id='signal'); ax.text(.5,.5,'Note',coords='ratio',id='note')",
    'annotations': "ax.plot([0,1,2],[1,2,0],id='signal'); ax.axvspan(.5,1.,id='span'); ax.arrow(.2,.2,.4,.3,coords='ratio',id='arrow')",
    'panels': "fig.set_layout([['left','right']]); ax=fig.subplots['left'].axes; ax.plot([0,1,2],[1,2,1],color='red',id='signal'); fig.subplots['right'].plot([0,1,2],[3,1,2],color='blue',id='other'); ax.activate()",
    'secondary_y': "ax.plot([0,1,2],[1,2,1],id='signal'); twin=ax.twinx(id='pressure'); twin.plot([0,1,2],[100,200,150],color='red',id='other'); ax.activate()",
}


@pytest.mark.skipif(NEEDS_UI, reason='requires X11 input tools and FIGGY_TEST_JUPYTER=1')
@pytest.mark.parametrize('feature', FEATURE_018)
def test_renderer_018_features_display_edit_and_export_in_both_hosts(tmp_path, feature):
    from PIL import Image
    setup = FEATURE_018[feature]
    with figgy.Figure(backend='native') as fig:
        ax = fig.axes[0]
        exec(setup, {'fig': fig, 'ax': ax})
        handle = fig.show(block=False)
        try:
            inputs = Inputs(handle)
            info = inputs.info()
            assert info['surface_frames'] > 0 and not info['error']
            assert fig.info['rgba_readbacks'] == fig.info['png_encodes'] == 0
            # Settings acceptance redraws the actual surface with all panels.
            state = fig.get_settings()
            state['config']['grid']['show_major_x'] = False
            fig.apply_settings(state)
            inputs.pump()
            assert not inputs.info()['error']
            native = fig.render_rgba(scale=2)
            assert native.shape == (1200, 1920, 4)
            assert np.any(native[..., :3] < 150)
            if feature == 'panels':
                for half in (native[:, :960, :3], native[:, 960:, :3]):
                    assert np.count_nonzero(half.max(axis=2)-half.min(axis=2) > 80) > 100
        finally:
            handle.close()
            Inputs.pump()
    source = "import json\nimport figgyplot as figgy\nfig,ax=figgy.subplots(backend='webgpu')\n" + setup + "\ndisplay(fig.widget())"
    with notebook(tmp_path/feature, source) as (page, execute):
        click_button(page, '[data-properties]')
        page.locator('[data-advanced]').evaluate('(el)=>el.open=true')
        state = page.evaluate(ROOT+'.snapshot()')
        state['config']['grid']['show_major_x'] = False
        page.locator('[data-settings]').fill(json.dumps(state))
        page.locator('[data-apply]').click()
        page.evaluate(ROOT+'.flush()')
        execute('await fig.sync()')
        assert not page.locator('.figgy-error').inner_text()
        accepted = json.loads(execute('print(json.dumps(fig.get_settings()))'))
        assert accepted['schema_version'] == 2
        assert not accepted['config']['grid']['show_major_x']
        if feature == 'child_maps':
            assert 'colorbar' not in accepted['config']
            assert 'colorbar' not in page.evaluate(ROOT+'.snapshot().config')
        if feature == 'panels':
            ObjectNavigator(page).panel('right')
            page.evaluate(ROOT+'.flush()')
            assert page.evaluate(ROOT+'.snapshot().config.active_layer') == {'Subplot': 0}
            ObjectNavigator(page).choose('subplot_0:chart_title')
            title = page.locator('[data-property=text]')
            title.fill('Right panel');title.dispatch_event('change')
            page.evaluate(ROOT+'.flush()')
            execute('await fig.sync()')
            accepted = json.loads(execute('print(json.dumps(fig.get_settings()))'))
            rich = accepted['config']['subplots'][0]['config']['chart_title']['text']
            assert ''.join(s['text'] for s in rich['segments']) == 'Right panel'
            assert not accepted['config']['chart_title']['text']['segments']
        path = tmp_path/'export.png'
        execute(f'await fig.savefig_async({str(path)!r},scale=2)')
        pixels = np.asarray(Image.open(path).convert('RGB'))
        assert pixels.shape == (1200, 1920, 3)
        assert np.any(pixels < 150)
        if feature == 'panels':
            for half in (pixels[:, :960], pixels[:, 960:]):
                assert np.count_nonzero(half.max(axis=2)-half.min(axis=2) > 80) > 100


@pytest.mark.skipif(NEEDS_UI, reason='requires X11 input tools and FIGGY_TEST_JUPYTER=1')
@pytest.mark.parametrize('kind', ['cartesian', 'radar'])
def test_annotation_layer_drag_and_endpoint_resize_match_hosts(tmp_path, kind):
    import copy
    setup = "ax.plot([0,1,2],[1,2,0],id='signal')" if kind == 'cartesian' else "ax.radar(['A','B','C'],[2,4,3])"
    setup += "; ax.arrow(.25,.3,.25,.15,coords='ratio',id='arrow').select()"
    if kind == 'cartesian': setup += "; ax.activate()"  # The annotation layer starts inactive.
    def geometry(state):
        owner = state['config'] if kind == 'cartesian' else state['radar']
        return owner['annotations']['items'][0]['kind']['Arrow']
    with figgy.Figure(backend='native') as fig:
        exec(setup, {'fig': fig, 'ax': fig.axes[0]})
        handle = fig.show(block=False)
        try:
            inputs = Inputs(handle)
            target = 'annotation:arrow' if kind == 'cartesian' else 'annotation_0'
            box = json.loads(fig._native.bounds_json(target))['rect']
            original = copy.deepcopy(geometry(fig.get_settings()))
            scale = inputs.info()['chart_panel'][2]/960
            point = native_point(inputs.info(), (box[0]+box[2]/2, box[1]+box[3]/2))
            drag_native(inputs, point, (12*scale, 6*scale))
            moved = copy.deepcopy(geometry(fig.get_settings()))
            assert moved['from'] != original['from'] and moved['to'] != original['to']
            bounds = json.loads(fig._native.bounds_json(target))
            endpoint = max(bounds['handles'], key=lambda r:r[0]+r[1])
            point = native_point(inputs.info(), (endpoint[0]+endpoint[2]/2, endpoint[1]+endpoint[3]/2))
            drag_native(inputs, point, (10*scale, 0))
            resized = geometry(fig.get_settings())
            assert resized['from'] == moved['from'] and resized['to'] != moved['to']
            assert not inputs.info()['error']
        finally:
            handle.close();Inputs.pump()
    source = "import json\nimport figgyplot as figgy\nfig,ax=figgy.subplots(backend='webgpu')\n"+setup+"\ndisplay(fig.widget())"
    with notebook(tmp_path/kind, source) as (page, execute):
        def screen(point):
            if kind == 'radar':
                return browser_point(page, point)
            return page.evaluate("""p=>{const c=document.querySelector('.figgy-editor canvas'),r=c.getBoundingClientRect();return [r.x+p[0]*r.width/c.width,r.y+p[1]*r.height/c.height];}""", point)
        original = geometry(page.evaluate(ROOT+'.snapshot()'))
        annotation = page.evaluate(ROOT+'.annotations()')[0]
        box = annotation['rect']
        start = screen([box[0]+box[2]/2, box[1]+box[3]/2])
        page.mouse.move(*start);page.mouse.down();page.mouse.move(start[0]+12,start[1]+6,steps=5);page.mouse.up()
        page.evaluate(ROOT+'.flush()')
        moved = geometry(page.evaluate(ROOT+'.snapshot()'))
        assert moved['from'] != original['from'] and moved['to'] != original['to']
        if page.locator('.figgy-properties').is_visible():
            click_button(page, '[data-close-properties]')
        annotation = page.evaluate(ROOT+'.annotations()')[0]
        endpoint = max(annotation['handles'], key=lambda r:r[0]+r[1])
        start = screen([endpoint[0]+endpoint[2]/2, endpoint[1]+endpoint[3]/2])
        page.mouse.move(*start);page.mouse.down();page.mouse.move(start[0]+10,start[1],steps=5);page.mouse.up()
        page.evaluate(ROOT+'.flush()')
        resized = geometry(page.evaluate(ROOT+'.snapshot()'))
        assert resized['from'] == moved['from'] and resized['to'] != moved['to']
        assert not page.locator('.figgy-error').inner_text()


def choose_native_object(inputs, query, key):
    inputs.click('object_search')
    inputs.key('ctrl+a')
    inputs.xdo('type', '--clearmodifiers', query)
    inputs.pump()
    inputs.click('tree:'+key)


@pytest.mark.skipif(NEEDS_UI, reason='requires real native and Jupyter inputs')
@pytest.mark.parametrize('backend',['native','webgpu'])
def test_editor_undo_redo_groups_a_real_title_drag(tmp_path,backend):
    setup="ax=fig.axes[0];ax.plot([0,1,2],[1,3,2],id='signal');ax.set_title('Move this title')"
    if backend=='native':
        with figgy.Figure(backend=backend) as fig:
            exec(setup,{'fig':fig});handle=fig.show(block=False)
            try:
                inputs=Inputs(handle);before=fig.get_settings();count=fig.edit_history['undo_count'];uploads=fig.info['column_uploads']
                r=inputs.info()['decorations']['chart_title']
                drag_native(inputs,(r[0]+r[2]/2,r[1]+r[3]/2),(24,12))
                after=fig.get_settings()
                assert after['config']['chart_title']['offset_x']!=before['config']['chart_title']['offset_x']
                assert fig.edit_history['undo_count']==count+1
                inputs.click('undo');assert fig.get_settings()==before
                inputs.click('redo');assert fig.get_settings()==after
                assert fig.info['column_uploads']==uploads and not inputs.info()['error']
            finally:handle.close();Inputs.pump()
        return
    from inline_editor_harness import instrumented_source
    source='import json\nimport figgyplot as fg\nfig=fg.Figure(backend="webgpu")\n'+setup+'\n'+instrumented_source(tmp_path)
    with notebook(tmp_path/'history-drag',source) as (page,execute):
        before=page.evaluate(ROOT+'.testRendererState()')
        count=json.loads(execute('print(json.dumps(fig.edit_history))'))['undo_count']
        rect=page.evaluate(ROOT+'.decorations()')['chart_title']['rect'];canvas=page.locator('canvas').bounding_box()
        backing=page.locator('canvas').evaluate('c=>[c.width,c.height]')
        x=canvas['x']+(rect[0]+rect[2]/2)*canvas['width']/backing[0];y=canvas['y']+(rect[1]+rect[3]/2)*canvas['height']/backing[1]
        page.mouse.move(x,y);page.mouse.down();page.mouse.move(x+24,y+12,steps=4);page.mouse.up();page.evaluate(ROOT+'.flush()')
        after=page.evaluate(ROOT+'.testRendererState()')
        assert after['config']['chart_title']['offset_x']!=before['config']['chart_title']['offset_x']
        assert json.loads(execute('print(json.dumps(fig.edit_history))'))['undo_count']==count+1
        click_button(page, '[data-undo]');page.evaluate(ROOT+'.flush()')
        assert page.evaluate(ROOT+'.testRendererState()')==before
        click_button(page, '[data-redo]');page.evaluate(ROOT+'.flush()')
        assert page.evaluate(ROOT+'.testRendererState()')==after
        assert not page.locator('.figgy-error').inner_text()


@pytest.mark.skipif(NEEDS_UI, reason='requires real native and Jupyter inputs')
@pytest.mark.parametrize('backend',['native','webgpu'])
def test_shared_property_controls_apply_and_undo_without_losing_the_object(tmp_path,backend):
    setup="ax=fig.axes[0];ax.plot([0,1,2],[1,3,2],id='signal',label='Signal')"
    if backend=='native':
        with figgy.Figure(backend=backend) as fig:
            exec(setup,{'fig':fig});handle=fig.show(block=False)
            try:
                inputs=Inputs(handle);before=fig.get_settings();uploads=fig.info['column_uploads']
                inputs.click('properties');choose_native_object(inputs,'signal','series/signal')
                inputs.click('line_width');inputs.key('ctrl+a');inputs.xdo('type','--clearmodifiers','8');inputs.key('Return')
                assert fig.get_settings()['series'][0]['render_type']['Line']['line']['line_width']==8
                assert inputs.info()['selected']=='signal'
                inputs.click('undo');assert fig.get_settings()==before
                assert fig.info['column_uploads']==uploads and not inputs.info()['error']
            finally:handle.close();Inputs.pump()
        return
    from inline_editor_harness import instrumented_source
    source='import json\nimport figgyplot as fg\nfig=fg.Figure(backend="webgpu")\n'+setup+'\n'+instrumented_source(tmp_path)
    with notebook(tmp_path/'property-command',source) as (page,execute):
        before=page.evaluate(ROOT+'.testRendererState()');uploads=page.evaluate(ROOT+'.stats.column_uploads')
        click_button(page, '[data-properties]');ObjectNavigator(page).choose('signal')
        width=page.locator('[data-property=line_width]');width.fill('8');width.press('Tab');page.evaluate(ROOT+'.flush()')
        after=page.evaluate(ROOT+'.testRendererState()')
        assert after['series'][0]['render_type']['Line']['line']['line_width']==8
        assert ObjectNavigator(page).selected()=='signal'
        python_state=json.loads(execute('print(json.dumps(fig.get_settings()))'))
        assert python_state==after
        click_button(page, '[data-undo]');page.evaluate(ROOT+'.flush()')
        assert page.evaluate(ROOT+'.testRendererState()')==before
        assert page.evaluate(ROOT+'.stats.column_uploads')==uploads
        assert not page.locator('.figgy-error').inner_text()


@pytest.mark.skipif(NEEDS_UI, reason='requires real native and Jupyter inputs')
def test_object_tree_routes_secondary_axes_and_reveals_canvas_selection(tmp_path):
    setup = "fig.set_layout([['left','right']]); ax=fig.subplots['left'].axes; ax.plot([0,1,2],[1,2,1],label='Signal',id='signal'); ax.set_title('Overview'); right=fig.subplots['right'].axes; right.plot([0,1,2],[3,1,2],id='other'); right.set_title('Measurements'); twin=right.twinx(id='pressure_axis'); twin.plot([0,1,2],[100,200,150],label='Pressure readings',id='pressure'); ax.activate()"
    with figgy.Figure(backend='native') as fig:
        exec(setup, {'fig': fig})
        handle=fig.show(block=False)
        try:
            inputs=Inputs(handle);inputs.click('properties')
            root_title_rect=inputs.info()['decorations']['chart_title']
            choose_native_object(inputs, 'pressure', 'series/pressure')
            assert fig.get_settings()['config']['active_layer']=={'SubplotOverlay':[0,0]}
            assert inputs.info()['selected']=='pressure'
            assert 'object' not in inputs.info()['controls'] and 'active_layer' not in inputs.info()['controls']
            choose_native_object(inputs, 'chart_title', 'panel/right/chart_title')
            inputs.click('text');inputs.key('ctrl+a');inputs.xdo('type','--clearmodifiers','Edited measurements');inputs.pump()
            state=fig.get_settings()
            assert ''.join(s['text'] for s in state['config']['subplots'][0]['config']['chart_title']['text']['segments'])=='Edited measurements'
            assert ''.join(s['text'] for s in state['config']['chart_title']['text']['segments'])=='Overview'
            # Directly choosing a different panel on the canvas also reveals it.
            # The first click enters the panel; the second edits its title.
            inputs.click_rect(root_title_rect)
            assert inputs.info()['focused_panel']=='left'
            assert inputs.info()['selected'] is None
            inputs.click_rect(root_title_rect)
            assert fig.get_settings()['config'].get('active_layer','Base')=='Base'
            assert inputs.info()['selected']=='chart_title'
            assert 'tree:panel/left/chart_title' in inputs.info()['controls']
            from PIL import ImageGrab
            frame=dict(line.split('=',1) for line in inputs.xdo('getwindowgeometry','--shell',inputs.wid).splitlines())
            x,y,w,h=[int(frame[k]) for k in ('X','Y','WIDTH','HEIGHT')]
            ImageGrab.grab(bbox=(x,y,x+w,y+h),xdisplay=os.environ['DISPLAY']).save(tmp_path/'native-object-navigator.png')
            assert fig.info['rgba_readbacks']==fig.info['png_encodes']==0
        finally:
            handle.close();Inputs.pump()
    source="import json\nimport figgyplot as figgy\nfig=figgy.Figure(backend='webgpu')\n"+setup+"\ndisplay(fig.widget())"
    with notebook(tmp_path/'objects',source) as (page,execute):
        initial=page.locator('canvas').bounding_box()
        assert initial['width']<=960.5 and initial['height']/initial['width']==pytest.approx(600/960,abs=.002)
        click_button(page, '[data-properties]')
        assert page.locator('select[data-target], select[data-layer]').count()==0
        nav=ObjectNavigator(page);nav.choose('pressure')
        page.evaluate(ROOT+'.flush()')
        assert page.evaluate(ROOT+'.snapshot().config.active_layer')=={'SubplotOverlay':[0,0]}
        assert page.locator('[data-object="pressure"]').get_attribute('aria-selected')=='true'
        nav.choose('subplot_0:chart_title')
        title=page.locator('[data-property=text]');title.fill('Edited measurements');title.dispatch_event('change');page.evaluate(ROOT+'.flush()')
        execute('await fig.sync()')
        state=json.loads(execute('print(json.dumps(fig.get_settings()))'))
        assert ''.join(s['text'] for s in state['config']['subplots'][0]['config']['chart_title']['text']['segments'])=='Edited measurements'
        assert ''.join(s['text'] for s in state['config']['chart_title']['text']['segments'])=='Overview'
        # Keyboard tree navigation is independent of chart arrow-key dragging.
        search=page.locator('[data-object-search]');search.fill('Pressure readings');search.press('ArrowDown')
        page.keyboard.press('Enter');page.evaluate(ROOT+'.flush()')
        assert nav.selected()=='pressure'
        # Inspector is docked outside the canvas, including on smaller outputs.
        canvas=page.locator('canvas').bounding_box();inspector=page.locator('.figgy-properties').bounding_box()
        assert inspector['x']>=canvas['x']+canvas['width']
        assert page.evaluate(ROOT+'.stats.png_exports')==0
        page.locator('.figgy-editor').screenshot(path=str(tmp_path/'object-navigator.png'))


@pytest.mark.skipif(NEEDS_UI, reason='requires real native and Jupyter inputs')
@pytest.mark.parametrize('family', ['boxplot','boxplot_horizontal','radar'])
def test_bounded_value_range_wheel_and_fit_work_in_both_hosts(tmp_path, family):
    kind='boxplot' if family.startswith('boxplot') else 'radar'
    setup="ax.boxplot([[1,2,4],[2,5,9]],orientation=%r)"%('horizontal' if family.endswith('horizontal') else 'vertical') if kind=='boxplot' else "ax.radar(['A','B','C'],[2,4,3])"
    with figgy.Figure(backend='native') as fig:
        exec(setup, {'fig':fig,'ax':fig.axes[0]});handle=fig.show(block=False)
        try:
            inputs=Inputs(handle)
            before=fig.get_settings()[kind]
            rect=inputs.info()['decorations']['data_area'];point=native_point(inputs.info(),(rect[0]+rect[2]/2,rect[1]+rect[3]/2))
            inputs.xdo('mousemove','--window',inputs.wid,*map(round,point));inputs.pump();inputs.xdo('click',4);inputs.pump()
            after=fig.get_settings()[kind]
            assert after['value_range'] is None if kind=='radar' else after['value_range'] is not None
            assert after['series']==before['series']
            panel_before=inputs.info()['chart_panel']
            before_inspector=inputs.info()
            inputs.click('properties');assert 'range_min' in inputs.info()['controls']
            if inputs.info()['chart_panel']!=panel_before:
                from PIL import ImageGrab
                (tmp_path/'inspector-layout.json').write_text(json.dumps(dict(before=before_inspector,after=inputs.info()),indent=2))
                ImageGrab.grab(xdisplay=os.environ['DISPLAY']).save(tmp_path/'inspector-layout.png')
            assert inputs.info()['chart_panel']==panel_before
            inputs.click('fit');assert fig.get_settings()[kind]['value_range'] is None
            assert fig.info['rgba_readbacks']==fig.info['png_encodes']==0
        finally:handle.close();Inputs.pump()
    source="import json\nimport figgyplot as figgy\nfig,ax=figgy.subplots(backend='webgpu')\n"+setup+"\ndisplay(fig.widget())"
    with notebook(tmp_path/family,source) as (page,execute):
        original=page.evaluate(ROOT+'.snapshot()')[kind]
        area=page.evaluate('async()=> (await '+ROOT+'.decorations()).find(v=>v.id==="data_area").rect')
        page.mouse.move(*browser_point(page,(area[0]+area[2]/2,area[1]+area[3]/2)));page.mouse.wheel(0,-40)
        if kind!='radar':page.wait_for_function(ROOT+f'.snapshot().{kind}.value_range !== null')
        else:assert page.evaluate(ROOT+f'.snapshot().{kind}.value_range') is None
        page.evaluate(ROOT+'.flush()')
        state=page.evaluate(ROOT+'.snapshot()')[kind]
        assert state['series']==original['series']
        click_button(page, '[data-properties]');minimum=page.locator('[data-property=range_min]');assert minimum.is_visible()
        click_button(page, '[data-fit]');page.evaluate(ROOT+'.flush()')
        assert page.evaluate(ROOT+f'.snapshot().{kind}.value_range') is None
        assert not page.locator('.figgy-error').inner_text()


@pytest.mark.skipif(NEEDS_UI, reason='requires real native and Jupyter inputs')
@pytest.mark.parametrize('family', ['cartesian', 'log_inverted', 'boxplot', 'boxplot_horizontal', 'categorical', 'radial', 'radar', 'polar'])
def test_annotation_drawing_editing_and_cancel_in_both_hosts(tmp_path, family):
    """Real gestures create one SSOT edit, never a document per preview frame."""
    setup = {
        'cartesian': "ax.plot([0,1,2],[1,3,2]);ax.set_xlim(0,2);ax.set_ylim(0,4)",
        'log_inverted': "ax.plot([1,10,100],[1,10,100]);ax.set_xlim(1,100);ax.set_ylim(1,100);ax.set_xscale('log');fig.configure(config={k:{'inverted':True} for k in ['bottom_x','top_x']})",
        'boxplot': "ax.boxplot([[1,2,4],[2,5,9]])",
        'boxplot_horizontal': "ax.boxplot([[1,2,4],[2,5,9]],orientation='horizontal')",
        'categorical': "ax.bar(['A','B','C'],[2,4,3])",
        'radial': "ax.donut([2,3,4])",
        'radar': "ax.radar(['A','B','C'],[2,4,3])",
        'polar': "ax.set_polar();ax.plot([0,1,2],[1,2,1])",
    }[family]
    kind = 'boxplot' if family.startswith('boxplot') else family if family in {'categorical','radial','radar'} else None
    horizontal = family == 'boxplot_horizontal'
    axes = [horizontal, not horizontal] if kind in {'boxplot','categorical'} else [False,False] if family in {'radial','radar','polar'} else [True,True]
    tools = ['arrow'] + (['vline','vspan'] if axes[0] else []) + (['hline','hspan'] if axes[1] else [])
    def owner(state): return state[kind] if kind else state['config']
    def items(state): return owner(state).get('annotations',{}).get('items',[])
    with figgy.Figure(backend='native') as fig:
        exec(setup, {'fig':fig,'ax':fig.axes[0]});handle=fig.show(block=False)
        inputs=None;samples=[]
        def drawing_probe(stage):
            samples.append({'stage':stage,'settings':fig.get_settings(),'host':inputs.info()})
            (tmp_path/'native-drawing-states.json').write_text(json.dumps(samples))
            (tmp_path/'native-drawing-inputs.json').write_text(json.dumps(inputs.events))
        try:
            inputs=Inputs(handle);inputs.click('draw');revision=fig.revision
            inputs.click('layout_mode');inputs.click('draw_arrow')
            assert not inputs.info()['layout_mode'] and inputs.info()['drawing_tool']=='arrow'
            if family=='radial':
                # Switching between plot windows must retain the armed tool.
                with figgy.Figure(backend='native') as other:
                    other.axes[0].plot([0,1],[0,1]);other_handle=other.show(block=False)
                    try:
                        Inputs(other_handle)
                        assert inputs.info()['drawing_tool']=='arrow'
                    finally:other_handle.close();Inputs.pump()
                inputs.xdo('windowraise',inputs.wid);inputs.xdo('windowfocus',inputs.wid);inputs.pump()
            start=native_point(inputs.info(),(330,240));end=native_point(inputs.info(),(490,340))
            inputs.xdo('mousemove','--window',inputs.wid,*map(round,start));inputs.pump();inputs.xdo('mousedown',1);inputs.pump()
            inputs.xdo('mousemove','--window',inputs.wid,*map(round,end));inputs.pump()
            assert fig.revision==revision and not items(fig.get_settings())
            inputs.key('Escape');inputs.xdo('mouseup',1);inputs.pump()
            assert not items(fig.get_settings())
            # The existing bounded hover route may resume after cancellation.
            if kind is None:assert fig.revision==revision
            inputs.click('draw_text');revision=fig.revision;point=native_point(inputs.info(),(330,240))
            drawing_probe('text-armed')
            inputs.click_rect([point[0]-1,point[1]-1,2,2])
            drawing_probe('text-placed')
            assert 'inline_text' in inputs.info()['controls'] and not items(fig.get_settings())
            inputs.xdo('type','--clearmodifiers','Discard this');inputs.pump();inputs.key('Escape')
            assert not items(fig.get_settings())
            if kind is None: assert fig.revision==revision
            inputs.click('draw_text');inputs.click_rect([point[0]-1,point[1]-1,2,2])
            draft_revision=fig.revision
            inputs.xdo('type','--clearmodifiers','Review this region');inputs.pump()
            assert not items(fig.get_settings()) and fig.revision==draft_revision
            assert not inputs.info()['properties_open']
            inputs.key('Return');assert len(items(fig.get_settings()))==1
            assert ''.join(v['text'] for v in items(fig.get_settings())[0]['kind']['Text']['text']['segments'])=='Review this region'
            # Editing is a second transaction; Escape retains both content and revision.
            revision=fig.revision
            def edit_native_text():
                inputs.xdo('mousemove','--window',inputs.wid,round(point[0]+20),round(point[1]+8));inputs.pump()
                inputs.xdo('click','--repeat',2,'--delay',100,1);inputs.pump()
                assert 'inline_text' in inputs.info()['controls'], inputs.info()
            edit_native_text();inputs.xdo('type','--clearmodifiers','Cancelled replacement');inputs.pump();inputs.key('Escape')
            if kind is None: assert fig.revision==revision
            assert ''.join(v['text'] for v in items(fig.get_settings())[0]['kind']['Text']['text']['segments'])=='Review this region'
            edit_native_text();inputs.key('End');inputs.xdo('type','--clearmodifiers',' again');inputs.pump();inputs.key('Return')
            assert ''.join(v['text'] for v in items(fig.get_settings())[0]['kind']['Text']['text']['segments'])=='Review this region again'
            assert not inputs.info()['properties_open']
            if any(axes):
                revision=fig.revision;inputs.click('draw_data_anchor');assert fig.revision==revision
            for tool in tools:
                inputs.click('draw_'+tool)
                assert inputs.info()['drawing_tool']==tool, inputs.info()
                start=native_point(inputs.info(),(340,260));end=native_point(inputs.info(),(510,360))
                count=len(items(fig.get_settings()));drag_native(inputs,start,(end[0]-start[0],end[1]-start[1]))
                assert len(items(fig.get_settings()))==count+1, inputs.info()
                if tool=='arrow':
                    assert ('Data' if any(axes) else 'Ratio') in items(fig.get_settings())[-1]['kind']['Arrow']['from']
                    assert 'head_length' in inputs.info()['controls']
            saved=fig.get_settings();ids=[i['id'] for i in items(saved)];assert len(ids)==len(set(ids))
            assert owner(saved)['active_layer']=='Annotations'
            inputs.click('delete_annotation');assert len(items(fig.get_settings()))==len(ids)-1
            assert not inputs.info()['error']
            assert fig.info['rgba_readbacks']==fig.info['png_encodes']==0
        finally:
            if inputs is not None:drawing_probe('closing')
            handle.close();Inputs.pump()
    source="import json\nimport figgyplot as figgy\nfig,ax=figgy.subplots(backend='webgpu')\n"+setup+"\ndisplay(fig.widget())"
    with notebook(tmp_path/family,source) as (page,execute):
        click_button(page, '[data-draw]')
        for name,allowed in [('vline',axes[0]),('vspan',axes[0]),('hline',axes[1]),('hspan',axes[1])]:
            assert page.locator(f'[data-tool={name}]').is_enabled()==allowed
        click_button(page, '[data-layout]');click_button(page, '[data-tool=arrow]')
        assert page.locator('[data-layout]').get_attribute('aria-pressed')=='false'
        assert page.locator('[data-select]').get_attribute('aria-pressed')=='false'
        if family=='radial':
            other=page.context.new_page()
            try:other.bring_to_front()
            finally:other.close();page.bring_to_front()
            assert page.locator('[data-tool=arrow]').get_attribute('aria-pressed')=='true'
        r=page.locator('canvas').bounding_box()
        page.mouse.move(r['x']+r['width']*.35,r['y']+r['height']*.4);page.mouse.down();page.mouse.move(r['x']+r['width']*.55,r['y']+r['height']*.6)
        page.wait_for_function("document.querySelector('.figgy-drawing-preview').childElementCount>0")
        assert not items(page.evaluate(ROOT+'.snapshot()'))
        page.keyboard.press('Escape');page.mouse.up();assert not items(page.evaluate(ROOT+'.snapshot()'))
        def place_browser_text():
            click_button(page, '[data-tool=text]');r=page.locator('canvas').bounding_box()
            page.mouse.click(r['x']+r['width']*.35,r['y']+r['height']*.4)
            page.locator('[data-inline-text]').wait_for(state='visible')
            page.wait_for_function("document.activeElement?.hasAttribute('data-inline-text')")
        place_browser_text();entry=page.locator('[data-inline-text]');entry.fill('Discard this');entry.press('Escape')
        assert not items(page.evaluate(ROOT+'.snapshot()'))
        place_browser_text();entry.fill('Review this region')
        assert not items(page.evaluate(ROOT+'.snapshot()'))
        assert not page.locator('.figgy-properties').is_visible()
        screenshot_editor(page,tmp_path/f'{family}-inline-text.png')
        entry.press('Enter');page.evaluate(ROOT+'.flush()')
        assert not page.locator('.figgy-error').inner_text()
        assert ''.join(v['text'] for v in items(page.evaluate(ROOT+'.snapshot()'))[0]['kind']['Text']['text']['segments'])=='Review this region'
        def edit_browser_text():
            page.wait_for_function('async()=> (await '+ROOT+'.annotations()).length===1')
            rect=page.evaluate(ROOT+'.annotations()')[0]['rect'];page.mouse.dblclick(*browser_point(page,(rect[0]+20,rect[1]+8)))
            entry.wait_for(state='visible');page.wait_for_function("document.activeElement?.hasAttribute('data-inline-text')")
        edit_browser_text();entry.fill('Cancelled replacement');entry.press('Escape');page.evaluate(ROOT+'.flush()')
        assert ''.join(v['text'] for v in items(page.evaluate(ROOT+'.snapshot()'))[0]['kind']['Text']['text']['segments'])=='Review this region'
        edit_browser_text();entry.press('End');entry.press('ArrowRight');entry.type(' again');entry.press('Enter');page.evaluate(ROOT+'.flush()')
        assert ''.join(v['text'] for v in items(page.evaluate(ROOT+'.snapshot()'))[0]['kind']['Text']['text']['segments'])=='Review this region again'
        assert not page.locator('.figgy-properties').is_visible()
        if any(axes):page.locator('[data-anchor-data]').check()
        for tool in tools:
            click_button(page, f'[data-tool={tool}]');r=page.locator('canvas').bounding_box();count=len(items(page.evaluate(ROOT+'.snapshot()')))
            page.mouse.move(r['x']+r['width']*.36,r['y']+r['height']*.44);page.mouse.down();page.mouse.move(r['x']+r['width']*.55,r['y']+r['height']*.6,steps=4);page.mouse.up()
            page.wait_for_function(ROOT+f'.snapshot().{kind or "config"}.annotations.items.length==={count+1}')
            page.evaluate(ROOT+'.flush()')
            assert not page.locator('.figgy-error').inner_text()
            if tool=='arrow':
                assert ('Data' if any(axes) else 'Ratio') in items(page.evaluate(ROOT+'.snapshot()'))[-1]['kind']['Arrow']['from']
                field=page.locator('[data-property=head_length]');field.fill('14');field.dispatch_event('change');page.evaluate(ROOT+'.flush()')
                page.locator('[data-property=line_style]').select_option('Dash');page.evaluate(ROOT+'.flush()')
                assert items(page.evaluate(ROOT+'.snapshot()'))[-1]['kind']['Arrow']['style']['head_length']==14
        execute('await fig.sync()');state=json.loads(execute('print(json.dumps(fig.get_settings()))'))
        assert items(state)==items(page.evaluate(ROOT+'.snapshot()'))
        count=len(items(state));page.locator('[data-delete-annotation]').click();page.evaluate(ROOT+'.flush()')
        assert len(items(page.evaluate(ROOT+'.snapshot()')))==count-1
        assert page.evaluate(ROOT+'.stats.png_exports')==0
        screenshot_editor(page,tmp_path/f'{family}-drawing.png')


@pytest.mark.skipif(NEEDS_UI, reason='requires a real browser')
def test_surface_readiness_rejects_matching_pre_resize_css_and_backing(tmp_path):
    from playwright.sync_api import sync_playwright
    from inline_editor_harness import SURFACE_READY,wait_surface
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=os.environ.get('BROWSER_EXECUTABLE_PATH') or shutil.which('chromium'),
                                  headless=False,args=['--no-sandbox'])
        try:
            page=browser.new_page(viewport={'width':980,'height':820})
            page.set_content('''<style>body{margin:0}canvas{position:absolute;left:389px;top:361.9375px;width:960px;height:600px}</style>
                <div class="figgy-editor"><canvas width="960" height="600"></canvas></div>''')
            old=page.evaluate("""()=>{const c=document.querySelector('canvas'),r=c.getBoundingClientRect();
                return {viewport:[innerWidth,innerHeight],canvas:[r.x,r.y,r.width,r.height],backing:[c.width,c.height]};}""")
            assert not page.evaluate(SURFACE_READY,[980,820,1]),old
            page.evaluate("""()=>{window.layoutDelivered=false;setTimeout(()=>{
                const c=document.querySelector('canvas');c.style.width='511px';c.style.height='319.375px';
                c.width=511;c.height=319;window.layoutDelivered=true;
            },200);}""")
            wait_surface(page,(980,820))
            assert page.evaluate('layoutDelivered')
            (tmp_path/'surface-readiness.json').write_text(json.dumps({'before':old,'after':page.locator('canvas').evaluate('c=>[c.width,c.height,c.getBoundingClientRect().width]')}))
        finally:browser.close()


@pytest.mark.skipif(NEEDS_UI, reason='requires a real browser')
def test_annotation_mouse_input_uses_live_layout_after_resize(tmp_path):
    from playwright.sync_api import sync_playwright
    from inline_editor_harness import annotation_point
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=os.environ.get('BROWSER_EXECUTABLE_PATH') or shutil.which('chromium'),
                                  headless=False,args=['--no-sandbox'])
        try:
            page=browser.new_page(viewport={'width':980,'height':820})
            page.set_content('''<style>body{margin:0}canvas{position:absolute;left:389px;top:361.9375px;width:960px;height:600px}</style>
                <div class="figgy-editor"><canvas width="960" height="600"></canvas></div>''')
            page.evaluate("""()=>{
                const root=document.querySelector('.figgy-editor'),canvas=root.querySelector('canvas');
                root.figgy={annotations:async()=>[{index:0,rect:[846,506,62,38]}],
                    snapshot:()=>({config:{chart_area:{width:960,height:600}}}),diagnostics:()=>({kind:'radial'})};
                window.clicks=[];canvas.addEventListener('dblclick',e=>clicks.push({trusted:e.isTrusted,x:e.clientX,y:e.clientY}));
            }""")
            old=page.locator('canvas').bounding_box()
            stale=[old['x']+854*old['width']/960,old['y']+512*old['height']/600]
            page.evaluate("""()=>{const c=document.querySelector('canvas');c.style.width='511px';
                c.style.height='319.375px';c.style.top='438.9375px';}""")
            page.mouse.dblclick(*stale)
            assert page.evaluate('clicks')==[]  # The CI point lies outside the viewport.
            current=annotation_point(page);page.mouse.dblclick(*current['point'])
            clicks=page.evaluate('clicks');assert len(clicks)==1 and clicks[0]['trusted']
            (tmp_path/'annotation-input-layout.json').write_text(json.dumps({'stale_point':stale,'current':current,'delivered':clicks}))
        finally:browser.close()


@pytest.mark.skipif(NEEDS_UI, reason='requires real native and Jupyter inputs')
@pytest.mark.parametrize('family', ['cartesian', 'radial'])
def test_inline_text_resize_multiline_and_existing_format_in_both_hosts(tmp_path, family):
    """Drafts survive resizing; editing an ordinary Python-owned layer needs no tree."""
    setup = "ax.plot([0,1,2],[1,3,2])" if family == 'cartesian' else "ax.donut([2,3,4])"
    kind = 'radial' if family == 'radial' else 'config'
    def annotation(state): return state[kind]['annotations']['items'][0]
    def content(state): return ''.join(v['text'] for v in annotation(state)['kind']['Text']['text']['segments'])
    with figgy.Figure(backend='native') as fig:
        exec(setup, {'fig':fig,'ax':fig.axes[0]});handle=fig.show(block=False)
        try:
            inputs=Inputs(handle);inputs.click('draw');inputs.click('draw_text')
            point=native_point(inputs.info(),(850,510));inputs.click_rect([point[0]-1,point[1]-1,2,2])
            inputs.xdo('type','--clearmodifiers','First');inputs.pump();inputs.key('shift+Return')
            inputs.xdo('type','--clearmodifiers','Second');inputs.pump()
            inputs.xdo('windowsize',inputs.wid,780,590);inputs.pump()
            assert 'inline_text' in inputs.info()['controls']
            rect=inputs.info()['controls']['inline_text'];width,height=inputs.info()['surface_size']
            assert rect[0]>=0 and rect[1]>=0 and rect[0]+rect[2]<=width+1 and rect[1]+rect[3]<=height+1
            inputs.key('Return');assert content(fig.get_settings())=='First\nSecond'
            state=fig.get_settings();state[kind]['active_layer']='Base'
            annotation(state)['kind']['Text']['text']['segments'][0]['bold']=True
            fig.apply_settings(state);inputs.pump()
            # Direct hit routing must reveal text even when its annotation layer is inactive.
            point=native_point(inputs.info(),(850,510))
            inputs.xdo('mousemove','--window',inputs.wid,round(point[0]+8),round(point[1]+6));inputs.pump()
            inputs.xdo('click','--repeat',2,'--delay',100,1);inputs.pump()
            assert 'inline_text' in inputs.info()['controls'],inputs.info()
            inputs.key('ctrl+End');inputs.xdo('type','--clearmodifiers','!');inputs.pump()
            # Clicking outside applies the pending text once, without starting a canvas drag.
            inputs.click('draw')
            assert content(fig.get_settings())=='First\nSecond!'
            assert annotation(fig.get_settings())['kind']['Text']['text']['segments'][0]['bold']
            assert not inputs.info()['error']
        finally:handle.close();Inputs.pump()
    source="import json\nimport figgyplot as figgy\nfig,ax=figgy.subplots(backend='webgpu')\n"+setup+"\ndisplay(fig.widget())"
    with notebook(tmp_path/family,source) as (page,execute):
        click_button(page, '[data-draw]');click_button(page, '[data-tool=text]')
        page.mouse.click(*browser_point(page,(850,510)));entry=page.locator('[data-inline-text]');entry.wait_for(state='visible')
        entry.fill('First');entry.press('Shift+Enter');entry.type('Second')
        from layout_probe import arm_browser
        from inline_editor_harness import OBSERVE, wait_surface, assert_contained
        arm_browser(page)
        page.set_viewport_size({'width':980,'height':820})
        wait_surface(page,(980,820))
        state=page.evaluate(OBSERVE)
        (tmp_path/'inline-editor-resize.json').write_text(json.dumps(state,indent=2))
        assert state['focused'] and state['value']=='First\nSecond'
        assert_contained(state)
        # Enter used by an IME must not confirm or discard its current composition.
        entry.dispatch_event('keydown',{'key':'Enter','code':'Enter','isComposing':True})
        assert entry.is_visible()
        entry.press('Enter');page.evaluate(ROOT+'.flush()')
        assert not page.locator('.figgy-error').inner_text()
        assert content(page.evaluate(ROOT+'.snapshot()'))=='First\nSecond'
        execute("state=fig.get_settings();state['"+kind+"']['active_layer']='Base';state['"+kind+"']['annotations']['items'][0]['kind']['Text']['text']['segments'][0]['bold']=True;fig.apply_settings(state);print('updated')")
        page.wait_for_function(f'({ROOT}.snapshot().{kind}.active_layer??"Base")==="Base" && {ROOT}.snapshot().{kind}.annotations.items[0].kind.Text.text.segments[0].bold===true')
        page.wait_for_function('async()=> (await '+ROOT+'.annotations()).length===1')
        from inline_editor_harness import annotation_point
        reopen=annotation_point(page)
        (tmp_path/'inline-reopen-request.json').write_text(json.dumps(reopen,indent=2))
        page.mouse.dblclick(*reopen['point'])
        try:
            entry.wait_for(state='visible');page.wait_for_function("document.activeElement?.hasAttribute('data-inline-text')")
        finally:
            reopen.update(observed=page.evaluate(OBSERVE),hit=page.evaluate(ROOT+'.stats.last_annotation_hit'),annotations=page.evaluate(ROOT+'.annotations()'))
            (tmp_path/'inline-reopen-result.json').write_text(json.dumps(reopen,indent=2))
            print('FIGGY INLINE REOPEN '+json.dumps(reopen))
        entry.press('Control+End');entry.type('!');click_button(page, '[data-draw]');page.evaluate(ROOT+'.flush()')
        assert content(page.evaluate(ROOT+'.snapshot()'))=='First\nSecond!'
        assert annotation(page.evaluate(ROOT+'.snapshot()'))['kind']['Text']['text']['segments'][0]['bold']
        assert not page.locator('.figgy-error').inner_text()


@pytest.mark.skipif(NEEDS_UI, reason='requires a real Jupyter WebGPU widget')
@pytest.mark.parametrize('dpr',[1,2])
def test_inline_editor_resize_uses_current_units_and_applies_real_edits(tmp_path,dpr):
    """Exercise queued resizes, actual draft edits, application and cancellation.

    Automatic chart layout may retain history. This checks the inline editor's
    document-unit font at document width, not whole-chart round-trip equality.
    """
    from inline_editor_harness import ROOT as host, instrumented_source, OBSERVE, wait_surface, observe, assert_contained, open_existing
    source="""import json
import figgyplot as fg
fig,ax=fg.subplots(backend='webgpu')
ax.plot([0,1,2],[1,3,2],id='signal')
ax.text(.95,.95,'Probe',coords='ratio',fontsize=16*72/fig.dpi,id='probe')
"""+instrumented_source(tmp_path)
    with notebook(tmp_path/'inline-resize-contract',source) as (page,execute):
        entry=open_existing(page)
        entry.fill('First\nSecond')
        before=observe(page,tmp_path,'before-resize')
        original=before['renderer']['config']['annotations']['items'][0]
        page.set_viewport_size({'width':640,'height':600})
        # Jupyter resizes its content asynchronously. Equality with the old CSS
        # size is not evidence that the requested shrink has happened yet.
        page.wait_for_function("initial=>document.querySelector('.figgy-editor canvas').width<initial",arg=before['backing'][0],polling=20)
        wait_surface(page,(640,600))
        (tmp_path/'before-queue-hold.json').write_text(json.dumps(page.evaluate(OBSERVE),indent=2))
        # Hold the existing host queue so CSS layout necessarily changes before
        # the GPU backing resize. This is a legal scheduling order, not a repair.
        page.evaluate(host+'.testHoldQueue()')
        previous_width=page.locator('canvas').evaluate('c=>c.width')
        try:
            page.set_viewport_size({'width':1500,'height':1000})
            page.wait_for_function("document.querySelector('.figgy-editor canvas').getBoundingClientRect().width===960",polling=20)
            page.wait_for_function(host+'.diagnostics().queued>0',polling=20)
            page.wait_for_function("previous=>window.__figgyInlinePass?.cssWidth===960&&window.__figgyInlinePass?.backingWidth===previous",arg=previous_width,polling=20)
            pending=page.evaluate(OBSERVE)
            (tmp_path/'queued-resize.json').write_text(json.dumps(pending,indent=2))
            assert pending['font']==16,pending
        finally:
            page.evaluate(host+'.testReleaseQueue()')
        wait_surface(page,(1500,1000))
        after=observe(page,tmp_path,'after-resize')
        assert after['renderer']['config']['annotations']['items'][0]==original
        assert after['font']==16 and after['focused'] and after['value']=='First\nSecond'
        assert_contained(after)
        # Changing DPR alone must update backing pixels without changing the
        # authored font or the CSS-space font at the requested document width.
        session=page.context.new_cdp_session(page)
        session.send('Emulation.setDeviceMetricsOverride',dict(width=1500,height=1000,deviceScaleFactor=dpr,mobile=False))
        wait_surface(page,(1500,1000),dpr)
        for text in ('First\nSecond','\n'.join('Line '+str(n) for n in range(8)),'Pressure 10⁻⁶ Torr / μm °C '*8):
            entry.fill(text)
            for width,height in ((980,820),(640,600),(1500,1000)):
                session.send('Emulation.setDeviceMetricsOverride',dict(width=width,height=height,deviceScaleFactor=dpr,mobile=False))
                wait_surface(page,(width,height),dpr)
                state=observe(page,tmp_path,f'layout-{len(text)}-{width}')
                assert state['renderer']['config']['annotations']['items'][0]==original
                assert state['value']==text and state['focused']
                assert_contained(state)
                if width==1500:assert state['font']==16,state
        # Actual pointer/keyboard actions must produce the intended accepted
        # document, independently of whether a screenshot can be captured.
        entry.fill('First\nSecond');entry.click();entry.press('Control+End');entry.type('!');entry.press('Enter')
        page.evaluate(host+'.flush()')
        applied=observe(page,tmp_path,'after-apply')
        item=applied['renderer']['config']['annotations']['items'][0]
        assert ''.join(s['text'] for s in item['kind']['Text']['text']['segments'])=='First\nSecond!'
        assert item['kind']['Text']['text']['font_size']==16
        python_state=json.loads(execute('print(json.dumps(fig.get_settings()))'))
        assert python_state==applied['renderer']
        entry=open_existing(page);entry.press('Control+End');entry.type(' discard');entry.press('Escape')
        page.evaluate(host+'.flush()')
        cancelled=observe(page,tmp_path,'after-cancel')
        assert cancelled['renderer']['config']['annotations']['items'][0]==item
        assert not entry.is_visible()


@pytest.mark.skipif(NEEDS_UI, reason='requires real native and Jupyter inputs')
@pytest.mark.parametrize('backend', ['native', 'webgpu'])
def test_grid_focus_routes_visible_axes_and_data_without_tree(tmp_path, backend):
    """A chart click enters it without editing; visible data choose their owner."""
    setup = """
fig.set_layout([['overview','measurements'],['residuals','spectrum']], gap=16)
ax=fig.subplots['overview'].axes
ax.plot([0,1,2],[1,3,2],id='overview_line')
ax.set_title('Overview')
right=fig.subplots['measurements'].axes
right.plot([2,5,8],[2,8,4],id='signal',label='Signal')
right.set_title('Measurements')
twin=right.twinx(id='pressure_axis')
twin.plot([2,5,8],[850,600,250],id='pressure',label='Pressure',color='red')
fig.subplots['residuals'].axes.plot([0,1,2],[-.1,.2,-.1],id='residual')
fig.subplots['residuals'].axes.set_title('Residuals')
fig.subplots['spectrum'].axes.plot([0,1,2],[1,4,2],id='spectrum')
fig.subplots['spectrum'].axes.set_title('Spectrum')
right.set_xlim(0,10);right.set_ylim(0,10);twin.set_ylim(0,1000)
ax.activate()
"""
    def data_point(rect, x, y):
        # Renderer selection bounds include a two-pixel selection padding.
        a,b,w,h=rect
        return a+2+(w-4)*x,b+2+(h-4)*(1-y)
    if backend=='native':
        with figgy.Figure(backend=backend) as fig:
            exec(setup, {'fig':fig})
            before=fig.get_settings();handle=fig.show(block=False)
            try:
                inputs=Inputs(handle);uploads=fig.info['column_uploads']
                assert inputs.info()['focused_panel'] is None
                r=before['config']['subplots'][0]['config']['chart_area']
                center=native_point(inputs.info(),(r['x']+r['width']/2,r['y']+r['height']/2))
                drag_native(inputs,center,(12,8))
                assert inputs.info()['focused_panel']=='measurements'
                assert inputs.info()['selected'] is None and not inputs.info()['properties_open']
                state=fig.get_settings()
                assert state['config']['subplots']==before['config']['subplots']
                area=inputs.info()['decorations']['subplot_0:data_area']
                pressure=data_point(area,.5,.6)
                inputs.click_rect([*pressure,0,0])
                assert inputs.info()['selected']=='pressure'
                from PIL import ImageGrab
                window=dict(line.split('=',1) for line in inputs.xdo('getwindowgeometry','--shell',inputs.wid).splitlines())
                sx,sy,sw,sh=[int(window[k]) for k in ('X','Y','WIDTH','HEIGHT')]
                ImageGrab.grab(bbox=(sx,sy-20,sx+sw,sy+sh-20),xdisplay=os.environ['DISPLAY']).save(tmp_path/'native-grid-direct-selection.png')
                assert fig.get_settings()['config']['active_layer']=={'SubplotOverlay':[0,0]}
                # A click on the primary line switches back automatically.
                inputs.click_rect([*data_point(area,.5,.8),0,0])
                assert inputs.info()['selected']=='signal'
                assert fig.get_settings()['config']['active_layer']=={'Subplot':0}
                # The right-hand axis belongs to the visible secondary scale.
                inputs.click_rect([area[0]+area[2]-2,area[1]+area[3]*.37,0,0])
                if inputs.info()['choice_candidates']:
                    inputs.click('choose:element/subplot_0:overlay_0:axis_right')
                assert inputs.info()['selected']=='subplot_0:overlay_0:axis_right'
                assert fig.get_settings()['config']['active_layer']=={'SubplotOverlay':[0,0]}
                old=fig.get_settings()
                inputs.xdo('mousemove','--window',inputs.wid,*map(round,data_point(area,.4,.5)));inputs.pump()
                inputs.xdo('keydown','Shift_L');inputs.xdo('click',4);inputs.xdo('keyup','Shift_L');inputs.pump()
                changed=fig.get_settings()
                assert changed['config']['subplots'][0]['config']['overlays'][0]['y_axis']['max']!=old['config']['subplots'][0]['config']['overlays'][0]['y_axis']['max']
                assert changed['config']['subplots'][0]['config']['left_y']==old['config']['subplots'][0]['config']['left_y']
                assert changed['config']['left_y']==old['config']['left_y']
                inputs.key('Escape')
                assert inputs.info()['focused_panel'] is None and inputs.info()['selected'] is None
                # Wheel is inert until the user enters a chart again.
                old=fig.get_settings();inputs.xdo('click',4);inputs.pump()
                assert fig.get_settings()['config']==old['config']
                inputs.click_rect([*native_point(inputs.info(),(100,100)),0,0])
                assert inputs.info()['focused_panel']=='overview'
                # The grid gutter clears focus instead of editing a neighbor.
                inputs.click_rect([*native_point(inputs.info(),(480,150)),0,0])
                assert inputs.info()['focused_panel'] is None
                assert fig.info['column_uploads']==uploads
                assert fig.info['rgba_readbacks']==fig.info['png_encodes']==0
                assert not inputs.info()['error']
            finally:handle.close();Inputs.pump()
        return
    source="import json\nimport figgyplot as figgy\nfig=figgy.Figure(backend='webgpu')\n"+setup+"\ndisplay(fig.widget())"
    with notebook(tmp_path/'grid-focus',source) as (page,execute):
        def click(point):
            # Cartesian decoration geometry uses current physical canvas pixels.
            screen=page.evaluate("""p=>{const c=document.querySelector('.figgy-editor canvas'),r=c.getBoundingClientRect();return [r.x+p[0]*r.width/c.width,r.y+p[1]*r.height/c.height];}""",point)
            page.mouse.click(*screen);page.evaluate(ROOT+'.flush()')
        assert page.evaluate(ROOT+'.stats.focused_panel') is None
        before=page.evaluate(ROOT+'.snapshot()');uploads=page.evaluate(ROOT+'.stats.column_uploads')
        page.mouse.click(*browser_point(page,(720,150)));page.evaluate(ROOT+'.flush()')
        assert page.evaluate(ROOT+'.stats.focused_panel')=='measurements'
        assert page.locator('.figgy-properties').is_hidden()
        assert page.evaluate(ROOT+'.snapshot().config.subplots')==before['config']['subplots']
        area=page.evaluate(ROOT+'.decorations()')['subplot_0:data_area']['rect']
        click(data_point(area,.5,.6))
        assert page.evaluate(ROOT+'.snapshot().config.active_layer')=={'SubplotOverlay':[0,0]}
        assert ObjectNavigator(page).selected()=='pressure'
        page.locator('.figgy-editor').screenshot(path=str(tmp_path/'browser-grid-direct-selection.png'))
        area=page.evaluate(ROOT+'.decorations()')['subplot_0:data_area']['rect']
        click(data_point(area,.5,.8))
        assert ObjectNavigator(page).selected()=='signal', (area,page.evaluate(ROOT+'.stats'),page.evaluate(ROOT+'.snapshot().config.active_layer'))
        assert page.evaluate(ROOT+'.snapshot().config.active_layer')=={'Subplot':0}
        click([area[0]+area[2]-2,area[1]+area[3]*.37])
        if page.locator('.figgy-target-chooser').is_visible():
            page.locator('[data-choice="element/subplot_0:overlay_0:axis_right"]').click();page.evaluate(ROOT+'.flush()')
        assert ObjectNavigator(page).selected()=='subplot_0:overlay_0:axis_right'
        old=page.evaluate(ROOT+'.snapshot()')
        point=page.evaluate("""p=>{const c=document.querySelector('.figgy-editor canvas'),r=c.getBoundingClientRect();return [r.x+p[0]*r.width/c.width,r.y+p[1]*r.height/c.height];}""",data_point(area,.4,.5))
        page.mouse.move(*point);page.keyboard.down('Shift');page.mouse.wheel(0,-40);page.keyboard.up('Shift');page.evaluate(ROOT+'.flush()')
        changed=page.evaluate(ROOT+'.snapshot()')
        assert changed['config']['subplots'][0]['config']['overlays'][0]['y_axis']['max']!=old['config']['subplots'][0]['config']['overlays'][0]['y_axis']['max']
        assert changed['config']['subplots'][0]['config']['left_y']==old['config']['subplots'][0]['config']['left_y']
        assert changed['config']['left_y']==old['config']['left_y']
        page.locator('canvas').press('Escape');page.evaluate(ROOT+'.flush()')
        assert page.evaluate(ROOT+'.stats.focused_panel') is None
        old=page.evaluate(ROOT+'.snapshot().config');page.mouse.wheel(0,-40);page.evaluate(ROOT+'.flush()')
        assert page.evaluate(ROOT+'.snapshot().config')==old
        canvas=page.locator('canvas');size=canvas.bounding_box()
        canvas.click(position={'x':100*size['width']/960,'y':100*size['height']/600});page.evaluate(ROOT+'.flush()')
        assert page.evaluate(ROOT+'.stats.focused_panel')=='overview'
        size=canvas.bounding_box();canvas.click(position={'x':480*size['width']/960,'y':150*size['height']/600});page.evaluate(ROOT+'.flush()')
        assert page.evaluate(ROOT+'.stats.focused_panel') is None
        assert page.evaluate(ROOT+'.stats.column_uploads')==uploads
        assert not page.locator('.figgy-error').inner_text()
        execute('await fig.sync()')
        assert json.loads(execute('print(json.dumps(fig.get_settings()))'))['config'].get('active_layer','Base')=='Base'


@pytest.mark.skipif(NEEDS_UI, reason='requires real native and Jupyter inputs')
@pytest.mark.parametrize('backend', ['native', 'webgpu'])
def test_coincident_series_chooser_is_view_only_until_commit(tmp_path, backend):
    """All same-axis and secondary-axis hits remain reachable without reordering."""
    setup = """
ax=fig.axes[0]
ax.plot([1,5,9],[5,5,5],id='red',label='Signal',color='red')
blue=json.loads(json.dumps(fig.get_settings()['series'][0]))
blue['series_id']='blue'
blue['render_type']['Line']['line']['line_color']={'r':0.,'g':0.,'b':1.,'a':1.}
fig._native.add_series_fitted(json.dumps(blue),None,[0.,10.,0.,10.])
twin=ax.twinx(id='pressure_axis')
twin.plot([1,5,9],[50,50,50],id='pressure',label='Pressure',color='green')
ax.set_xlim(0,10);ax.set_ylim(0,10);twin.set_ylim(0,100)
ax.set_title('Overlapping signals');ax.legend();ax.activate()
s=fig.get_settings()
s['series'][0]['render_type']['Line']['line']['fill']={'ToSeries':'blue'}
fig.apply_settings(s)
"""
    def point(rect):
        x,y,w,h=rect
        return x+w/2,y+h/2
    if backend=='native':
        with figgy.Figure(backend=backend) as fig:
            exec(setup,{'fig':fig,'json':json});handle=fig.show(block=False)
            try:
                inputs=Inputs(handle);before=fig.get_settings();revision=fig.revision;uploads=fig.info['column_uploads']
                inputs.click_rect([*point(inputs.info()['decorations']['data_area']),0,0])
                choices=inputs.info()['choice_candidates']
                assert {c['key'] for c in choices}=={'series/red','series/blue','series/pressure'},inputs.info()
                assert fig.get_settings()==before and fig.revision==revision
                inputs.input_frame('mousemove','--window',inputs.wid,*map(round,point(inputs.info()['controls']['choose:series/blue'])))
                assert inputs.info()['choice_preview']=='series/blue'
                assert fig.get_settings()==before and fig.revision==revision
                from PIL import ImageGrab
                window=dict(line.split('=',1) for line in inputs.xdo('getwindowgeometry','--shell',inputs.wid).splitlines())
                x,y,w,h=[int(window[k]) for k in ('X','Y','WIDTH','HEIGHT')]
                ImageGrab.grab(bbox=(x,y-20,x+w,y+h-20),xdisplay=os.environ['DISPLAY']).save(tmp_path/'native-overlap-chooser.png')
                inputs.key('Escape');assert inputs.info()['choice_candidates'] is None
                assert fig.get_settings()==before and fig.revision==revision
                inputs.click_rect([*point(inputs.info()['decorations']['data_area']),0,0])
                inputs.click('choose:series/red')
                assert inputs.info()['selected']=='red' and inputs.info()['properties_open']
                state=fig.get_settings();assert state['config']['picked_data']['refs'][0]['series_id']=='red'
                assert state['series']==before['series']
                assert state['config']['legend']==before['config']['legend']
                # Selection stays available through the tree, including duplicate labels.
                assert fig.info['column_uploads']==uploads
                assert fig.info['rgba_readbacks']==fig.info['png_encodes']==0
                assert not inputs.info()['error']
            finally:handle.close();Inputs.pump()
        return
    source="import json\nimport figgyplot as figgy\nfig=figgy.Figure(backend='webgpu')\n"+setup+"\ndisplay(fig.widget())"
    with notebook(tmp_path/'coincident',source) as (page,execute):
        def click_center():
            area=page.evaluate(ROOT+'.decorations()')['data_area']['rect']
            p=page.evaluate("""p=>{const c=document.querySelector('.figgy-editor canvas'),r=c.getBoundingClientRect();return [r.x+p[0]*r.width/c.width,r.y+p[1]*r.height/c.height];}""",point(area))
            page.mouse.click(*p);page.evaluate(ROOT+'.flush()')
        before=page.evaluate(ROOT+'.snapshot()');uploads=page.evaluate(ROOT+'.stats.column_uploads')
        click_center()
        assert {c['key'] for c in page.evaluate(ROOT+'.stats.choice_candidates')}=={'series/red','series/blue','series/pressure'},page.evaluate(ROOT+'.stats')
        assert page.evaluate(ROOT+'.snapshot()')==before
        page.locator('[data-choice="series/blue"]').hover();page.evaluate(ROOT+'.flush()')
        assert page.evaluate(ROOT+'.stats.choice_preview')=='series/blue'
        assert page.evaluate(ROOT+'.snapshot()')==before
        page.locator('.figgy-editor').screenshot(path=str(tmp_path/'browser-overlap-chooser.png'))
        page.keyboard.press('ArrowDown');page.evaluate(ROOT+'.flush()')
        assert page.evaluate(ROOT+'.stats.choice_preview')!='series/blue'
        assert page.evaluate(ROOT+'.snapshot()')==before
        page.keyboard.press('Escape');page.evaluate(ROOT+'.flush()')
        assert page.locator('.figgy-target-chooser').is_hidden()
        assert page.evaluate(ROOT+'.snapshot()')==before
        click_center();page.locator('[data-choice="series/red"]').click();page.evaluate(ROOT+'.flush()')
        assert ObjectNavigator(page).selected()=='red'
        state=page.evaluate(ROOT+'.snapshot()')
        assert state['config']['picked_data']['refs'][0]['series_id']=='red'
        assert state['series']==before['series'] and state['config']['legend']==before['config']['legend']
        assert page.evaluate(ROOT+'.stats.column_uploads')==uploads
        assert not page.locator('.figgy-error').inner_text()


@pytest.mark.skipif(NEEDS_UI, reason='requires real native and Jupyter inputs')
@pytest.mark.parametrize('backend', ['native', 'webgpu'])
def test_fully_overlapping_panels_keep_the_chosen_chart(tmp_path, backend):
    """Choose a rear chart once; subsequent canvas clicks keep its ownership."""
    setup="""
fig.set_layout([['rear','front']])
for id,name in [('rear','Rear chart'),('front','Front chart')]:
    ax=fig.subplots[id].axes
    ax.plot([1,5,9],[5,5,5],id=id+'_line',label=name)
    ax.set_title(name);ax.set_xlim(0,10);ax.set_ylim(0,10)
fig.subplots['rear'].set_rect(0,0,960,600)
fig.subplots['front'].set_rect(0,0,960,600)
fig.subplots['rear'].axes.activate()
"""
    if backend=='native':
        with figgy.Figure(backend=backend) as fig:
            exec(setup,{'fig':fig,'json':json});handle=fig.show(block=False)
            try:
                inputs=Inputs(handle);before=fig.get_settings();revision=fig.revision
                inputs.click_rect([*native_point(inputs.info(),(300,200)),0,0])
                assert {c['key'] for c in inputs.info()['choice_candidates']}=={'panel/rear','panel/front'}
                assert fig.get_settings()==before and fig.revision==revision
                inputs.click('choose:panel/rear')
                assert inputs.info()['focused_panel']=='rear'
                rect=inputs.info()['decorations']['data_area']
                inputs.click_rect([rect[0]+rect[2]/2,rect[1]+rect[3]/2,0,0])
                assert inputs.info()['selected']=='rear_line'
                assert inputs.info()['focused_panel']=='rear'
                inputs.click('switch_chart');inputs.click('choose:panel/front')
                assert inputs.info()['focused_panel']=='front'
                assert fig.get_settings()['config']['active_layer']=={'Subplot':0}
                # A tree choice of the covered chart also owns following canvas input.
                inputs.click('object_search');inputs.xdo('type','--clearmodifiers','rear_line');inputs.pump()
                inputs.click('tree:series/rear_line')
                assert inputs.info()['focused_panel']=='rear'
                rect=inputs.info()['decorations']['data_area']
                inputs.click_rect([rect[0]+rect[2]/2,rect[1]+rect[3]/2,0,0])
                assert inputs.info()['focused_panel']=='rear'
                assert not inputs.info()['error']
            finally:handle.close();Inputs.pump()
        return
    source="import figgyplot as figgy\nfig=figgy.Figure(backend='webgpu')\n"+setup+"\ndisplay(fig.widget())"
    with notebook(tmp_path/'overlap-panels',source) as (page,execute):
        before=page.evaluate(ROOT+'.snapshot()')
        page.mouse.click(*browser_point(page,(300,200)));page.evaluate(ROOT+'.flush()')
        assert {c['key'] for c in page.evaluate(ROOT+'.stats.choice_candidates')}=={'panel/rear','panel/front'}
        assert page.evaluate(ROOT+'.snapshot()')==before
        page.locator('[data-choice="panel/rear"]').click();page.evaluate(ROOT+'.flush()')
        assert page.evaluate(ROOT+'.stats.focused_panel')=='rear'
        r=page.evaluate(ROOT+'.decorations()')['data_area']['rect']
        p=page.evaluate("""p=>{const c=document.querySelector('.figgy-editor canvas'),r=c.getBoundingClientRect();return [r.x+p[0]*r.width/c.width,r.y+p[1]*r.height/c.height];}""",[r[0]+r[2]/2,r[1]+r[3]/2])
        page.mouse.click(*p);page.evaluate(ROOT+'.flush()')
        assert ObjectNavigator(page).selected()=='rear_line'
        assert page.evaluate(ROOT+'.stats.focused_panel')=='rear'
        page.locator('.figgy-switch-chart').click();page.evaluate(ROOT+'.flush()')
        page.locator('[data-choice="panel/front"]').click();page.evaluate(ROOT+'.flush()')
        assert page.evaluate(ROOT+'.stats.focused_panel')=='front'
        assert page.evaluate(ROOT+'.snapshot().config.active_layer')=={'Subplot':0}
        if page.locator('.figgy-properties').is_hidden():click_button(page, '[data-properties]')
        ObjectNavigator(page).choose('rear_line');page.evaluate(ROOT+'.flush()')
        assert page.evaluate(ROOT+'.stats.focused_panel')=='rear'
        r=page.evaluate(ROOT+'.decorations()')['data_area']['rect']
        p=page.evaluate("""p=>{const c=document.querySelector('.figgy-editor canvas'),r=c.getBoundingClientRect();return [r.x+p[0]*r.width/c.width,r.y+p[1]*r.height/c.height];}""",[r[0]+r[2]/2,r[1]+r[3]/2])
        page.mouse.click(*p);page.evaluate(ROOT+'.flush()')
        assert page.evaluate(ROOT+'.stats.focused_panel')=='rear'
        assert not page.locator('.figgy-error').inner_text()


@pytest.mark.skipif(NEEDS_UI, reason='requires real native and Jupyter inputs')
@pytest.mark.parametrize('backend', ['native', 'webgpu'])
def test_inactive_overlay_objects_can_be_edited_and_dragged_directly(tmp_path, backend):
    """Overlay objects receive input without first activating their layer in a tree."""
    setup="""
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
    if backend=='native':
        with figgy.Figure(backend=backend) as fig:
            exec(setup,{'fig':fig});handle=fig.show(block=False)
            from layout_probe import native_sample, save_native
            samples=[];inputs=None
            try:
                inputs=Inputs(handle);before=fig.get_settings();uploads=fig.info['column_uploads']
                native_sample(inputs,samples,'initial')
                assert before['config'].get('active_layer','Base')=='Base'
                primary_left=inputs.info()['decorations']['axis_left']
                area=inputs.info()['decorations']['data_area'];scale=inputs.info()['chart_panel'][2]/960
                inputs.click_rect([area[0]+area[2]-2+45*scale,area[1]+area[3]*.4,0,0])
                assert inputs.info()['selected']=='overlay_0:axis_right',inputs.info()
                assert fig.get_settings()['config']['active_layer']=={'Overlay':0}
                inputs.click('min');inputs.key('ctrl+a');inputs.xdo('type','--clearmodifiers','10');inputs.key('Return')
                changed=fig.get_settings()
                assert changed['config']['overlays'][0]['y_axis']['min']==10
                assert changed['config']['left_y']==before['config']['left_y']
                # Matching numbers do not make independent coordinate layers linked.
                equal=fig.get_settings();equal['config']['overlays'][0]['y_axis'].update(min=0,max=10,major_spacing=2)
                fig.apply_settings(equal);inputs.pump()
                inputs.click('min');inputs.key('ctrl+a');inputs.xdo('type','--clearmodifiers','1');inputs.key('Return')
                assert fig.get_settings()['config']['overlays'][0]['y_axis']['min']==1
                assert fig.get_settings()['config']['left_y']==before['config']['left_y']
                fig.apply_settings(changed);inputs.pump()
                # The shared left axis belongs to Base even while the overlay is active.
                rect=inputs.info()['decorations']['overlay_0:axis_title_right']
                inputs.click_rect(primary_left)
                assert fig.get_settings()['config'].get('active_layer','Base')=='Base'
                before=fig.get_settings()
                start=(rect[0]+rect[2]/2,rect[1]+rect[3]/2)
                native_sample(inputs,samples,'before_title_drag')
                drag_native(inputs,start,(16,12))
                native_sample(inputs,samples,'after_title_drag')
                assert inputs.info()['selected']=='overlay_0:axis_title_right'
                assert fig.get_settings()['config']['overlays'][0]['y_axis']['title_option']!=before['config']['overlays'][0]['y_axis']['title_option']
                assert fig.get_settings()['config']['left_y']==before['config']['left_y']
                # Common typography precedes the text row in a scrollable form.
                # Exercise ordinary scrolling and real editing at default and
                # minimum supported sizes, rather than requiring every row to
                # be visible immediately after a different object is selected.
                for width,height in ((1312,744),(900,520)):
                    inputs.xdo('windowsize',inputs.wid,width,height);inputs.pump()
                    untouched=fig.get_settings();revision=fig.revision
                    inputs.click('text')
                    info=inputs.info();r=info['controls']['text'];v=info['controls']['properties_viewport']
                    assert r[1]>=v[1]-1 and r[1]+r[3]<=v[1]+v[3]+1,info
                    assert fig.get_settings()==untouched and fig.revision==revision
                    value=f'Pressure {height}'
                    inputs.key('ctrl+a');inputs.xdo('type','--clearmodifiers',value);inputs.key('Return')
                    edited=fig.get_settings()
                    rich=edited['config']['overlays'][0]['y_axis']['title_option']['text']
                    assert ''.join(s['text'] for s in rich['segments'])==value
                    assert rich['font_size']==untouched['config']['overlays'][0]['y_axis']['title_option']['text']['font_size']
                    assert edited['config']['left_y']==before['config']['left_y']
                assert fig.info['column_uploads']==uploads and not inputs.info()['error']
                from PIL import ImageGrab
                window=dict(line.split('=',1) for line in inputs.xdo('getwindowgeometry','--shell',inputs.wid).splitlines())
                x,y,w,h=[int(window[k]) for k in ('X','Y','WIDTH','HEIGHT')]
                ImageGrab.grab(bbox=(x,y-20,x+w,y+h-20),xdisplay=os.environ['DISPLAY']).save(tmp_path/'native-overlay-object-edit.png')
            finally:
                if inputs is not None:save_native(inputs,samples,tmp_path)
                handle.close();Inputs.pump()
        return
    source="import figgyplot as figgy\nfig=figgy.Figure(backend='webgpu')\n"+setup+"\ndisplay(fig.widget())"
    with notebook(tmp_path/'overlay-objects',source) as (page,execute):
        def bounds(target):return page.evaluate(ROOT+'.decorations()')[target]['rect']
        def screen(rect):
            return page.evaluate("""r=>{const c=document.querySelector('.figgy-editor canvas'),b=c.getBoundingClientRect();return [b.x+(r[0]+r[2]/2)*b.width/c.width,b.y+(r[1]+r[3]/2)*b.height/c.height];}""",rect)
        before=page.evaluate(ROOT+'.snapshot()');uploads=page.evaluate(ROOT+'.stats.column_uploads')
        # Decorations exposes the active owner; the shared plot edge plus the
        # configured offset locates the inactive overlay without activating it.
        area=bounds('data_area');page.mouse.click(*screen([area[0]+area[2]-2+45*page.locator('canvas').evaluate('c=>c.width/960'),area[1]+area[3]*.4,0,0]));page.evaluate(ROOT+'.flush()')
        assert ObjectNavigator(page).selected()=='overlay_0:axis_right'
        assert page.evaluate(ROOT+'.snapshot().config.active_layer')=={'Overlay':0}
        page.locator('[data-property=min]').fill('10');page.locator('[data-property=min]').press('Tab');page.evaluate(ROOT+'.flush()')
        changed=page.evaluate(ROOT+'.snapshot()')
        assert changed['config']['overlays'][0]['y_axis']['min']==10
        assert changed['config']['left_y']==before['config']['left_y']
        execute("state=fig.get_settings();state['config']['overlays'][0]['y_axis'].update(min=0,max=10,major_spacing=2);fig.apply_settings(state);print('matched')")
        page.wait_for_function(ROOT+'.snapshot().config.overlays[0].y_axis.max===10')
        page.locator('[data-property=min]').fill('1');page.locator('[data-property=min]').press('Tab');page.evaluate(ROOT+'.flush()')
        assert page.evaluate(ROOT+'.snapshot().config.overlays[0].y_axis.min')==1
        assert page.evaluate(ROOT+'.snapshot().config.left_y')==before['config']['left_y']
        execute(f"fig.apply_settings({changed!r});print('restored')")
        page.wait_for_function(ROOT+'.snapshot().config.overlays[0].y_axis.max===100')
        area=bounds('data_area');page.mouse.click(*screen([area[0]+2,area[1]+area[3]*.4,0,0]));page.evaluate(ROOT+'.flush()')
        assert page.evaluate('('+ROOT+'.snapshot().config.active_layer??"Base")')=='Base'
        # Title geometry is offset to the right of the overlay axis; find its
        # public bounds using the same active-owner decoration API after direct
        # selection of the secondary axis, then return to Base before dragging.
        area=bounds('data_area');scale=page.locator('canvas').evaluate('c=>c.width/960')
        page.mouse.click(*screen([area[0]+area[2]-2+45*scale,area[1]+area[3]*.4,0,0]));page.evaluate(ROOT+'.flush()')
        title=bounds('overlay_0:axis_title_right')
        area=bounds('data_area');page.mouse.click(*screen([area[0]+2,area[1]+area[3]*.4,0,0]));page.evaluate(ROOT+'.flush()')
        before=page.evaluate(ROOT+'.snapshot()');start=screen(title)
        page.mouse.move(*start);page.mouse.down();page.mouse.move(start[0]+16,start[1]+12,steps=5);page.mouse.up();page.evaluate(ROOT+'.flush()')
        assert ObjectNavigator(page).selected()=='overlay_0:axis_title_right'
        assert page.locator('.figgy-inspector-scroll').evaluate('e=>e.scrollTop')==0
        changed=page.evaluate(ROOT+'.snapshot()')
        assert changed['config']['overlays'][0]['y_axis']['title_option']!=before['config']['overlays'][0]['y_axis']['title_option']
        assert changed['config']['left_y']==before['config']['left_y']
        title_text=page.locator('[data-property=text]')
        title_text.fill('Pressure edited');title_text.press('Tab');page.evaluate(ROOT+'.flush()')
        edited=page.evaluate(ROOT+'.snapshot()')
        assert ''.join(s['text'] for s in edited['config']['overlays'][0]['y_axis']['title_option']['text']['segments'])=='Pressure edited'
        assert edited['config']['left_y']==before['config']['left_y']
        assert page.evaluate(ROOT+'.stats.column_uploads')==uploads and not page.locator('.figgy-error').inner_text()
        page.locator('.figgy-editor').screenshot(path=str(tmp_path/'browser-overlay-object-edit.png'))


@pytest.mark.skipif(NEEDS_UI, reason='requires real native and Jupyter inputs')
@pytest.mark.parametrize('panel',['main','child'])
def test_legend_shared_typography_precedes_entries_in_both_hosts(tmp_path,panel):
    setup="ax.plot([0,1,2],[4,3,4],id='unlabelled')\nfor i in range(3): ax.plot([0,1,2],[i,i+1,i],marker=['o','s','^'][i],label=f'10⁻{chr(0x2076+i)} Torr',id=f'p{i}')\nax.legend()"
    if panel=='child':setup="ax.plot([0,1],[8,9],label='Other panel',id='other_panel');ax.legend()\nfig.set_layout([['main','child']]);ax=fig.subplots['child'].axes\n"+setup
    target='subplot_0:legend' if panel=='child' else 'legend'
    tree_panel='child' if panel=='child' else 'main'
    def config(state):return state['config']['subplots'][0]['config'] if panel=='child' else state['config']
    def assert_scope(state):
        if panel=='child':assert 'Other panel' in ''.join(s['text'] for s in state['config']['legend']['content']['segments'])
    def assert_style(state):
        assert_scope(state)
        assert config(state)['legend']['content']['font']=='Liberation Sans'
        assert config(state)['legend']['content']['font_size']==21
        for series in state['series']:
            if series['series_id'].startswith('p') and series['label'] is not None:assert any(s['text']=='-' and s['superscript'] for s in series['label']['segments'])
            if series['label'] is not None:assert not any(s['bold'] for s in series['label']['segments'])
    with figgy.Figure(backend='native') as fig:
        ax=fig.axes[0];exec(setup,{'fig':fig,'ax':ax});handle=fig.show(block=False)
        try:
            inputs=Inputs(handle);inputs.click('properties')
            choose_native_object(inputs,'legend',f'panel/{tree_panel}/legend')
            controls=inputs.info()['controls']
            if panel=='child':assert 'legend_label_other_panel' not in controls
            assert controls['font'][1]<controls['font_size'][1]<controls['legend_label_p0'][1]
            inputs.click('font');inputs.key('ctrl+a');inputs.xdo('type','--clearmodifiers','Liberation Sans');inputs.key('Tab')
            inputs.click('font_size');inputs.key('ctrl+a');inputs.xdo('type','--clearmodifiers','21');inputs.key('Return')
            assert_style(fig.get_settings())
            legend=config(fig.get_settings())['legend']['content']
            fig.configure(series={'p1':{'render_type':{'ScatterLine':{'scatter':{'point_size':5.6}}}}});inputs.pump()
            assert config(fig.get_settings())['legend']['content']==legend
            inputs.click('legend_label_p2');inputs.key('End');inputs.xdo('type','--clearmodifiers',' updated');inputs.key('Tab')
            assert_style(fig.get_settings())
            assert ''.join(s['text'] for s in next(s for s in fig.get_settings()['series'] if s['series_id']=='p2')['label']['segments']).endswith(' updated')
            (tmp_path/'native-legend-settings.json').write_text(json.dumps(fig.get_settings()))
            # Return to the top so the capture shows common controls first.
            choose_native_object(inputs,'chart_title',f'panel/{tree_panel}/chart_title')
            choose_native_object(inputs,'legend',f'panel/{tree_panel}/legend')
            from PIL import ImageGrab
            window=dict(line.split('=',1) for line in inputs.xdo('getwindowgeometry','--shell',inputs.wid).splitlines())
            x,y,w,h=[int(window[k]) for k in ('X','Y','WIDTH','HEIGHT')]
            ImageGrab.grab(bbox=(x,y-20,x+w,y+h-20),xdisplay=os.environ['DISPLAY']).save(tmp_path/'native-legend-typography.png')
            assert not inputs.info()['error']
        finally:handle.close();Inputs.pump()
    source="import json\nimport figgyplot as figgy\nfig,ax=figgy.subplots(backend='webgpu')\n"+setup+"\ndisplay(fig.widget())"
    with notebook(tmp_path/'legend',source) as (page,execute):
        click_button(page, '[data-properties]');ObjectNavigator(page).choose(target)
        if panel=='child':assert page.locator('[data-property=legend_label_other_panel]').count()==0
        order=page.locator('[data-property]').evaluate_all("els=>els.map(el=>el.dataset.property)")
        assert order.index('font')<order.index('font_size')<order.index('legend_label_p0')
        assert page.locator('[data-property=text]').count()==0
        font=page.locator('[data-property=font]');font.fill('Liberation Sans');font.dispatch_event('change');page.evaluate(ROOT+'.flush()')
        size=page.locator('[data-property=font_size]');size.fill('21');size.dispatch_event('change');page.evaluate(ROOT+'.flush()')
        assert_style(page.evaluate(ROOT+'.snapshot()'))
        legend=config(page.evaluate(ROOT+'.snapshot()'))['legend']['content']
        execute("fig.configure(series={'p1':{'render_type':{'ScatterLine':{'scatter':{'point_size':5.6}}}}})");page.evaluate(ROOT+'.flush()')
        assert config(page.evaluate(ROOT+'.snapshot()'))['legend']['content']==legend
        label=page.locator('[data-property=legend_label_p2]');label.fill(label.input_value()+' updated');label.dispatch_event('change');page.evaluate(ROOT+'.flush()')
        execute('await fig.sync()');state=json.loads(execute('print(json.dumps(fig.get_settings()))'))
        assert_style(state)
        assert ''.join(s['text'] for s in next(s for s in state['series'] if s['series_id']=='p2')['label']['segments']).endswith(' updated')
        assert not page.locator('.figgy-error').inner_text()
        screenshot_editor(page,tmp_path/'browser-legend-typography.png')


@pytest.mark.skipif(NEEDS_UI, reason='requires real native and Jupyter inputs')
@pytest.mark.parametrize('owner',['primary','subplot','overlay','shared'])
def test_zoom_recalculates_auto_ticks_and_preserves_fixed_ticks_in_both_hosts(tmp_path,owner):
    setup="ax=fig.axes[0];ax.plot([0,1000],[1,1000],id='base');ax.set_xlim(0,1000);ax.set_ylim(1,1000)\n"
    if owner in ('subplot','shared'):setup+="fig.set_layout([['main','right']]);ax=fig.subplots['right'].axes;ax.plot([0,1000],[1,1000],id='other');ax.set_xlim(0,1000);ax.set_ylim(1,1000)\n"
    if owner=='overlay':setup+="ax=ax.twinx(id='pressure');ax.plot([0,1000],[1,1e9],id='pressure_data');ax.set_yscale('log');ax.set_ylim(1,1e9)\n"
    if owner=='shared':setup+="fig.share_axes('x')\n"
    setup+='ax.activate()'
    key='right_y' if owner=='overlay' else 'bottom_x'
    target='overlay_0:axis_right' if owner=='overlay' else 'subplot_0:axis_bottom' if owner in ('subplot','shared') else 'axis_bottom'
    node='panel/main/overlay/pressure/axis_right' if owner=='overlay' else 'panel/right/axis_bottom' if owner in ('subplot','shared') else 'panel/main/axis_bottom'
    def config(state):return state['config']['subplots'][0]['config'] if owner in ('subplot','shared') else state['config']
    def axis(state):return config(state)['overlays'][0]['y_axis'] if owner=='overlay' else config(state)[key]
    manual="ax.configure(y_axis={'major_spacing':3.0})" if owner=='overlay' else "ax.configure(bottom_x={'major_spacing':7.0},top_x={'major_spacing':7.0})"
    def center(state):
        r=config(state)['chart_area'];return r['x']+r['width']/2,r['y']+r['height']/2
    native_spacing=None
    with figgy.Figure(backend='native') as fig:
        exec(setup,{'fig':fig});handle=fig.show(block=False)
        try:
            inputs=Inputs(handle);before=fig.get_settings();spacing=axis(before)['major_spacing'];uploads=fig.info['column_uploads']
            x,y=native_point(inputs.info(),center(before));modifier='shift' if owner=='overlay' else 'ctrl'
            if owner in ('subplot','shared'):inputs.click_rect([x,y,0,0])
            def zoom():
                inputs.xdo('mousemove','--window',inputs.wid,round(x),round(y));inputs.pump();inputs.xdo('keydown',modifier);inputs.xdo('click','--repeat',8,'--delay',15,4);inputs.xdo('keyup',modifier);inputs.pump()
            zoom();current=fig.get_settings();native_spacing=axis(current)['major_spacing']
            assert native_spacing<spacing
            if owner=='overlay':assert current['config']['left_y']==before['config']['left_y']
            if owner=='subplot':assert current['config']['bottom_x']==before['config']['bottom_x']
            # Explicit numeric configuration selects fixed ticks and survives zoom.
            ax=fig._axes_for('right' if owner in ('subplot','shared') else 'main','pressure' if owner=='overlay' else None)
            exec(manual,{'ax':ax});inputs.pump();fixed=axis(fig.get_settings())['major_spacing'];zoom()
            assert axis(fig.get_settings())['major_spacing']==fixed
            inputs.click('properties');choose_native_object(inputs,'axis_right' if owner=='overlay' else 'axis_bottom',node)
            inputs.click('auto_ticks');inputs.pump()
            assert axis(fig.get_settings())['major_spacing']!=fixed
            if owner=='shared':
                state=fig.get_settings()
                assert state['config']['bottom_x']['major_spacing']==axis(state)['major_spacing']
                assert state['identity']['tick_modes']['main']['bottom_x']=='Auto'
                inputs.click('major_spacing');inputs.key('ctrl+a');inputs.xdo('type','--clearmodifiers','13');inputs.key('Return')
                state=fig.get_settings()
                assert state['config']['bottom_x']['major_spacing']==axis(state)['major_spacing']==13
                assert state['identity']['tick_modes']['main']['bottom_x']=='Fixed'
            assert fig.info['column_uploads']==uploads
            assert not inputs.info()['error']
        finally:handle.close();Inputs.pump()
    source="import json\nimport figgyplot as figgy\nfig=figgy.Figure(backend='webgpu')\n"+setup+"\ndisplay(fig.widget())"
    with notebook(tmp_path/owner,source) as (page,execute):
        click_button(page, '[data-properties]');ObjectNavigator(page).choose(target,node=node)
        state=page.evaluate(ROOT+'.snapshot()');x,y=browser_point(page,center(state));modifier='Shift' if owner=='overlay' else 'Control'
        def zoom():
            page.mouse.move(x,y);page.keyboard.down(modifier);page.mouse.wheel(0,-320);page.keyboard.up(modifier);page.evaluate(ROOT+'.flush()')
        before=axis(state)['major_spacing'];zoom();state=page.evaluate(ROOT+'.snapshot()')
        assert axis(state)['major_spacing']<before
        assert axis(state)['major_spacing']==native_spacing
        # Kernel idle does not acknowledge delivery of the widget-state update.
        # Capture the baseline only after the browser has accepted this command.
        accepted=json.loads(execute(manual+'; await fig.sync(); print(json.dumps(fig.get_settings()))'))
        fixed=axis(accepted)['major_spacing']
        browser_fixed=page.evaluate(ROOT+'.snapshot()')
        (tmp_path/'fixed-tick-baseline.json').write_text(json.dumps({'accepted':accepted,'browser':browser_fixed},indent=2))
        assert fixed==(3.0 if owner=='overlay' else 7.0)
        assert axis(browser_fixed)['major_spacing']==fixed
        zoom()
        assert axis(page.evaluate(ROOT+'.snapshot()'))['major_spacing']==fixed
        ObjectNavigator(page).choose(target,node=node);page.locator('[data-property=auto_ticks]').check();page.evaluate(ROOT+'.flush()')
        assert axis(page.evaluate(ROOT+'.snapshot()'))['major_spacing']!=fixed
        if owner=='shared':
            state=page.evaluate(ROOT+'.snapshot()')
            assert state['config']['bottom_x']['major_spacing']==axis(state)['major_spacing']
            assert state['identity']['tick_modes']['main']['bottom_x']=='Auto'
            spacing=page.locator('[data-property=major_spacing]');spacing.fill('13');spacing.press('Tab');page.evaluate(ROOT+'.flush()')
            state=page.evaluate(ROOT+'.snapshot()')
            assert state['config']['bottom_x']['major_spacing']==axis(state)['major_spacing']==13
            assert state['identity']['tick_modes']['main']['bottom_x']=='Fixed'
        execute('await fig.sync()');accepted=json.loads(execute('print(json.dumps(fig.get_settings()))'))
        assert accepted['identity']['tick_modes']==page.evaluate(ROOT+'.snapshot().identity.tick_modes')
        assert not page.locator('.figgy-error').inner_text()

@pytest.mark.skipif(NEEDS_UI, reason='requires real native and Jupyter inputs')
@pytest.mark.parametrize('backend',['native','webgpu'])
@pytest.mark.parametrize('kind',['cartesian','categorical','boxplot'])
def test_anchor_mode_controls_preserve_the_prepared_annotation_rectangle(tmp_path,backend,kind):
    setup={'cartesian':"ax.plot([0,10],[0,20],id='signal');ax.set_xlim(0,10);ax.set_ylim(0,20)", 'categorical':"ax.bar(['A','B'],[5,10])",'boxplot':"ax.boxplot([[1,2,3],[2,4,6]])"}[kind]
    setup+=";ax.text(0,5,'Keep position',coords='data',id='probe')"
    target='annotation:probe' if kind=='cartesian' else 'annotation_0';key=('panel/main' if kind=='cartesian' else 'bounded')+'/annotation/probe'
    if backend=='native':
        with figgy.Figure(backend=backend,id='anchor-ui') as fig:
            exec(setup,{'fig':fig,'ax':fig.axes[0]});handle=fig.show(block=False)
            try:
                inputs=Inputs(handle);inputs.click('properties');choose_native_object(inputs,'Keep position',key)
                inputs.click('section:Coordinates');before=json.loads(fig._native.bounds_json(target))['rect']
                inputs.click('property:Coordinates/anchor');inputs.click('anchor_Ratio')
                after=json.loads(fig._native.bounds_json(target))['rect']
                assert after==pytest.approx(before,abs=.01)
                assert 'Ratio' in fig.get_settings()['config' if kind=='cartesian' else kind]['annotations']['items'][0]['kind']['Text']['anchor']
                inputs.click('undo');assert json.loads(fig._native.bounds_json(target))['rect']==pytest.approx(before,abs=.01)
                assert not inputs.info()['error']
            finally:handle.close();Inputs.pump()
        return
    source='import json\nimport figgyplot as fg\nfig=fg.Figure(backend="webgpu",id="anchor-ui")\nax=fig.axes[0]\n'+setup+'\ndisplay(fig.widget())'
    with notebook(tmp_path/(kind+'-anchor'),source) as (page,execute):
        click_button(page, '[data-properties]');ObjectNavigator(page).choose(target,node=key)
        page.locator('[data-property-section="Coordinates"] summary').click()
        before=page.evaluate(ROOT+'.annotations()')[0]['rect']
        page.locator('[data-catalog-field="Coordinates/anchor"]').select_option('Ratio');page.evaluate(ROOT+'.flush()')
        after=page.evaluate(ROOT+'.annotations()')[0]['rect']
        assert after==pytest.approx(before,abs=.01)
        state=json.loads(execute('print(json.dumps(fig.get_settings()))'))
        assert 'Ratio' in state['config' if kind=='cartesian' else kind]['annotations']['items'][0]['kind']['Text']['anchor']
        click_button(page, '[data-undo]');page.evaluate(ROOT+'.flush()')
        assert page.evaluate(ROOT+'.annotations()')[0]['rect']==pytest.approx(before,abs=.01)
        assert not page.locator('.figgy-error').inner_text()


@pytest.mark.skipif(NEEDS_UI, reason='requires real native and Jupyter inputs')
@pytest.mark.parametrize('backend',['native','webgpu'])
def test_reset_button_restores_the_presented_chart_and_can_be_undone(tmp_path,backend):
    setup="ax=fig.axes[0];ax.plot([0,1,2],[1,3,2],id='signal');ax.set_title('Original')"
    if backend=='native':
        with figgy.Figure(backend=backend,id='reset-ui') as fig:
            exec(setup,{'fig':fig});handle=fig.show(block=False)
            try:
                inputs=Inputs(handle);initial=fig.get_settings()['series'][0]['render_type']['Line']['line']['line_width']
                inputs.click('properties');choose_native_object(inputs,'signal','series/signal')
                inputs.click('line_width');inputs.key('ctrl+a');inputs.xdo('type','--clearmodifiers','8');inputs.key('Return')
                choose_native_object(inputs,'Figure','figure/reset-ui');inputs.click('reset_edits')
                assert fig.get_settings()['series'][0]['render_type']['Line']['line']['line_width']==initial
                assert not fig.edit_history['can_reset']
                inputs.click('undo');assert fig.get_settings()['series'][0]['render_type']['Line']['line']['line_width']==8
                assert not inputs.info()['error']
            finally:handle.close();Inputs.pump()
        return
    source='import json\nimport figgyplot as fg\nfig=fg.Figure(backend="webgpu",id="reset-ui")\n'+setup+'\ndisplay(fig.widget())'
    with notebook(tmp_path/'reset-ui',source) as (page,execute):
        initial=page.evaluate(ROOT+'.snapshot()')['series'][0]['render_type']['Line']['line']['line_width']
        click_button(page, '[data-properties]');ObjectNavigator(page).choose('signal')
        field=page.locator('[data-property=line_width]');field.fill('8');field.press('Tab');page.evaluate(ROOT+'.flush()')
        ObjectNavigator(page).choose('figure',node='figure/reset-ui');click_button(page, '[data-reset-edits]');page.evaluate(ROOT+'.flush()')
        assert page.evaluate(ROOT+'.snapshot()')['series'][0]['render_type']['Line']['line']['line_width']==initial
        assert not json.loads(execute('print(json.dumps(fig.edit_history))'))['can_reset']
        click_button(page, '[data-undo]');page.evaluate(ROOT+'.flush()')
        assert page.evaluate(ROOT+'.snapshot()')['series'][0]['render_type']['Line']['line']['line_width']==8
        assert not page.locator('.figgy-error').inner_text()

@pytest.mark.skipif(NEEDS_UI, reason='requires real native and Jupyter inputs')
@pytest.mark.parametrize('backend',['native','webgpu'])
def test_all_colormap_controls_change_data_and_bar_pixels_and_undo(tmp_path,backend):
    import hashlib
    from PIL import Image
    setup="ax=fig.axes[0];ax.scatter([0,1,2],[1,2,1],c=[0,.5,1],s=400,id='signal');ax.set_xlim(-.5,2.5);ax.set_ylim(0,3)"
    maps=['Viridis','Magma','Turbo','RdBu','GrayScale']
    def region(pixels,rect,inset=0):
        x,y,w,h=rect
        return np.asarray(pixels)[round(y+h*inset):round(y+h*(1-inset)),round(x+w*inset):round(x+w*(1-inset)),:3]
    def hashes(pixels,boxes):
        return tuple(hashlib.sha256(region(pixels,rect,.1 if i==0 else 0).tobytes()).hexdigest() for i,rect in enumerate(boxes))
    if backend=='native':
        with figgy.Figure(backend=backend) as fig:
            exec(setup,{'fig':fig});handle=fig.show(block=False)
            try:
                inputs=Inputs(handle);inputs.click('properties');uploads=fig.info['column_uploads'];seen=[]
                for index,cmap in enumerate(maps):
                    if index%2:choose_native_object(inputs,'signal','series/signal')
                    else:inputs.click_rect(inputs.info()['decorations']['colorbar'])
                    if 'colormap' not in inputs.info()['controls']:inputs.click('section:Color scale')
                    inputs.click('colormap');inputs.click('colormap_'+cmap)
                    boxes=[json.loads(fig._native.bounds_json(name))['rect'] for name in ('data_area','colorbar')]
                    pixels=fig.render_rgba();seen.append(hashes(pixels,boxes))
                    assert fig.get_settings()['config']['colorbar']['colormap']==cmap
                assert all(len({v[i] for v in seen})==5 for i in (0,1))
                gray=region(pixels,boxes[0],.1).astype(int);assert np.max(gray.max(axis=2)-gray.min(axis=2))<=2
                inputs.click('undo');assert hashes(fig.render_rgba(),boxes)==seen[-2]
                assert fig.info['column_uploads']==uploads and not inputs.info()['error']
            finally:handle.close();Inputs.pump()
        return
    source='import json\nimport figgyplot as fg\nfig=fg.Figure(backend="webgpu")\n'+setup+'\ndisplay(fig.widget())'
    with notebook(tmp_path/'colormap-pixels',source) as (page,execute):
        click_button(page, '[data-properties]');seen=[];uploads=page.evaluate(ROOT+'.stats.column_uploads')
        for index,cmap in enumerate(maps):
            ObjectNavigator(page).choose('signal' if index%2 else 'colorbar')
            section=page.locator('[data-property-section="Color scale"]')
            if not section.evaluate('element=>element.open'):section.locator('summary').click()
            page.locator('[data-property=colormap]').select_option(cmap);page.evaluate(ROOT+'.flush()')
            path=tmp_path/(cmap+'.png');execute(f'await fig.savefig_async({str(path)!r})');pixels=np.array(Image.open(path).convert('RGB'))
            decorations=page.evaluate(ROOT+'.decorations()');w,h=page.locator('canvas').evaluate('c=>[c.width,c.height]')
            boxes=[[r[0]*960/w,r[1]*600/h,r[2]*960/w,r[3]*600/h] for r in [decorations[name]['rect'] for name in ('data_area','colorbar')]]
            seen.append(hashes(pixels,boxes))
            assert page.evaluate(ROOT+'.snapshot()')['config']['colorbar']['colormap']==cmap
        assert all(len({v[i] for v in seen})==5 for i in (0,1))
        gray=region(pixels,boxes[0],.1).astype(int);assert np.max(gray.max(axis=2)-gray.min(axis=2))<=2
        click_button(page, '[data-undo]');page.evaluate(ROOT+'.flush()')
        path=tmp_path/'undo.png';execute(f'await fig.savefig_async({str(path)!r})')
        assert hashes(np.array(Image.open(path).convert('RGB')),boxes)==seen[-2]
        assert page.evaluate(ROOT+'.stats.column_uploads')==uploads and not page.locator('.figgy-error').inner_text()

@pytest.mark.skipif(NEEDS_UI, reason='requires real native and Jupyter inputs')
@pytest.mark.parametrize('backend',['native','webgpu'])
def test_palette_entry_buttons_and_numeric_fields_use_real_controls(tmp_path,backend):
    setup="ax=fig.axes[0];ax.scatter([0,1,2],[1,3,2],id='signal',label='Signal');ax.set_xlim(-.5,2.5);ax.set_ylim(0,4)"
    if backend=='native':
        with figgy.Figure(backend=backend) as fig:
            exec(setup,{'fig':fig});handle=fig.show(block=False)
            try:
                inputs=Inputs(handle);inputs.click('properties');choose_native_object(inputs,'signal','series/signal')
                inputs.click('section:Marker palette');inputs.click('property:Marker palette/add')
                inputs.click('property:Marker palette/source');inputs.click('point_style_index_column_signal/x')
                inputs.click('property:Marker palette/entry/1/override/point_size')
                pixels_before=fig.render_rgba().astype(int)
                field='property:Marker palette/entry/1/point_size';inputs.click(field);inputs.key('ctrl+a');inputs.xdo('type','--clearmodifiers','9');inputs.key('Return')
                assert fig.get_settings()['series'][0]['render_type']['Scatter']['scatter']['point_style_table'][0]['point_size']==9
                pixels_after=fig.render_rgba().astype(int)
                blue=lambda p:np.count_nonzero((p[:,:,2]>p[:,:,0]+20)&(p[:,:,2]>p[:,:,1]+20))
                assert blue(pixels_after)>blue(pixels_before)
                from PIL import ImageGrab
                geometry=dict(line.split('=',1) for line in inputs.xdo('getwindowgeometry','--shell',inputs.wid).splitlines() if '=' in line)
                x,y,w,h=(int(geometry[key]) for key in ('X','Y','WIDTH','HEIGHT'))
                ImageGrab.grab(xdisplay=os.environ['DISPLAY']).crop((x,y,x+w,y+h)).save(tmp_path/'native-marker-palette.png')
                inputs.click('undo');inputs.click('undo');inputs.click('undo');inputs.click('undo')
                assert fig.get_settings()['series'][0]['render_type']['Scatter']['scatter'].get('point_style_table') is None
                assert not inputs.info()['error']
            finally:handle.close();Inputs.pump()
        return
    source='import json\nimport figgyplot as fg\nfig=fg.Figure(backend="webgpu")\n'+setup+'\ndisplay(fig.widget())'
    with notebook(tmp_path/'palette-controls',source) as (page,execute):
        click_button(page, '[data-properties]');ObjectNavigator(page).choose('signal')
        page.locator('[data-property-section="Marker palette"] summary').click()
        page.locator('[data-catalog-field="Marker palette/add"]').click();page.evaluate(ROOT+'.flush()')
        page.locator('[data-catalog-field="Marker palette/source"]').select_option('signal/x');page.evaluate(ROOT+'.flush()')
        page.locator('[data-catalog-field="Marker palette/entry/1/override/point_size"]').check();page.evaluate(ROOT+'.flush()')
        before_path=tmp_path/'palette-before.png';execute(f'await fig.savefig_async({str(before_path)!r})')
        # A comm refresh preserves the expanded group and selected object.
        field=page.locator('[data-catalog-field="Marker palette/entry/1/point_size"]')
        field.fill('9');field.press('Tab');page.evaluate(ROOT+'.flush()')
        assert page.evaluate(ROOT+'.snapshot()')['series'][0]['render_type']['Scatter']['scatter']['point_style_table'][0]['point_size']==9
        from PIL import Image
        after_path=tmp_path/'palette-after.png';execute(f'await fig.savefig_async({str(after_path)!r})')
        blue=lambda p:np.count_nonzero((p[:,:,2]>p[:,:,0]+20)&(p[:,:,2]>p[:,:,1]+20))
        assert blue(np.array(Image.open(after_path).convert('RGB')).astype(int))>blue(np.array(Image.open(before_path).convert('RGB')).astype(int))
        screenshot_editor(page,tmp_path/'browser-marker-palette.png')
        for _ in range(4):click_button(page, '[data-undo]');page.evaluate(ROOT+'.flush()')
        assert page.evaluate(ROOT+'.snapshot()')['series'][0]['render_type']['Scatter']['scatter'].get('point_style_table') is None
        assert not page.locator('.figgy-error').inner_text()

@pytest.mark.skipif(NEEDS_UI, reason='requires real native and Jupyter inputs')
@pytest.mark.parametrize('backend',['native','webgpu'])
def test_timestamp_offset_accepts_negative_integer_entry_in_both_inspectors(tmp_path,backend):
    setup="ax=fig.axes[0];ax.plot([0,1,2],[1,3,2],id='signal');fig.configure(config={'bottom_x':{'label_style':{'format':{'Timestamp':{'timezone':{'FixedOffsetMinutes':0},'label':{'Pattern':'%H:%M'}}}}}})"
    prop='Layout and appearance/format/Timestamp/timezone/FixedOffsetMinutes'
    if backend=='native':
        with figgy.Figure(backend=backend) as fig:
            exec(setup,{'fig':fig});handle=fig.show(block=False)
            try:
                inputs=Inputs(handle);inputs.click('properties');choose_native_object(inputs,'tick labels','panel/main/tick_labels_bottom')
                inputs.click('section:Layout and appearance');inputs.click('property:'+prop);inputs.key('ctrl+a');inputs.xdo('type','--clearmodifiers','--','-420');inputs.key('Return')
                assert fig.get_settings()['config']['bottom_x']['label_style']['format']['Timestamp']['timezone']=={'FixedOffsetMinutes':-420}
                assert not inputs.info()['error']
            finally:handle.close();Inputs.pump()
        return
    source='import json\nimport figgyplot as fg\nfig=fg.Figure(backend="webgpu")\n'+setup+'\ndisplay(fig.widget())'
    with notebook(tmp_path/'timestamp-offset',source) as (page,execute):
        click_button(page, '[data-properties]');ObjectNavigator(page).choose('tick_labels_bottom')
        page.locator('[data-property-section="Layout and appearance"] summary').click()
        field=page.locator('[data-catalog-field="'+prop+'"]');field.fill('-420');field.press('Tab');page.evaluate(ROOT+'.flush()')
        assert page.evaluate(ROOT+'.snapshot()')['config']['bottom_x']['label_style']['format']['Timestamp']['timezone']=={'FixedOffsetMinutes':-420}
        assert not page.locator('.figgy-error').inner_text()

@pytest.mark.skipif(NEEDS_UI, reason='requires real Jupyter inputs')
def test_browser_property_ack_advances_its_base_but_rejects_external_conflicts(tmp_path):
    source="import json\nimport figgyplot as fg\nfig=fg.Figure(backend='webgpu')\nfig.axes[0].plot([0,1,2],[1,3,2],id='signal')\ndisplay(fig.widget())"
    with notebook(tmp_path/'property-conflict',source) as (page,execute):
        click_button(page, '[data-properties]');ObjectNavigator(page).choose('signal')
        field=page.locator('[data-property=line_width]')
        for value in ('4','8'):
            field.fill(value);field.press('Tab');page.evaluate(ROOT+'.flush()')
            assert page.evaluate(ROOT+'.snapshot()')['series'][0]['render_type']['Line']['line']['line_width']==int(value)
        field.fill('6')
        execute("fig.configure(series={'signal':{'render_type':{'Line':{'line':{'line_width':12}}}}}); await fig.sync()")
        assert field.input_value()=='6'
        before=page.evaluate(ROOT+'.snapshot()')
        field.press('Tab');page.evaluate(ROOT+'.flush()')
        assert 'stale edit' in page.locator('.figgy-error').inner_text()
        assert page.evaluate(ROOT+'.snapshot()')==before
        assert json.loads(execute('print(json.dumps(fig.get_settings()))'))==before
        click_button(page, '[data-undo]');page.evaluate(ROOT+'.flush()')
        assert page.evaluate(ROOT+'.snapshot()')['series'][0]['render_type']['Line']['line']['line_width']==8

@pytest.mark.skipif(NEEDS_UI, reason='requires real native and Jupyter inputs')
@pytest.mark.parametrize('backend',['native','webgpu'])
def test_colorbar_title_has_a_direct_text_control_in_both_hosts(tmp_path,backend):
    setup="ax=fig.axes[0];ax.imshow([[0,1],[2,3]],id='field');fig.configure(config={'colorbar':{'axis':{'title_option':{'visible':True}}}})"
    prop='Title/text/plain_text'
    if backend=='native':
        with figgy.Figure(backend=backend) as fig:
            exec(setup,{'fig':fig});handle=fig.show(block=False)
            try:
                inputs=Inputs(handle);inputs.click('properties');choose_native_object(inputs,'colorbar_title','panel/main/colorbar_title')
                inputs.click('property:'+prop);inputs.key('ctrl+a');inputs.xdo('type','--clearmodifiers','Temperature (K)');inputs.key('Tab')
                rich=fig.get_settings()['config']['colorbar']['axis']['title_option']['text']
                assert ''.join(v['text'] for v in rich['segments'])=='Temperature (K)'
                assert json.loads(fig._native.bounds_json('colorbar_title'))['rect'][3]>0
                history_before=fig.edit_history
                inputs.click('undo');assert not fig.get_settings()['config']['colorbar']['axis']['title_option']['text']['segments'], (inputs.info()['error'],history_before,fig.edit_history,fig.edit_operations()[-3:])
                assert not inputs.info()['error']
            finally:handle.close();Inputs.pump()
        return
    source='import json\nimport figgyplot as fg\nfig=fg.Figure(backend="webgpu")\n'+setup+'\ndisplay(fig.widget())'
    with notebook(tmp_path/'colorbar-title',source) as (page,execute):
        click_button(page, '[data-properties]');ObjectNavigator(page).choose('colorbar_title')
        field=page.locator('[data-catalog-field="'+prop+'"]');field.fill('Temperature (K)');field.press('Tab');page.evaluate(ROOT+'.flush()')
        assert ''.join(v['text'] for v in page.evaluate(ROOT+'.snapshot()')['config']['colorbar']['axis']['title_option']['text']['segments'])=='Temperature (K)'
        assert page.evaluate(ROOT+'.decorations()')['colorbar_title']['rect'][3]>0
        click_button(page, '[data-undo]');page.evaluate(ROOT+'.flush()')
        assert not page.evaluate(ROOT+'.snapshot()')['config']['colorbar']['axis']['title_option']['text']['segments']
        assert not page.locator('.figgy-error').inner_text()

@pytest.mark.skipif(NEEDS_UI, reason='requires real native and Jupyter inputs')
@pytest.mark.parametrize('backend',['native','webgpu'])
def test_radial_detail_tree_selection_edits_only_the_chosen_child(tmp_path,backend):
    setup="ax=fig.axes[0];ax.pie([3,2,1]);child=copy.deepcopy(fig.get_settings()['radial']['slices'][0]);child.update(value=1,label='Detail A');other=copy.deepcopy(child);other.update(value=2,label='Detail B');fig.configure_radial(split={'slice_index':0,'children':[child,other],'kind':'Pie'})"
    if backend=='native':
        import copy
        with figgy.Figure(backend=backend) as fig:
            exec(setup,{'fig':fig,'copy':copy});handle=fig.show(block=False)
            samples=[];started=time.monotonic();inputs=None
            def probe(stage):
                sample={'stage':stage,'elapsed_seconds':time.monotonic()-started,
                        'settings':fig.get_settings(),'host':json.loads(handle.info_json())}
                if inputs is not None:
                    (tmp_path/'native-input-events.json').write_text(json.dumps(inputs.events))
                samples.append(sample)
                (tmp_path/'native-detail-states.json').write_text(json.dumps(samples))
            try:
                inputs=Inputs(handle);probe('opened')
                inputs.click('properties');probe('properties')
                choose_native_object(inputs,'Detail B','bounded/series/slice_1_1');probe('selected-child')
                inputs.click('section:Series style');probe('style-section')
                inputs.click('property:Series style/custom');probe('custom-style')
                inputs.click('property:Series style/style/gap_degrees');inputs.key('ctrl+a');inputs.xdo('type','--clearmodifiers','5');inputs.key('Return')
                probe('edited-gap')
                chart=fig.get_settings()['radial'];assert chart['split']['children'][1]['style']['gap_degrees']==5
                assert chart['split']['children'][0]['style'] is None and all(v['style'] is None for v in chart['slices'])
                assert not inputs.info()['error']
            except Exception:
                probe('failure')
                print('FIGGY NATIVE DETAIL FAILURE '+json.dumps(samples[-1]),flush=True)
                raise
            finally:handle.close();Inputs.pump()
        return
    source='import copy,json\nimport figgyplot as fg\nfig=fg.Figure(backend="webgpu")\n'+setup+'\ndisplay(fig.widget())'
    with notebook(tmp_path/'radial-detail',source) as (page,execute):
        click_button(page, '[data-properties]');ObjectNavigator(page).choose('slice_1_1',node='bounded/series/slice_1_1')
        page.locator('[data-property-section="Series style"] summary').click()
        page.locator('[data-catalog-field="Series style/custom"]').check();page.evaluate(ROOT+'.flush()')
        field=page.locator('[data-catalog-field="Series style/style/gap_degrees"]');field.fill('5');field.press('Tab');page.evaluate(ROOT+'.flush()')
        chart=page.evaluate(ROOT+'.snapshot()')['radial'];assert chart['split']['children'][1]['style']['gap_degrees']==5
        assert chart['split']['children'][0]['style'] is None and all(v['style'] is None for v in chart['slices'])
        assert not page.locator('.figgy-error').inner_text()

@pytest.mark.skipif(NEEDS_UI, reason='requires real native inputs')
def test_closing_native_window_finishes_accepted_text_edit():
    with figgy.Figure(backend='native') as fig:
        fig.axes[0].imshow([[0,1],[2,3]],id='field')
        fig.configure(config={'colorbar':{'axis':{'title_option':{'visible':True}}}})
        handle=fig.show(block=False)
        try:
            inputs=Inputs(handle);inputs.click('properties');choose_native_object(inputs,'colorbar_title','panel/main/colorbar_title')
            inputs.click('property:Title/text/plain_text');inputs.xdo('type','--clearmodifiers','Temperature');inputs.key('Tab')
            assert fig.edit_history['pending_edit']
        finally:
            handle.close();Inputs.pump()
        assert not fig.edit_history['gesture_active']
        fig.undo()
        assert not fig.get_settings()['config']['colorbar']['axis']['title_option']['text']['segments']

@pytest.mark.skipif(NEEDS_UI, reason='requires a real notebook WebGPU surface')
def test_large_logarithmic_values_render_at_their_projected_height_in_both_hosts(tmp_path):
    """Large linear operands must not cancel the logarithm in GPU projection."""
    from PIL import Image
    setup="ax=fig.axes[0];ax.scatter([1,2,3],[1e6,1e8,1e10],color='blue',s=100,id='large');ax.set_xlim(0,4);ax.set_yscale('log');ax.set_ylim(1e5,1e11);ax.grid(False)"
    def check(pixels,rect):
        x,y,w,h=rect;pixels=np.asarray(pixels)
        for vx,decade in [(1,6),(2,8),(3,10)]:
            px,py=round(x+w*vx/4),round(y+h*(11-decade)/6)
            patch=pixels[py-4:py+5,px-4:px+5,:3]
            assert np.any((patch[:,:,2]>180)&(patch[:,:,0]<80)&(patch[:,:,1]<80)), (vx,decade,rect)
    with figgy.Figure(backend='native') as fig:
        exec(setup,{'fig':fig});check(fig.render_rgba(),json.loads(fig._native.bounds_json('data_area'))['rect'])
    source='import figgyplot as fg\nfig=fg.Figure(backend="webgpu")\n'+setup+'\ndisplay(fig.widget())'
    with notebook(tmp_path/'large-log',source) as (page,execute):
        path=tmp_path/'large-log.png';execute(f'await fig.savefig_async({str(path)!r})')
        rect=page.evaluate(ROOT+'.decorations()')['data_area']['rect']
        width,height=page.locator('.figgy-editor canvas').evaluate('(c)=>[c.width,c.height]')
        check(Image.open(path).convert('RGB'),[rect[0]*960/width,rect[1]*600/height,rect[2]*960/width,rect[3]*600/height])
        assert not page.locator('.figgy-error').inner_text()


@pytest.mark.skipif(NEEDS_UI, reason='requires real native and notebook review inputs')
@pytest.mark.parametrize('backend',['native','webgpu'])
@pytest.mark.parametrize('family',['cartesian','radial'])
def test_review_submission_keeps_comments_and_view_on_storage_failure(tmp_path,monkeypatch,backend,family):
    from figgyplot.review import Session
    setup="ax=fig.axes[0];ax.plot([0,1],[1,3],id='signal')" if family=='cartesian' else "ax=fig.axes[0];ax.pie([3,2,1])"
    comments='Keep the title and adjust the legend next'
    cache=tmp_path/'review-cache'
    if backend=='native':
        with Session(cache) as session:
            fig=session.figure(id='review-chart');exec(setup,{'fig':fig})
            session.present();handle=fig._windows[-1];inputs=Inputs(handle)
            inputs.click('review_comments');inputs.xdo('type','--clearmodifiers',comments);inputs.pump()
            fig.axes[0].set_title('Human chart title');inputs.pump()
            inputs.click('draw');inputs.click('draw_text')
            px,py=native_point(inputs.info(),(350,250));inputs.click_rect([px,py,0,0])
            inputs.xdo('type','--clearmodifiers','Human annotation');inputs.pump()
            inputs.click('review_changes')
            assert json.loads(handle.review_request_json())['comments']==comments
            assert not handle.closed
            def fail(*args):raise OSError('simulated storage failure')
            with monkeypatch.context() as patch:
                patch.setattr(session._store,'write',fail);session.poll()
            inputs.pump()
            assert not handle.closed and not session.events()
            assert inputs.info()['review']['comments']==comments
            assert 'simulated storage failure' in inputs.info()['review']['error']
            from PIL import ImageGrab
            geometry=dict(line.split('=',1) for line in inputs.xdo('getwindowgeometry','--shell',inputs.wid).splitlines() if '=' in line)
            x,y,w,h=(int(geometry[key]) for key in ('X','Y','WIDTH','HEIGHT'))
            ImageGrab.grab(xdisplay=os.environ['DISPLAY']).crop((x,y,x+w,y+h)).save(tmp_path/'native-review.png')
            inputs.click('review_changes');session.poll();assert handle.closed
            feedback=session.feedback(session.events()[0]['work_id'])['round']['documents']['review-chart']
            assert feedback['comments'][0]['text']==comments
            assert comments not in json.dumps(feedback['approval']['settings'])
            owner=feedback['approval']['settings']['radial' if family=='radial' else 'config']
            assert ''.join(s['text'] for s in owner['annotations']['items'][-1]['kind']['Text']['text']['segments'])=='Human annotation'
            assert feedback['approval']['changes']
        return
    source="import json\nfrom figgyplot.review import Session\nsession=Session("+repr(str(cache))+",backend='webgpu')\nfig=session.figure(id='review-chart')\n"+setup+"\ndisplay(session.widget(fig))"
    with notebook(tmp_path/'notebook-review',source,allow_closed=True) as (page,execute):
        field=page.locator('[data-review-comments]');field.fill(comments);field.press('Tab')
        execute("fig.axes[0].set_title('Human chart title'); await fig.sync()")
        execute("real_write=session._store.write\ndef fail_write(*args):\n    raise OSError('simulated storage failure')\nsession._store.write=fail_write")
        click_button(page,'[data-draw]');click_button(page,'[data-tool=text]')
        page.mouse.click(*browser_point(page,(350,250)))
        page.locator('[data-inline-text]').fill('Human annotation')
        click_button(page,'[data-review-changes]')
        page.wait_for_function("document.querySelector('[data-review-status]').textContent.includes('simulated storage failure')")
        assert field.input_value()==comments
        assert json.loads(execute('print(json.dumps(session.events()))'))==[]
        screenshot_editor(page,tmp_path/'browser-review.png')
        execute('session._store.write=real_write')
        click_button(page,'[data-review-changes]')
        page.wait_for_function("!document.querySelector('.figgy-editor')")
        feedback=json.loads(execute('print(json.dumps(session.feedback(session.events()[0]["work_id"])))'))['round']['documents']['review-chart']
        assert feedback['comments'][0]['text']==comments
        assert comments not in json.dumps(feedback['approval']['settings'])
        owner=feedback['approval']['settings']['radial' if family=='radial' else 'config']
        assert ''.join(s['text'] for s in owner['annotations']['items'][-1]['kind']['Text']['text']['segments'])=='Human annotation'
        assert feedback['approval']['changes']


@pytest.mark.skipif(NEEDS_UI, reason='requires real native review input')
@pytest.mark.parametrize('family',['cartesian','radial'])
def test_native_review_long_comments_keep_approval_controls_reachable(tmp_path,family):
    from figgyplot.review import Session
    comments='\n'.join('Review note '+str(i) for i in range(40))
    with Session(tmp_path/'cache') as session:
        fig=session.figure(id='review-chart')
        if family=='radial':fig.axes[0].pie([3,2,1])
        else:fig.axes[0].plot([0,1],[1,3],id='signal')
        session.present();handle=fig._windows[-1];inputs=Inputs(handle)
        with pytest.raises(RuntimeError,match='already has'):fig.show(block=False)
        inputs.click('properties')
        if family=='cartesian':inputs.click_rect(inputs.info()['decorations']['axis_bottom'])
        props=inputs.info()['controls']['properties_viewport']
        review=inputs.info()['controls']['review_comments']
        (tmp_path/'review-property-bounds.json').write_text(json.dumps({'properties':props,'review':review}))
        assert (props[0]+props[2]<=review[0] or review[0]+review[2]<=props[0]
                or props[1]+props[3]<=review[1] or review[1]+review[3]<=props[1])
        session.comment(fig.id,'Preserve the original data',target={'series_id':'signal'})
        inputs.click('review_comments')
        import subprocess
        set_clipboard(comments)
        inputs.key('ctrl+v');inputs.pump();session.poll()
        info=inputs.info();width,height=info['surface_size']
        for key in ['review_comments','review_changes','review_accept']:
            x,y,w,h=info['controls'][key]
            assert 0<=x<x+w<=width and 0<=y<y+h<=height,(key,info['controls'][key],info['surface_size'])
        assert info['review']['comments']==comments
        inputs.click('review_changes');session.poll();assert handle.closed
        with pytest.raises(RuntimeError,match='approved|sealed'):fig.show(block=False)
        feedback=session.feedback(session.events()[0]['work_id'])['round']['documents'][fig.id]
        assert [c['text'] for c in feedback['comments']]==['Preserve the original data',comments]


@pytest.mark.skipif(NEEDS_UI, reason='requires real notebook duplicate views')
def test_review_duplicate_browser_views_require_explicit_resolution(tmp_path):
    source="from figgyplot.review import Session\nimport json\nsession=Session("+repr(str(tmp_path/'cache'))+",backend='webgpu')\nfig=session.figure(id='review-chart',retain_notebook_data=True)\nfig.axes[0].plot([0,1],[1,3],id='signal')\nw=session.widget(fig)\ndisplay(w,w)"
    with notebook(tmp_path/'duplicate-views',source,allow_closed=True,initial_views=2) as (page,execute):
        fields=page.locator('[data-review-comments]')
        fields.nth(0).fill('First view feedback');fields.nth(1).fill('Second view draft')
        page.locator('[data-review-changes]').nth(0).click()
        page.wait_for_function("Array.from(document.querySelectorAll('[data-review-status]')).some(s=>s.textContent.includes('duplicate review views'))")
        assert page.locator('.figgy-editor').count()==2
        assert fields.nth(1).input_value()=='Second view draft'
        assert json.loads(execute('print(json.dumps(session.events()))'))==[]
        assert json.loads(execute('print(json.dumps(session.snapshot()["rounds"][-1]["documents"]["review-chart"]["approval"]))')) is None
        execute('session.cancel()')


@pytest.mark.skipif(NEEDS_UI, reason='requires real native and notebook review rounds')
@pytest.mark.parametrize('backend',['native','webgpu'])
def test_review_controller_displays_a_complete_regenerated_round(tmp_path,backend):
    from figgyplot.review import Session
    source=tmp_path/'builder.py';cache=tmp_path/'cache'
    def builder(title, extra=False):
        text="def build(session):\n    fig=session.figure(id='review-round')\n    fig.axes[0].plot([0,1],[1,3],id='signal')\n    fig.axes[0].set_title("+repr(title)+")\n"
        if extra:text+="    other=session.figure(id='second-result')\n    other.axes[0].plot([0,1],[3,1],id='other')\n"
        return text
    source.write_text(builder('Initial title'))
    if backend=='native':
        with Session(cache,source={'entrypoint':str(source)}) as session:
            namespace={};exec(source.read_text(),namespace);namespace['build'](session)
            session.present();old=session._figures['review-round']._windows[-1]
            inputs=Inputs(old);inputs.click('review_comments');inputs.xdo('type','--clearmodifiers','Add the second chart');inputs.pump()
            inputs.click('review_changes');session.poll();assert old.closed
            source.write_text(builder('Updated source title',True))
            agent=Session.open(cache);work=agent.events()[0]['work_id'];assert agent.regenerate(work)==2
            session.poll();Inputs.pump()
            assert set(session._handles)=={'review-round','second-result'}
            assert all(not h.closed for h in session._handles.values())
            state=session._figures['review-round'].get_settings()
            assert ''.join(s['text'] for s in state['config']['chart_title']['text']['segments'])=='Updated source title'
            session.cancel()
        return
    initial="import asyncio,json,runpy\nfrom pathlib import Path\nfrom figgyplot.review import Session\nsession=Session("+repr(str(cache))+",source={'entrypoint':"+repr(str(source))+"},backend='webgpu')\nrunpy.run_path("+repr(str(source))+")['build'](session)\nfig=session._figures['review-round']\ndisplay(session.widget(fig))\nwatcher=asyncio.create_task(session.watch())"
    with notebook(tmp_path/'round-publication',initial,allow_closed=True) as (page,execute):
        page.locator('[data-review-comments]').fill('Add the second chart')
        click_button(page,'[data-review-changes]')
        page.wait_for_function("!document.querySelector('.figgy-editor')")
        source.write_text(builder('Updated source title',True))
        result=execute("agent=Session.open("+repr(str(cache))+"); work=agent.events()[0]['work_id']; print(await asyncio.to_thread(agent.regenerate,work))")
        assert result.strip()=='2'
        page.wait_for_function("document.querySelectorAll('.figgy-editor').length===2 && [...document.querySelectorAll('.figgy-editor [data-status]')].every(s=>s.textContent==='Ready')",timeout=180000)
        assert json.loads(execute("print(json.dumps(sorted(session._figures)))"))==['review-round','second-result']
        page.wait_for_function("[...document.querySelectorAll('.figgy-editor')].every(r=>{const d=r.figgy.diagnostics();return !d.dirty&&!d.frame_pending&&!d.busy&&!d.queued;})",polling=100,timeout=180000)
        for index in range(2):page.locator('.figgy-editor').nth(index).screenshot(path=str(tmp_path/f'complete-next-round-{index}.png'))
        execute('watcher.cancel(); session.cancel()')


@pytest.mark.skipif(NEEDS_UI, reason='requires native and real Jupyter input')
def test_layout_selects_plot_on_first_click_and_exposes_real_geometry(tmp_path):
    from PIL import ImageGrab
    with figgy.Figure(backend='native',grid=[['left','right']]) as fig:
        fig.subplots['left'].plot([0,1],[2,3],id='one')
        fig.subplots['right'].plot([0,1],[3,2],id='two')
        handle=fig.show(block=False)
        try:
            inputs=Inputs(handle);inputs.click('layout_mode')
            inputs.click_rect([*native_point(inputs.info(),(240,300)),0,0])
            assert inputs.info()['selected']=='data_area'
            assert inputs.info()['properties_open']
            assert all('plot_'+key in inputs.info()['controls'] for key in ['x','y','width','height'])
            before=fig.get_settings();inputs.click('plot_width');inputs.key('ctrl+a');inputs.xdo('type','--clearmodifiers','220');inputs.key('Return')
            assert not inputs.info()['error']
            owner=next(v for v in fig.editor_properties() if v['target']=='data_area')
            bounds=next(v['value'] for v in owner['fields'] if v['id']=='Plot area/bounds')
            assert bounds[2]==220
            assert fig.get_settings()['config']['chart_area']==before['config']['chart_area']
            # Make the inspector wider using its actual separator.
            old=inputs.info()['controls']['inspector_resize']
            drag_native(inputs,(old[0]+3,old[1]+old[3]/2),(-100,0))
            assert inputs.info()['controls']['plot_width'][0] < inputs.info()['surface_size'][0]-150
            ImageGrab.grab(xdisplay=os.environ['DISPLAY']).save(tmp_path/'native-layout-controls.png')
            assert fig.info['column_uploads']==4
        finally:handle.close();Inputs.pump()
    source="import figgyplot as fg\nfig=fg.Figure(backend='webgpu',grid=[['left','right']])\nfig.subplots['left'].plot([0,1],[2,3],id='one')\nfig.subplots['right'].plot([0,1],[3,2],id='two')\ndisplay(fig.widget())"
    with notebook(tmp_path/'browser-layout',source) as (page,execute):
        check_display_frame_ready(page)
        click_button(page,'[data-layout]')
        page.mouse.click(*browser_point(page,(240,300)))
        control=page.locator('[data-layout-component=width]');control.wait_for(state='visible')
        control.fill('220');control.press('Tab');page.evaluate(ROOT+'.flush()')
        catalog=json.loads(execute('import json;print(json.dumps(fig.editor_properties()))'))
        owner=next(o for o in catalog if o['target']=='data_area')
        assert next(f['value'] for f in owner['fields'] if f['id']=='Plot area/bounds')[2]==220
        screenshot_editor(page,tmp_path/'browser-layout-controls.png')
        assert not page.locator('.figgy-error').inner_text()


@pytest.mark.skipif(NEEDS_UI, reason='requires native and real Jupyter input')
def test_polar_wheel_does_not_modify_angular_or_radial_ranges(tmp_path):
    with figgy.Figure(backend='native') as fig:
        ax=fig.axes[0];ax.set_polar();ax.plot([0,90,180,270],[1,2,3,2])
        handle=fig.show(block=False)
        try:
            inputs=Inputs(handle);rect=inputs.info()['decorations']['data_area']
            point=(rect[0]+rect[2]/2,rect[1]+rect[3]/2)
            inputs.xdo('mousemove','--window',inputs.wid,*map(round,point));inputs.pump()
            before=fig.get_settings()
            for modifier in [None,'ctrl','shift']:
                if modifier:inputs.xdo('keydown',modifier)
                inputs.xdo('click',4);inputs.pump()
                if modifier:inputs.xdo('keyup',modifier)
                assert fig.get_settings()['config']==before['config']
            assert fig.info['column_uploads']==2
        finally:handle.close();Inputs.pump()
    source="import figgyplot as fg\nfig,ax=fg.subplots(backend='webgpu')\nax.set_polar();ax.plot([0,90,180,270],[1,2,3,2])\ndisplay(fig.widget())"
    with notebook(tmp_path/'polar-wheel',source) as (page,execute):
        check_display_frame_ready(page)
        before=page.evaluate(ROOT+'.snapshot()')
        area=page.evaluate('async()=> (await '+ROOT+'.decorations()).data_area.rect')
        page.mouse.move(*browser_surface_point(page,(area[0]+area[2]/2,area[1]+area[3]/2)))
        for modifier in [None,'Control','Shift']:
            if modifier:page.keyboard.down(modifier)
            page.mouse.wheel(0,-40)
            if modifier:page.keyboard.up(modifier)
        page.evaluate(ROOT+'.flush()')
        after=page.evaluate(ROOT+'.snapshot()')
        assert after['config']==before['config']


@pytest.mark.skipif(NEEDS_UI, reason='requires native and real Jupyter input')
def test_element_review_comments_use_selected_font_and_preserve_ssot(tmp_path):
    from figgyplot.review import Session
    from figgyplot._native import font_family_available
    from PIL import ImageGrab
    family='Noto Sans CJK KR' if font_family_available('Noto Sans CJK KR') else 'DejaVu Sans'
    text='이 주석을 오른쪽으로 이동해 주세요' if family=='Noto Sans CJK KR' else 'Move this annotation to the right'
    with Session(tmp_path/'native-cache',backend='native',review_font=family,review_font_size=17) as session:
        fig=session.figure(id='plot');fig.axes[0].plot([0,1],[2,3],id='one')
        fig.axes[0].set_title('Review title')
        fig.axes[0].text(.3,.3,'Review this element',coords='ratio',id='note')
        session.present();handle=session._handles['plot']
        inputs=Inputs(handle)
        before=fig.get_settings()
        bounds=json.loads(fig._native.bounds_json('annotation:note'))['rect']
        point=native_point(inputs.info(),(bounds[0]+bounds[2]/2,bounds[1]+bounds[3]/2))
        inputs.input_frame('mousemove','--window',inputs.wid,*map(round,point));inputs.input_frame('click',3)
        target=next(v['id'] for v in fig.editor_properties() if v['target']=='annotation:note')
        inputs.click('review_target:'+target);inputs.click('review_target_text')
        import subprocess
        set_clipboard(text)
        inputs.key('ctrl+v');inputs.pump()
        ImageGrab.grab(xdisplay=os.environ['DISPLAY']).save(tmp_path/'native-element-comment.png')
        inputs.click('review_target_save');session.poll()
        comments=session._review_state('plot')['target_comments']
        assert len(comments)==1 and comments[0]['target']==target and comments[0]['text']==text
        comment_id=comments[0]['id']
        inputs.click('review_target_list');inputs.click('review_target_edit:'+comment_id)
        inputs.click('review_target_text');inputs.key('ctrl+a')
        set_clipboard(text+'!')
        inputs.key('ctrl+v');inputs.click('review_target_save');session.poll();inputs.key('Escape')
        assert session._review_state('plot')['target_comments'][0]['id']==comment_id
        # A decoration uses its own stable target, separately from annotations.
        bounds=inputs.info()['decorations']['chart_title']
        inputs.input_frame('mousemove','--window',inputs.wid,round(bounds[0]+bounds[2]/2),round(bounds[1]+bounds[3]/2));inputs.input_frame('click',3)
        title=next(v['id'] for v in fig.editor_properties() if v['target']=='chart_title')
        inputs.click('review_target:'+title);inputs.click('review_target_text')
        inputs.xdo('type','--clearmodifiers','Clarify the title');inputs.click('review_target_save');session.poll()
        comments=session._review_state('plot')['target_comments'];assert len(comments)==2
        title_comment=next(c for c in comments if c['target']==title)
        inputs.click('review_target_list');inputs.click('review_target_delete:'+title_comment['id']);session.poll();inputs.key('Escape')
        comments=session._review_state('plot')['target_comments']
        assert len(comments)==1 and comments[0]['id']==comment_id and comments[0]['text']==text+'!'
        assert fig.get_settings()==before
        inputs.click('review_changes');session.poll()
        assert session.events()
        assert session.feedback(session.events()[0]['work_id'])['round']['documents']['plot']['comments'][0]['text']==text+'!'
        work=session.events()[0]['work_id']
        summary=session.feedback_summary(work)
        obj,=summary['figures'][0]['objects']
        assert obj['target']==target and obj['change_count']==0 and obj['comments'][0]['id']==comment_id
        detail=session.feedback_details(work,'plot',target=target)
        assert not detail['changes'] and detail['objects'][0]['snapshots']['after']
    source="import figgyplot as fg\nfrom figgyplot.review import Session\nsession=Session(backend='webgpu',review_font="+repr(family)+",review_font_size=17)\nfig=session.figure(id='plot');fig.axes[0].plot([0,1],[2,3],id='one')\nfig.axes[0].text(.3,.3,'Review this element',coords='ratio',id='note')\ndisplay(session.widget(fig))"
    with notebook(tmp_path/'browser-comments',source) as (page,execute):
        check_display_frame_ready(page)
        page.wait_for_function("document.querySelector('.figgy-editor').style.getPropertyValue('--figgy-review-font') !== ''")
        before=page.evaluate(ROOT+'.snapshot()')
        bounds=page.evaluate(ROOT+'.annotations()')[0]['rect']
        page.mouse.click(*browser_surface_point(page,(bounds[0]+bounds[2]/2,bounds[1]+bounds[3]/2)),button='right')
        menu=page.locator('[data-review-target]');menu.wait_for(state='visible');target=menu.get_attribute('data-review-target');menu.click()
        page.locator('[data-review-target-text]').fill(text)
        assert page.locator('[data-review-target-text]').evaluate('e=>getComputedStyle(e).fontSize')=='17px'
        screenshot_editor(page,tmp_path/'browser-element-comment.png')
        page.locator('[data-review-target-save]').click()
        assert json.loads(execute('import json;print(json.dumps(session._review_state("plot")["target_comments"]))'))[0]['target']==target
        click_button(page,'[data-review-target-list]');page.get_by_role('button',name='Edit',exact=True).click()
        page.locator('[data-review-target-text]').fill(text+'!');page.locator('[data-review-target-save]').click()
        # A series can be addressed directly from the object tree, even in an overlay.
        click_button(page,'[data-properties]')
        row=page.locator('[role=treeitem][data-object="one"]');row.wait_for(state='visible');row.click(button='right')
        menu=page.locator('[data-review-target]');series_target=menu.get_attribute('data-review-target');menu.click()
        assert series_target!=target
        page.locator('[data-review-target-text]').fill('Clarify this series');page.locator('[data-review-target-save]').click()
        click_button(page,'[data-review-target-list]')
        page.locator('dialog section').filter(has_text='Clarify this series').get_by_role('button',name='Delete',exact=True).click()
        page.get_by_role('button',name='Close',exact=True).last.click()
        comments=json.loads(execute('import json;print(json.dumps(session._review_state("plot")["target_comments"]))'))
        assert len(comments)==1 and comments[0]['target']==target and comments[0]['text']==text+'!'
        assert page.evaluate(ROOT+'.snapshot()')==before
        assert not page.locator('[data-review-status]').inner_text().startswith('Review font could not')
        assert page.evaluate("document.fonts.status")=='loaded'
        assert not page.locator('.figgy-error').inner_text()


@pytest.mark.skipif(NEEDS_UI, reason='requires native and real Jupyter input')
def test_review_connect_and_finish_buttons_use_a_terminal_lifecycle_signal(tmp_path,monkeypatch):
    from figgyplot.review import Session
    with Session(tmp_path/'native-connect',backend='native') as session:
        fig=session.figure(id='plot');fig.axes[0].plot([0,1],[2,3],id='signal')
        session.start();before=fig.get_settings();session._set_comment_text('plot','저장 후 종료')
        poll=session.poll;clicked=False
        def automate_review():
            nonlocal clicked
            poll()
            if not clicked:
                inputs=Inputs(session._handles['plot'])
                inputs.click('review_finish');clicked=True
                poll()
        monkeypatch.setattr(session,'poll',automate_review)
        event=session.connect(timeout=10)
        assert clicked and event['intent']=='finish'
        assert session.snapshot()['rounds'][-1]['documents']['plot']['approval']['settings']==before
        assert session.finish(event['work_id'])==1
        assert session.status['state']=='completed'
        assert not session._handles
    source="import json\nfrom figgyplot.review import Session\nsession=Session(backend='webgpu')\nfig=session.figure(id='plot');fig.axes[0].plot([0,1],[2,3],id='signal')\ndisplay(session.widget(fig))"
    with notebook(tmp_path/'browser-finish',source,allow_closed=True) as (page,execute):
        check_display_frame_ready(page)
        before=page.evaluate(ROOT+'.snapshot()')
        page.locator('[data-review-comments]').fill('저장 후 종료')
        click_button(page,'[data-review-finish]')
        page.wait_for_function("!document.querySelector('.figgy-editor')")
        event=json.loads(execute('print(json.dumps(session.events()[0]))'))
        assert event['intent']=='finish'
        approved=json.loads(execute('print(json.dumps(session.snapshot()["rounds"][-1]["documents"]["plot"]["approval"]["settings"]))'))
        assert approved==before
        assert execute('print(session.finish(session.events()[0]["work_id"]))').strip()=='1'
        assert json.loads(execute('print(json.dumps(session.status))'))['state']=='completed'


@pytest.mark.skipif(NEEDS_UI, reason='requires native and real Jupyter input')
@pytest.mark.parametrize('annotation',['arrow','text'])
def test_annotation_drag_reuses_inspector_descriptions_until_release(tmp_path, monkeypatch, annotation):
    from time import perf_counter
    measurement={}
    monkeypatch.setenv('FIGGY_PROFILE_HOST','1')
    def assert_only_arrow_coordinates_changed(host,before,after):
        (tmp_path/f'{host}-drag-ssot.json').write_text(json.dumps(dict(before=before,after=after),indent=2))
        old=json.loads(json.dumps(before));new=json.loads(json.dumps(after))
        kind='Arrow' if annotation=='arrow' else 'Text'
        a=old['config']['annotations']['items'][0]['kind'][kind]
        b=new['config']['annotations']['items'][0]['kind'][kind]
        keys=('from','to') if annotation=='arrow' else ('anchor',)
        for key in keys:
            assert a[key]!=b[key]
            for axis in ('x','y'):
                assert b[key]['Ratio'][axis]>a[key]['Ratio'][axis]
            b[key]=a[key]
        assert new==old
    with figgy.Figure(backend='native') as fig:
        fig.axes[0].plot([0,1],[2,3],id='one')
        if annotation=='arrow':fig.axes[0].arrow(.2,.2,.3,.2,coords='ratio',id='arrow')
        else:fig.axes[0].text(.2,.2,'Move this text',coords='ratio',id='arrow')
        fig.axes[0].text(.7,.7,'Keep this annotation',coords='ratio',id='fixed')
        handle=fig.show(block=False)
        try:
            inputs=Inputs(handle);inputs.click('properties')
            rect=json.loads(fig._native.bounds_json('annotation:arrow'))['rect']
            start=native_point(inputs.info(),(rect[0]+rect[2]/2,rect[1]+rect[3]/2))
            inputs.click_rect([*start,0,0]);before=inputs.info()['property_catalog_builds'];old=fig.get_settings();uploads=fig.info['column_uploads']
            if annotation=='text':time.sleep(.5)  # This gesture is a drag, not double-click text editing.
            inputs.input_frame('mousemove','--window',inputs.wid,*map(round,start));inputs.input_frame('mousedown',1)
            work_before=fig.info['host_work']
            begin=perf_counter()
            for step in range(1,7):inputs.input_frame('mousemove','--window',inputs.wid,round(start[0]+step*3),round(start[1]+step*2))
            during=inputs.info()['property_catalog_builds'];inputs.input_frame('mouseup',1)
            work_after=fig.info['host_work']
            for stage in ('annotation_view','native_axis_refresh','native_styles'):
                assert work_after.get(stage,{}).get('count',0)==work_before.get(stage,{}).get('count',0), (stage,work_before,work_after)
            assert work_after['native_annotation_refresh']['count']>work_before.get('native_annotation_refresh',{}).get('count',0)
            measurement['native']=dict(moves=6,inspector_rebuilds_during=during-before,elapsed=perf_counter()-begin,last_input_to_submit_ms=inputs.info()['last_input_to_submit_ms'])
            assert during-before<=1
            assert_only_arrow_coordinates_changed('native',old,fig.get_settings())
            assert fig.info['column_uploads']==uploads
        finally:handle.close();Inputs.pump()
    item="ax.arrow(.2,.2,.3,.2,coords='ratio',id='arrow')" if annotation=='arrow' else "ax.text(.2,.2,'Move this text',coords='ratio',id='arrow')"
    source="import figgyplot as fg\nfig,ax=fg.subplots(backend='webgpu')\nax.plot([0,1],[2,3],id='one');"+item+"\nax.text(.7,.7,'Keep this annotation',coords='ratio',id='fixed')\ndisplay(fig.widget())"
    with notebook(tmp_path/'browser-drag',source) as (page,execute):
        check_display_frame_ready(page)
        click_button(page,'[data-properties]')
        rect=page.evaluate(ROOT+'.annotations()')[0]['rect']
        start=browser_surface_point(page,(rect[0]+rect[2]/2,rect[1]+rect[3]/2))
        page.mouse.click(*start);page.evaluate(ROOT+'.flush()')
        if annotation=='text':time.sleep(.5)
        before=page.evaluate(ROOT+'.stats.inspector_rebuilds')
        old=page.evaluate(ROOT+'.snapshot()');uploads=page.evaluate(ROOT+'.stats.column_uploads')
        begin=perf_counter();page.mouse.move(*start);page.mouse.down()
        page.mouse.move(start[0]+24,start[1]+16,steps=8)
        during=page.evaluate(ROOT+'.stats.inspector_rebuilds')
        page.mouse.up();page.evaluate(ROOT+'.flush()')
        measurement['browser']=dict(moves=8,inspector_rebuilds_during=during-before,elapsed=perf_counter()-begin)
        assert during-before<=1
        assert_only_arrow_coordinates_changed('browser',old,page.evaluate(ROOT+'.snapshot()'))
        assert page.evaluate(ROOT+'.stats.column_uploads')==uploads
        assert not page.locator('.figgy-error').inner_text()
    (tmp_path/'wrapper-drag-measurement.json').write_text(json.dumps(measurement,indent=2))


@pytest.mark.skipif(NEEDS_UI, reason='requires actual native review and clipboard input')
@pytest.mark.parametrize('kind',['line','radial'])
def test_native_review_images_paste_preview_remove_and_targeted_submission(tmp_path,kind):
    from PIL import Image, ImageGrab
    from figgyplot.review import Session
    from figgyplot._review_diff import persistent
    from figgyplot._native import font_family_available
    image=tmp_path/'reference.png';Image.new('RGB',(96,64),'#E69F00').save(image)
    family='Noto Sans CJK KR' if font_family_available('Noto Sans CJK KR') else 'DejaVu Sans'
    with Session(tmp_path/'cache',backend='native',review_font=family) as session:
        fig=session.figure(id='plot');ax=fig.axes[0]
        if kind=='radial':ax.donut([3,2,1],labels=['A','B','C'])
        else:ax.plot([0,1],[2,3],id='signal')
        ax.set_title('Image review')
        session.present();inputs=Inputs(session._handles['plot']);before=fig.get_settings()
        def clipboard_image():
            subprocess.run(['xclip','-selection','clipboard','-t','image/png','-i',str(image)],check=True,
                           stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10)
        clipboard_image();inputs.click('review_comments');inputs.key('ctrl+v');session.poll()
        ref,=session._review_state('plot')['attachments']
        assert 'data' not in inputs.info()['review']['attachments'][0]
        inputs.click('review_image:'+ref['id']);inputs.key('Escape')
        inputs.click('review_image_remove:'+ref['id']);session.poll()
        assert not session._review_state('plot')['attachments']
        inputs.click('review_paste');session.poll()
        assert len(session._review_state('plot')['attachments'])==1
        bounds=inputs.info()['decorations']['chart_title']
        if kind=='radial':
            # Bounded-host decoration stats are document pixels; Cartesian
            # decorations are already in surface coordinates.
            panel=inputs.info()['chart_panel'];area=before['config']['chart_area']
            bounds=[panel[0]+bounds[0]*panel[2]/area['width'],panel[1]+bounds[1]*panel[3]/area['height'],bounds[2]*panel[2]/area['width'],bounds[3]*panel[3]/area['height']]
        inputs.input_frame('mousemove','--window',inputs.wid,round(bounds[0]+bounds[2]/2),round(bounds[1]+bounds[3]/2));inputs.input_frame('click',3)
        target='bounded/chart_title' if kind=='radial' else 'panel/main/chart_title'
        inputs.click('review_target:'+target);inputs.click('review_target_text');inputs.key('ctrl+v')
        assert any(k.startswith('review_target_image:') for k in inputs.info()['controls'])
        inputs.click('review_target_save');session.poll()
        target_comment,=session._review_state('plot')['target_comments'];assert not target_comment['text']
        assert len(target_comment['attachments'])==1
        inputs.click('review_target_list');inputs.click('review_target_edit:'+target_comment['id'])
        inputs.click('review_target_image_remove:'+ref['id']);inputs.click('review_target_paste')
        inputs.click('review_target_save');session.poll();inputs.key('Escape')
        set_clipboard('Keep the palette');inputs.click('review_comments');inputs.key('ctrl+v');session.poll()
        assert session._review_state('plot')['comments']=='Keep the palette'
        assert persistent(fig.get_settings())==persistent(before)
        ImageGrab.grab(xdisplay=os.environ['DISPLAY']).save(tmp_path/'review-images.png')
        inputs.click('review_changes');session.poll()
        small=session.feedback_summary(session.events()[0]['work_id'])
        figure,=small['figures'];obj,=figure['objects']
        assert obj['target']==target and obj['change_count']==0
        assert figure['comments'][0]['attachments'][0]['path']==obj['comments'][0]['attachments'][0]['path']
        assert os.path.isfile(obj['comments'][0]['attachments'][0]['path'])
    Inputs.pump()


@pytest.mark.skipif(NEEDS_UI, reason='requires real notebook WebGPU and clipboard input')
def test_browser_review_images_upload_clipboard_preview_and_targeted_submission(tmp_path):
    from PIL import Image
    orange=tmp_path/'reference.png';green=tmp_path/'clipboard.png'
    Image.new('RGB',(96,64),'#E69F00').save(orange);Image.new('RGB',(96,64),'#009E73').save(green)
    cache=tmp_path/'cache'
    source=("from figgyplot.review import Session\n"
            f"session=Session({str(cache)!r},backend='webgpu')\n"
            "fig=session.figure(id='plot');ax=fig.axes[0]\n"
            "ax.plot([0,1],[2,3],id='signal');ax.text(.3,.3,'Review me',coords='ratio',id='note')\n"
            "display(session.widget(fig))")
    with notebook(tmp_path/'browser-images',source,allow_closed=True) as (page,execute):
        check_display_frame_ready(page);before=page.evaluate(ROOT+'.snapshot()')
        general=page.locator('.figgy-review')
        general.locator('input[type=file]').set_input_files(orange)
        general.locator('[data-review-image]').wait_for()
        page.evaluate("""async encoded=>{const bytes=Uint8Array.from(atob(encoded),c=>c.charCodeAt(0));await navigator.clipboard.write([new ClipboardItem({'image/png':new Blob([bytes],{type:'image/png'})})]);}""",base64.b64encode(green.read_bytes()).decode())
        general.locator('[data-review-comments]').click();page.keyboard.press('Control+V')
        page.wait_for_function("document.querySelectorAll('.figgy-review [data-review-image]').length===2")
        general.locator('[data-review-image]').first.click()
        page.wait_for_function("document.querySelector('.figgy-review-image-preview img')?.naturalWidth===96")
        page.locator('.figgy-review-image-preview button').click()
        general.locator('[data-review-image-remove]').first.click()
        assert general.locator('[data-review-image]').count()==1
        general.locator('[data-review-comments]').fill('Keep the palette')
        # Editing the review field scrolls a tall notebook output to its bottom.
        # Bring the chart into view before deriving a viewport pointer position.
        page.locator('.figgy-editor canvas').scroll_into_view_if_needed()
        bounds=page.evaluate(ROOT+'.annotations()')[0]['rect']
        page.mouse.click(*browser_surface_point(page,(bounds[0]+bounds[2]/2,bounds[1]+bounds[3]/2)),button='right')
        page.locator('[data-review-target]').click()
        dialog=page.locator('.figgy-review-dialog')
        assert page.locator('.lm-Menu:visible').count()==0
        dialog.locator('input[type=file]').set_input_files(orange)
        dialog.locator('[data-review-target-image]').wait_for()
        dialog.locator('[data-review-target-save]').click()
        assert page.evaluate(ROOT+'.snapshot()')==before
        screenshot_editor(page,tmp_path/'browser-review-images.png')
        general.locator('[data-review-changes]').click()
        output=execute("import time,json\nfor _ in range(100):\n    if session.events():break\n    time.sleep(.01)\nprint(json.dumps(session.feedback_summary(session.events()[0]['work_id'])))")
        summary=json.loads(output.strip());figure,=summary['figures'];obj,=figure['objects']
        assert obj['target']=='panel/main/annotation/note' and obj['change_count']==0
        assert not obj['comments'][0]['text']
        a=figure['comments'][0]['attachments'][0];b=obj['comments'][0]['attachments'][0]
        assert a['sha256']!=b['sha256'] and os.path.isfile(a['path']) and os.path.isfile(b['path'])


@pytest.mark.skipif(NEEDS_UI, reason='requires native and real Jupyter input')
def test_style_api_composition_renders_consistent_grid_and_colorbar_in_both_hosts(tmp_path):
    from PIL import Image
    source = '''import figgyplot as fg
fg.use_style('dashboard.operations')
template=fg.Figure(backend=BACKEND)
template.set_layout([['left','right']],gap=44,column_weights=[2,1])
style=template.extract_style();template.close()
fig=fg.Figure(backend=BACKEND,style=style,grid=[['left','right']])
fg.use_style(None)
fig.subplots['left'].plot([0,1],[1,2],color='#64c6ef',id='left-line')
right=fig.subplots['right'].axes
right.scatter([0,1],[1,2],c=[0,1],id='right-points')
state=fig.get_settings()
bar=state['config']['subplots'][0]['config']['colorbar']
bar['gap_px']=17;bar['axis']['label_style']['font_size']=16
fig.apply_settings(state)
right.imshow([[1,2],[3,4]],cmap='magma',id='field')
fig.subplots['left'].set_title('Measured')
right.set_title('Mapped values')
'''
    def check(state):
        layout=state['identity']['layout'];width,height=layout['size']
        first=round((width-44)*2/3);start=round((width-44)*2/3+44)
        assert layout['gap']==44 and layout['column_weights']==[2,1]
        assert state['config']['chart_area']==dict(x=0,y=0,width=first,height=height)
        panel=state['config']['subplots'][0]['config']
        assert panel['chart_area']==dict(x=start,y=0,width=width-start,height=height)
        assert panel['colorbar']['gap_px']==17
        assert panel['colorbar']['axis']['label_style']['font_size']==16
        assert panel['colorbar']['colormap']=='Magma'
        assert [s['series_id'] for s in state['series']]==['left-line','right-points','field']
    def check_pixels(image):
        rgb=np.asarray(image.convert('RGB')).astype(int)
        boundary=round(rgb.shape[1]*.65)
        left=rgb[:,:boundary];right=rgb[:,boundary:]
        # These are authored scene colors, independent of the SSOT serializer
        # and host Ready flag. A blank/black presented canvas must fail.
        cyan=np.all(np.abs(left-[100,198,239])<=5,axis=2)
        yellow=(right[:,:,0]>220)&(right[:,:,1]>150)&(right[:,:,2]<220)&(right[:,:,0]-right[:,:,2]>25)
        assert cyan.sum()>50,'The displayed left-panel signal is missing'
        assert yellow.sum()>100,'The displayed right-panel scalar field is missing'
    namespace={};exec(source.replace('BACKEND',repr('native')),namespace)
    fig=namespace['fig']
    try:
        check(fig.get_settings());fig.savefig(tmp_path/'native-style-composition.png')
        with Image.open(tmp_path/'native-style-composition.png') as image:check_pixels(image)
        handle=fig.show(block=False)
        try:
            inputs=Inputs(handle);inputs.pump()
            assert inputs.info()['chart_panel'][2]>0
            assert fig.info['column_uploads']==9
        finally:handle.close();Inputs.pump()
    finally:fig.close()
    with notebook(tmp_path/'browser-style-composition',source.replace('BACKEND',repr('webgpu'))+'\ndisplay(fig.widget())') as (page,execute):
        check_display_frame_ready(page)
        check(json.loads(execute('import json;print(json.dumps(fig.get_settings()))')))
        assert json.loads(execute("print(json.dumps(fig.info['columns']))"))==9
        screenshot_editor(page,tmp_path/'browser-style-composition.png')
        canvas=page.locator('.figgy-editor canvas')
        canvas.screenshot(path=str(tmp_path/'browser-style-canvas.png'))
        with Image.open(tmp_path/'browser-style-canvas.png') as image:check_pixels(image)
        assert not page.locator('.figgy-error').inner_text()


@pytest.mark.skipif(NEEDS_UI, reason='requires native and real Jupyter wheel input')
@pytest.mark.parametrize('backend', ['native', 'webgpu'])
@pytest.mark.parametrize('mode', ['api', 'exact'])
@pytest.mark.parametrize('fixed', [False, True])
def test_export_replay_preserves_future_wheel_tick_behavior(tmp_path, backend, mode, fixed):
    """Equal pre-gesture SSOT must retain the user's auto/fixed tick behavior."""
    setup = f'''
import figgyplot as fg
from figgyplot.ticker import MultipleLocator
fig = fg.Figure(backend={backend!r})
ax = fig.axes[0]
ax.plot([0, 1000], [1, 4], id='signal')
ax.set_xlim(0, 1000)
ax.set_ylim(0, 5)
fig.apply_style('report')
if {fixed!r}: ax.xaxis.set_major_locator(MultipleLocator(200))
before = fig.get_settings()
exec(fig.to_code(mode={mode!r}), {{'fig': fig}})
assert fig.get_settings() == before
'''
    def check(before, after):
        a, b = before['config']['bottom_x'], after['config']['bottom_x']
        assert b['max']-b['min'] < (a['max']-a['min'])/2
        if fixed:
            assert b['major_spacing'] == a['major_spacing']
        else:
            assert b['major_spacing'] < a['major_spacing']
        assert after['identity'].get('tick_modes') == before['identity'].get('tick_modes')
        assert after['series'] == before['series']
        (tmp_path/'wheel-before-after.json').write_text(json.dumps(dict(before=before, after=after), indent=2))
    if backend == 'native':
        scope = {}; exec(setup, scope); fig = scope['fig']
        with fig:
            handle = fig.show(block=False)
            try:
                inputs = Inputs(handle); before = fig.get_settings(); uploads = fig.info['column_uploads']
                x, y, w, h = inputs.info()['decorations']['data_area']
                inputs.xdo('mousemove', '--window', inputs.wid, round(x+w/2), round(y+h/2)); inputs.pump()
                inputs.xdo('keydown', 'ctrl')
                try:
                    inputs.xdo('click', '--repeat', 8, '--delay', 20, 4)
                finally:
                    inputs.xdo('keyup', 'ctrl')
                inputs.pump()
                check(before, fig.get_settings())
                assert fig.info['column_uploads'] == uploads
                assert not inputs.info()['error']
            finally:
                handle.close(); Inputs.pump()
    else:
        with notebook(tmp_path/'notebook', setup+'\ndisplay(fig.widget())') as (page, execute):
            before = page.evaluate(ROOT+'.snapshot()')
            uploads = page.evaluate(ROOT+'.stats.column_uploads')
            upload_bytes = page.evaluate(ROOT+'.stats.binary_upload_bytes')
            rect = page.evaluate(ROOT+'.decorations()')['data_area']['rect']
            x, y = browser_point(page, (rect[0]+rect[2]/2, rect[1]+rect[3]/2))
            page.mouse.move(x, y); page.keyboard.down('Control')
            try:
                page.mouse.wheel(0, -640)
            finally:
                page.keyboard.up('Control')
            page.wait_for_function(
                f"() => {{ const a={ROOT}.snapshot().config.bottom_x; return a.max-a.min < {(before['config']['bottom_x']['max']-before['config']['bottom_x']['min'])/2!r}; }}"
            )
            page.evaluate(ROOT+'.flush()')
            after = page.evaluate(ROOT+'.snapshot()')
            check(before, after)
            execute('await fig.sync()')
            assert page.evaluate(ROOT+'.stats.column_uploads') == uploads
            assert page.evaluate(ROOT+'.stats.binary_upload_bytes') == upload_bytes
            assert not page.locator('.figgy-error').inner_text()


@pytest.mark.skipif(NEEDS_UI, reason='requires actual native and notebook label geometry')
@pytest.mark.parametrize('backend', ['native', 'webgpu'])
def test_colorbar_requested_label_is_visible_and_separate_in_both_hosts(tmp_path, backend):
    setup = f'''
import figgyplot as fg
fig = fg.Figure(backend={backend!r})
points = fig.axes[0].scatter([1,2],[3,4],c=[10,20])
bar = fig.colorbar(points, label='Temperature (K)')
bar.ax.yaxis.label.set_fontsize(18)
bar.ax.tick_params(labelsize=12)
'''
    def check(title, ticks):
        assert title[2] > 0 and title[3] > 0
        assert ticks[2] > 0 and ticks[3] > 0
        assert title[0] > ticks[0]+ticks[2]
    if backend == 'native':
        scope = {}; exec(setup, scope); fig = scope['fig']
        with fig:
            handle = fig.show(block=False)
            try:
                inputs = Inputs(handle); decorations = inputs.info()['decorations']
                assert scope['bar'].ax.yaxis.label.get_visible()
                check(decorations['colorbar_title'], decorations['colorbar_tick_labels'])
                assert not inputs.info()['error']
            finally:
                handle.close(); Inputs.pump()
    else:
        with notebook(tmp_path/'colorbar', setup+'\ndisplay(fig.widget())') as (page, execute):
            decorations = page.evaluate(ROOT+'.decorations()')
            assert page.evaluate(ROOT+'.snapshot().config.colorbar.axis.title_option.visible')
            check(decorations['colorbar_title']['rect'], decorations['colorbar_tick_labels']['rect'])
            assert not page.locator('.figgy-error').inner_text()

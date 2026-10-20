from object_navigation import ObjectNavigator
"""Same input scenarios must work on native surfaces and real notebook WebGPU."""
import json
import os
import shutil
import time
import numpy as np
import pytest
import figgyplot as figgy
from test_radial_desktop import Inputs
from jupyter_harness import notebook, button_point_without_frames

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
        assert current['renderer_version'] == '0.18.0'
        assert current['config']['legend']['content'] != before['config']['legend']['content']
        assert 'Temperature' in ''.join(s['text'] for s in current['config']['legend']['content']['segments'])
        revision = figure.revision
        figure.apply_settings(current)
        assert figure.revision == revision

NEEDS_UI = not os.environ.get('DISPLAY') or not all(shutil.which(p) for p in ['xdotool','xclip','wmctrl']) or os.environ.get('FIGGY_TEST_JUPYTER') != '1'

if os.environ.get('FIGGY_REQUIRE_INTERACTION_PARITY') == '1' and NEEDS_UI:
    raise RuntimeError('Required interaction parity cannot be skipped: install X11 tools, set DISPLAY and FIGGY_TEST_JUPYTER=1')


def offset(chart, target):
    return next((v['offset'] for v in chart['decorations']['offsets'] if v['element'] == target), [0, 0])


def drag_native(inputs, start, delta):
    for args in [('mousemove','--window',inputs.wid,*map(round,start)),('mousedown',1),
                 ('mousemove','--window',inputs.wid,*map(round,(start[0]+delta[0],start[1]+delta[1]))),('mouseup',1)]:
        inputs.xdo(*args)
        inputs.pump()


def native_point(info, logical):
    p=info['chart_panel']
    return p[0]+logical[0]*p[2]/960, p[1]+logical[1]*p[3]/600


def browser_point(page, logical):
    r=page.locator('.figgy-editor canvas').bounding_box()
    return r['x']+logical[0]*r['width']/960, r['y']+logical[1]*r['height']/600


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
        page.locator('button[data-visibility]').click();page.evaluate(ROOT+'.flush()')
    page.locator('[data-close-properties]').click()
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
        page.locator('[data-layout]').click()
        box=page.evaluate("async()=> (await "+ROOT+".decorations()).find(v=>v.id==='data_area').rect")
        page.mouse.click(*browser_point(page,(box[0]+box[2]/2,box[1]+box[3]/2)))
        if panel.is_visible():page.locator('[data-close-properties]').click()
        handles=page.evaluate("async()=> (await "+ROOT+".decorations()).find(v=>v.id==='data_area').handles")
        h=max(handles,key=lambda r:r[0]+r[1]);pos=(h[0]+h[2]/2,h[1]+h[3]/2)
        click_at=browser_point(page,pos)
        (tmp_path/'resize-before.json').write_text(json.dumps({'logical':pos,'screen':click_at,'handles':handles,'state':page.evaluate(ROOT+'.snapshot()'),'element':page.evaluate('(p)=>document.elementFromPoint(...p)?.outerHTML.slice(0,500)',click_at)}))
        assert page.evaluate('(p)=>document.elementFromPoint(...p)?.tagName',click_at)=='CANVAS'
        page.mouse.move(*click_at);page.mouse.down();page.mouse.move(*browser_point(page,(pos[0]-16,pos[1]-12)),steps=5);page.mouse.up()
        execute('await fig.sync()')
        state=json.loads(execute('print(json.dumps(fig.get_settings()))'))
        assert state[kind]['decorations']['data_area'] == pytest.approx(native_area,abs=1.2), page.locator('.figgy-error').inner_text()
        page.locator('[data-fit]').click();page.locator('[data-select]').click();page.evaluate(ROOT+'.flush()')
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
def test_browser_coalesces_input_while_ordinary_frame_is_pending(tmp_path):
    """Slow GPU completion must not build a frame backlog ahead of PNG export."""
    source="import json\nimport figgyplot as figgy\nfig,ax=figgy.subplots(backend='webgpu')\nax.bar(['A','B'],[3,5])\nax.set_title('Frame backpressure')\ndisplay(fig.widget())"
    with notebook(tmp_path/'frame-backpressure', source) as (page,execute):
        page.locator('[data-properties]').click()
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
            # match the dropdown immediately, even while renderer work is held.
            target=ObjectNavigator(page)
            series_id=page.evaluate(ROOT+'.snapshot().categorical.series[0].id')
            target.choose(series_id)
            assert page.locator('[data-property=label]').count() == 1
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
            assert offset(accepted['categorical'],'ChartTitle') == pytest.approx([13,6],abs=.2)
            assert target.selected() == series_id
        finally:
            page.evaluate('window.figgyFrameGate.release()')
        page.wait_for_function('before=>window.figgyGPUWork.submitted>before',arg=submitted,polling=100)
        execute('await fig.sync()')
        state=json.loads(execute('print(json.dumps(fig.get_settings()))'))
        assert offset(state['categorical'],'ChartTitle') == pytest.approx([13,6],abs=.2), target.selected()
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
        page.locator('[data-properties]').click()
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
        page.locator('button[data-visibility]').click();page.locator('[data-visibility="Chart title"]').uncheck()
        assert not config()['chart_title']['visible']
        page.locator('[data-style]').click();page.locator('[data-style-mode=sketch]').click()
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
        page.locator('[data-properties]').click();ObjectNavigator(page).choose('axis_bottom')
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
        page.locator('[data-fit]').click();execute('await fig.sync()')
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
        page.locator('[data-properties]').click()
        # Saved 0.17 settings must also pass the browser's local installer,
        # before any kernel round trip can normalize the renderer stamp.
        legacy = page.evaluate(ROOT+'.snapshot()')
        legacy['renderer_version'] = '0.17.0'
        legacy['config']['chart_title']['offset_x'] = 7
        page.locator('[data-advanced]').evaluate('element=>element.open=true')
        page.locator('[data-settings]').fill(json.dumps(legacy))
        page.locator('[data-apply]').click()
        page.wait_for_function(ROOT+'.snapshot().config.chart_title.offset_x===7')
        assert page.evaluate(ROOT+'.snapshot().renderer_version') == '0.18.0'
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
        page.locator('[data-properties]').click()
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
        page.locator('[data-properties]').click()
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
            page.locator('button[data-visibility]').click()
            toggle=page.locator(f'input[data-visibility="{label}"]')
            assert not toggle.is_checked()
            toggle.check();page.evaluate(ROOT+'.flush()')
            page.locator('button[data-visibility]').click()
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
            page.locator('button[data-visibility]').click();toggle.uncheck();page.evaluate(ROOT+'.flush()')
            assert not title(page.evaluate(ROOT+'.snapshot()'),axis)['visible']
            toggle.check();page.evaluate(ROOT+'.flush()')
            assert title(page.evaluate(ROOT+'.snapshot()'),axis)['text']==rich
            page.locator('button[data-visibility]').click()
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
    def check_edit(get_state, edit, source, field, value, linked=True):
        before=get_state()['config']
        edit(targets[source],field,value)
        after=get_state()['config']
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
        finally: handle.close();Inputs.pump()
    source="import json\nimport figgyplot as figgy\nfig,ax=figgy.subplots(backend='webgpu')\n"+setup+"display(fig.widget())"
    with notebook(tmp_path/('paired_'+dimension),source) as (page,execute):
        page.locator('[data-properties]').click()
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
        page.locator('[data-copy]').click();page.evaluate(ROOT+'.flush()')
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
        page.locator('[data-properties]').click()
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
            page.locator('[data-close-properties]').click()
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
def test_object_tree_routes_secondary_axes_and_reveals_canvas_selection(tmp_path):
    setup = "fig.set_layout([['left','right']]); ax=fig.subplots['left'].axes; ax.plot([0,1,2],[1,2,1],label='Signal',id='signal'); ax.set_title('Overview'); right=fig.subplots['right'].axes; right.plot([0,1,2],[3,1,2],id='other'); right.set_title('Measurements'); twin=right.twinx(id='pressure_axis'); twin.plot([0,1,2],[100,200,150],label='Pressure readings',id='pressure'); ax.activate()"
    with figgy.Figure(backend='native') as fig:
        exec(setup, {'fig': fig})
        handle=fig.show(block=False)
        try:
            inputs=Inputs(handle);inputs.click('properties')
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
            target=inputs.info()['decorations'].get('chart_title')
            if target:
                inputs.click_rect(target)
                assert fig.get_settings()['config']['active_layer']=='Base'
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
        page.locator('[data-properties]').click()
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
            assert after['value_range'] is not None
            assert after['series']==before['series']
            panel_before=inputs.info()['chart_panel']
            inputs.click('properties');assert 'range_min' in inputs.info()['controls']
            assert inputs.info()['chart_panel']==panel_before
            inputs.click('fit');assert fig.get_settings()[kind]['value_range'] is None
            assert fig.info['rgba_readbacks']==fig.info['png_encodes']==0
        finally:handle.close();Inputs.pump()
    source="import json\nimport figgyplot as figgy\nfig,ax=figgy.subplots(backend='webgpu')\n"+setup+"\ndisplay(fig.widget())"
    with notebook(tmp_path/family,source) as (page,execute):
        original=page.evaluate(ROOT+'.snapshot()')[kind]
        area=page.evaluate('async()=> (await '+ROOT+'.decorations()).find(v=>v.id==="data_area").rect')
        page.mouse.move(*browser_point(page,(area[0]+area[2]/2,area[1]+area[3]/2)));page.mouse.wheel(0,-40)
        page.wait_for_function(ROOT+f'.snapshot().{kind}.value_range !== null')
        page.evaluate(ROOT+'.flush()')
        state=page.evaluate(ROOT+'.snapshot()')[kind]
        assert state['series']==original['series']
        page.locator('[data-properties]').click();minimum=page.locator('[data-property=range_min]');assert minimum.is_visible()
        page.locator('[data-fit]').click();page.evaluate(ROOT+'.flush()')
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
        try:
            inputs=Inputs(handle);inputs.click('draw');revision=fig.revision
            inputs.click('layout_mode');inputs.click('draw_arrow')
            assert not inputs.info()['layout_mode'] and inputs.info()['drawing_tool']=='arrow'
            start=native_point(inputs.info(),(330,240));end=native_point(inputs.info(),(490,340))
            inputs.xdo('mousemove','--window',inputs.wid,*map(round,start));inputs.pump();inputs.xdo('mousedown',1);inputs.pump()
            inputs.xdo('mousemove','--window',inputs.wid,*map(round,end));inputs.pump()
            assert fig.revision==revision and not items(fig.get_settings())
            inputs.key('Escape');inputs.xdo('mouseup',1);inputs.pump()
            assert not items(fig.get_settings())
            # The existing bounded hover route may resume after cancellation.
            if kind is None:assert fig.revision==revision
            inputs.click('draw_text');revision=fig.revision;point=native_point(inputs.info(),(330,240))
            inputs.click_rect([point[0]-1,point[1]-1,2,2]);assert len(items(fig.get_settings()))==1
            assert inputs.info()['properties_open']
            if kind is None:
                assert fig.revision==revision+1
                selection=inputs.info()['annotation_selection'];assert selection['index']==0
                text_width=selection['rect'][2]
            inputs.click('annotation_text');inputs.key('ctrl+a');inputs.xdo('type','--clearmodifiers','Review this region');inputs.pump()
            assert ''.join(v['text'] for v in items(fig.get_settings())[0]['kind']['Text']['text']['segments'])=='Review this region'
            if kind is None:
                selection=inputs.info()['annotation_selection'];assert selection['index']==0
                assert selection['rect'][2]>text_width*2
            if any(axes):
                revision=fig.revision;inputs.click('draw_data_anchor');assert fig.revision==revision
            for tool in tools:
                inputs.click('draw_'+tool)
                start=native_point(inputs.info(),(340,260));end=native_point(inputs.info(),(510,360))
                count=len(items(fig.get_settings()));drag_native(inputs,start,(end[0]-start[0],end[1]-start[1]))
                assert len(items(fig.get_settings()))==count+1, inputs.info()['error']
                if tool=='arrow':
                    assert ('Data' if any(axes) else 'Ratio') in items(fig.get_settings())[-1]['kind']['Arrow']['from']
                    assert 'head_length' in inputs.info()['controls']
            saved=fig.get_settings();ids=[i['id'] for i in items(saved)];assert len(ids)==len(set(ids))
            assert owner(saved)['active_layer']=='Annotations'
            inputs.click('delete_annotation');assert len(items(fig.get_settings()))==len(ids)-1
            assert not inputs.info()['error']
            assert fig.info['rgba_readbacks']==fig.info['png_encodes']==0
        finally:handle.close();Inputs.pump()
    source="import json\nimport figgyplot as figgy\nfig,ax=figgy.subplots(backend='webgpu')\n"+setup+"\ndisplay(fig.widget())"
    with notebook(tmp_path/family,source) as (page,execute):
        page.locator('[data-draw]').click()
        for name,allowed in [('vline',axes[0]),('vspan',axes[0]),('hline',axes[1]),('hspan',axes[1])]:
            assert page.locator(f'[data-tool={name}]').is_enabled()==allowed
        page.locator('[data-layout]').click();page.locator('[data-tool=arrow]').click()
        assert page.locator('[data-layout]').get_attribute('aria-pressed')=='false'
        assert page.locator('[data-select]').get_attribute('aria-pressed')=='false'
        r=page.locator('canvas').bounding_box()
        page.mouse.move(r['x']+r['width']*.35,r['y']+r['height']*.4);page.mouse.down();page.mouse.move(r['x']+r['width']*.55,r['y']+r['height']*.6)
        page.wait_for_function("document.querySelector('.figgy-drawing-preview').childElementCount>0")
        assert not items(page.evaluate(ROOT+'.snapshot()'))
        page.keyboard.press('Escape');page.mouse.up();assert not items(page.evaluate(ROOT+'.snapshot()'))
        page.locator('[data-tool=text]').click();r=page.locator('canvas').bounding_box();page.mouse.click(r['x']+r['width']*.35,r['y']+r['height']*.4)
        page.wait_for_function(ROOT+f'.snapshot().{kind or "config"}.annotations.items.length===1')
        page.evaluate(ROOT+'.flush()')
        page.wait_for_function("document.activeElement?.dataset.property==='text'")
        text_width=page.evaluate(ROOT+'.annotations()')[0]['rect'][2]
        text=page.locator('[data-property=text]');text.fill('Review this region');text.dispatch_event('change');page.evaluate(ROOT+'.flush()')
        assert ''.join(v['text'] for v in items(page.evaluate(ROOT+'.snapshot()'))[0]['kind']['Text']['text']['segments'])=='Review this region'
        page.wait_for_function('async width=>(await '+ROOT+'.annotations())[0].rect[2]>width*2',arg=text_width)
        if any(axes):page.locator('[data-anchor-data]').check()
        for tool in tools:
            page.locator(f'[data-tool={tool}]').click();r=page.locator('canvas').bounding_box();count=len(items(page.evaluate(ROOT+'.snapshot()')))
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
        page.locator('.figgy-editor').screenshot(path=str(tmp_path/f'{family}-drawing.png'))

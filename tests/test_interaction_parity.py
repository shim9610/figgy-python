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
}
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
        window.figgyPreparationGate={entered:false,armedAt:performance.now(),release:()=>{
            prototype.onSubmittedWorkDone=original;release();
        }};
        prototype.onSubmittedWorkDone=function(...args){
            const completion=original.apply(this,args);
            window.figgyPreparationGate.entered=true;
            window.figgyPreparationGate.enteredAt=performance.now();
            return completion.then(()=>gate);
        };
    }""")
    try:
        execute('import asyncio; preparation=asyncio.create_task(fig.prepare_async(timeout=60))')
        try:
            # This is a GPU-fence handshake, not a visual condition. Poll on a
            # timer so delayed software-GPU presentation cannot stall RAF polling.
            page.wait_for_function('window.figgyPreparationGate.entered', polling=100)
        except Exception:
            print('Preparation gate diagnostic:', page.evaluate("""()=>({
                gate:window.figgyPreparationGate,now:performance.now(),
                status:document.querySelector('.figgy-editor [data-status]')?.textContent,
                stats:document.querySelector('.figgy-editor')?.figgy?.stats
            })"""))
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
            canvas.style.width='90%';const r=canvas.getBoundingClientRect(),dpr=devicePixelRatio||1;
            return [Math.round(r.width*dpr),Math.round(r.height*dpr)];
        }""")
        assert requested_size != before_size
    finally:
        page.evaluate('window.figgyPreparationGate.release()')
    report=json.loads(execute('print(json.dumps(await preparation))'))
    assert report['ready'] and report['backend']=='webgpu'
    page.evaluate(ROOT+'.flush()')
    check_display_frame_ready(page)
    assert page.locator('.figgy-properties').is_visible()
    if kind=='radial':
        assert page.locator('[data-target]').input_value()=='chart_title'
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


def check_display_frame_ready(page):
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
            inputs.click('object');inputs.click('object_chart_title')
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
        page.locator('[data-properties]').click();page.locator('[data-target]').select_option('axis_bottom')
        page.locator('[data-property=visible]').uncheck();page.locator('[data-property=tick_labels_visible]').uncheck();page.locator('[data-property=ticks_visible]').uncheck()
        for tick in ['None','Inside','Both','Outside']:
            page.locator('[data-property=tick_direction]').select_option(tick)
            execute('await fig.sync()');assert_axis(page.evaluate(ROOT+'.snapshot()'),tick)
        page.locator('[data-target]').select_option('chart_title')
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
        target=page.locator('[data-target]')
        def choose(control, value):
            page.locator(f'[data-property={control}]').select_option(value);page.evaluate(ROOT+'.flush()')
        target.select_option('axis_bottom');before=page.evaluate(ROOT+'.snapshot()')
        choose('axis_scale','Logarithmic')
        assert_scale(page.evaluate(ROOT+'.snapshot()'),'bottom_x','Logarithmic')
        current=page.evaluate(ROOT+'.snapshot()')
        assert current['config']['top_x']=={**before['config']['top_x'], **{key:current['config']['bottom_x'][key] for key in ['min','max','scale','major_spacing']}}
        assert page.locator('[data-property=axis_scale]').input_value()=='Logarithmic'
        assert not page.locator('.figgy-error').inner_text()
        for name,key in [('axis_bottom','bottom_x'),('axis_left','left_y')]:
            target.select_option(name)
            for scale in ['Logarithmic','Linear']:
                choose('axis_scale',scale);assert_scale(page.evaluate(ROOT+'.snapshot()'),key,scale)
        # Both the field series and the colorbar itself expose the same controls.
        target.select_option('field');assert page.locator('[data-property=color_scale]').count()==1
        target.select_option('colorbar')
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
        page.locator('[data-target]').select_option('colorbar')
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
        page.locator('[data-target]').select_option('axis_left')
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
            assert page.locator('[data-target]').input_value()==target
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
                for _ in range(16):
                    info=inputs.info();controls=info['controls'];rect=controls.get(key)
                    header=controls['object'];footer=controls['advanced']
                    top=header[1]+header[3]+30;bottom=footer[1]-40
                    if rect and top<rect[1] and rect[1]+rect[3]<bottom:
                        inputs.click(key);return
                    panel=info['chart_panel']
                    inputs.xdo('mousemove','--window',inputs.wid,round(panel[0]+panel[2]+150),350)
                    inputs.xdo('click',4 if rect and rect[1]<=top else 5);inputs.pump()
                raise AssertionError(f'Control not visible: {key}')
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
            page.locator('[data-target]').select_option(target)
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

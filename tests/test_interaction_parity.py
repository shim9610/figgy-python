"""Same input scenarios must work on native surfaces and real notebook WebGPU."""
import json
import os
import shutil
import time
import numpy as np
import pytest
import figgyplot as figgy
from test_radial_desktop import Inputs
from jupyter_harness import notebook

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
        panel=page.locator('.figgy-properties')
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

from object_navigation import ObjectNavigator
"""Numeric label editing must affect rendered labels in both interactive hosts."""
import json

import numpy as np
import pytest
import figgyplot as figgy

from jupyter_harness import notebook
from test_interaction_parity import NEEDS_UI, ROOT
from test_radial_desktop import Inputs


SETUP = """ax.imshow(np.array([[0.,.3],[.6,.91475]]), extent=(0,6.564076,0,6.564076), origin='lower', id='field')
ax.set_ylabel('Positive samples (log)')
for key in ['bottom_x','left_y']:
    fig.configure(config={key:{'min':0.,'max':6.564076,'major_spacing':1.3128152,'label_style':{'format':'Decimal','significant_digits':7}}})
fig.configure(config={'colorbar':{'axis':{'label_style':{'format':'Decimal','significant_digits':7}}}})
"""


def style(state, key):
    axis = state['config']['colorbar']['axis'] if key == 'colorbar' else state['config'][key]
    return axis['label_style']


@pytest.mark.skipif(NEEDS_UI, reason='requires real native and Jupyter UI')
def test_numeric_format_and_precision_editing_in_both_hosts(tmp_path):
    targets = [('tick_labels_left','left_y'), ('axis_bottom','bottom_x'),
               ('colorbar_tick_labels','colorbar')]
    native_styles = {}
    with figgy.figure(backend='native') as fig:
        ax = fig.axes[0]
        exec(SETUP, {'fig':fig,'ax':ax,'np':np})
        handle = fig.show(block=False)
        try:
            inputs = Inputs(handle)
            def click_control(key):
                # Inputs scrolls the actual property viewport, below the object tree.
                inputs.click(key)
            for target,key in targets:
                rect=inputs.info()['decorations'][target]
                # The deliberately wide initial labels overlap the title at
                # mid-height. Hit a visible label-strip section above it.
                hit=[rect[0]+rect[2]*(.2 if target.startswith('colorbar') else .8),rect[1]+rect[3]*.15,0,0] if 'tick_labels' in target else rect
                inputs.click_rect(hit)
                assert inputs.info()['selected']==target
                before=fig.get_settings()
                width_before=json.loads(fig._native.bounds_json(target))['rect'][2]
                assert 'significant_digits' in inputs.info()['controls'], (target, sorted(inputs.info()['controls']), inputs.info()['error'])
                click_control('significant_digits');inputs.key('ctrl+a')
                inputs.xdo('type','--clearmodifiers','2');inputs.key('Return')
                assert style(fig.get_settings(),key)['significant_digits']==2, (target, inputs.info()['controls'].get('significant_digits'), inputs.info()['error'])
                if target=='tick_labels_left':
                    assert json.loads(fig._native.bounds_json(target))['rect'][2] < width_before-10
                for notation in ['Scientific','Power','Decimal']:
                    click_control('label_format');inputs.click('label_format_'+notation)
                    assert style(fig.get_settings(),key)['format']==notation
                # A format edit changes neither range nor tick spacing.
                axis=lambda s:s['config']['colorbar']['axis'] if key=='colorbar' else s['config'][key]
                for field in ['min','max','major_spacing','scale']:
                    assert axis(fig.get_settings())[field]==axis(before)[field]
                native_styles[key]=style(fig.get_settings(),key)
                assert not inputs.info()['error']
            fig.savefig(tmp_path/'native-formatted.png')
        finally:
            handle.close();Inputs.pump()
    source="import json\nimport numpy as np\nimport figgyplot as figgy\nfig,ax=figgy.subplots(backend='webgpu')\n"+SETUP+"display(fig.widget())"
    with notebook(tmp_path/'numeric', source) as (page,execute):
        page.locator('[data-properties]').click()
        for target,key in targets:
            ObjectNavigator(page).choose(target)
            width_before=page.evaluate('async target=>(await '+ROOT+'.decorations())[target].rect[2]',target)
            digits=page.locator('[data-property=significant_digits]')
            digits.fill('2')
            # A Python update/comm acknowledgement must not replace a focused
            # uncommitted form input before its normal blur/change event.
            execute("fig.configure(config={'grid':{'show_minor_x':True}});print('updated')")
            assert digits.input_value()=='2'
            digits.press('Tab');page.evaluate(ROOT+'.flush()')
            assert style(page.evaluate(ROOT+'.snapshot()'),key)['significant_digits']==2
            if target=='tick_labels_left':
                width_after=page.evaluate('async target=>(await '+ROOT+'.decorations())[target].rect[2]',target)
                assert width_after < width_before-10
            for notation in ['Scientific','Power','Decimal']:
                page.locator('[data-property=label_format]').select_option(notation)
                page.evaluate(ROOT+'.flush()')
                assert style(page.evaluate(ROOT+'.snapshot()'),key)['format']==notation
            execute('await fig.sync()')
            state=json.loads(execute('print(json.dumps(fig.get_settings()))'))
            assert style(state,key)==native_styles[key]
            assert not page.locator('.figgy-error').inner_text()
        execute("copy=fig.to_code(); other,bx=figgy.subplots(backend='webgpu'); bx.imshow(np.array([[0.,.3],[.6,.91475]]),id='field'); exec(copy,{'fig':other}); assert other.get_settings()['config']==fig.get_settings()['config']; other.close()")
        path=tmp_path/'browser-formatted.png'
        execute(f'await fig.savefig_async({str(path)!r})')


@pytest.mark.skipif(NEEDS_UI, reason='requires real native and Jupyter UI')
@pytest.mark.parametrize('draft_kind',['property','snapshot','late_property','conflict_property'])
def test_numeric_draft_survives_external_update_before_selection_ack(tmp_path,draft_kind):
    source="import copy\nimport numpy as np\nimport figgyplot as figgy\nfig,ax=figgy.subplots(backend='webgpu')\n"+SETUP+"w=fig.widget(); display(w)"
    with notebook(tmp_path/'pending-number',source) as (page,execute):
        page.locator('[data-properties]').click()
        execute("""saved_send=w.send
held_acks=[]
def hold_ack(content,*args,**kwargs):
    if content.get('action')=='ack': held_acks.append((copy.deepcopy(content),args,kwargs))
    else: saved_send(content,*args,**kwargs)
w.send=hold_ack
""")
        if draft_kind in ('late_property','conflict_property'):execute("saved_send_state=w.send_state\nw.send_state=lambda *args,**kwargs:None")
        ObjectNavigator(page).choose('tick_labels_left')
        page.wait_for_function(ROOT+'.diagnostics().edit_inflight !== null')
        for _ in range(20):
            if int(execute('print(len(held_acks))').strip()): break
        else:pytest.fail('selection acknowledgement was not held')
        digits=page.locator('[data-property=significant_digits]')
        if draft_kind!='snapshot':digits.fill('2')
        update="fig.configure(config={'grid':{'show_minor_x':True}})"
        if draft_kind=='conflict_property':update+=";fig.configure(config={'left_y':{'label_style':{'significant_digits':4}}})"
        accepted=int(execute(update+";print(fig.revision)").strip())
        if draft_kind not in ('late_property','conflict_property'):page.wait_for_function('(revision)=>'+ROOT+'.diagnostics().accepted_revision>=revision',arg=accepted)
        if draft_kind!='snapshot':
            assert digits.input_value()=='2'
            digits.press('Tab')
        else:
            before_axis=page.evaluate(ROOT+".snapshot().config.left_y")
            area=page.evaluate('async()=>(await '+ROOT+'.decorations()).data_area.rect')
            canvas=page.locator('.figgy-editor canvas');box=canvas.bounding_box()
            size=canvas.evaluate('(c)=>[c.width,c.height]')
            page.mouse.move(box['x']+(area[0]+area[2]/2)*box['width']/size[0],box['y']+(area[1]+area[3]/2)*box['height']/size[1])
            page.mouse.wheel(0,-120)
            page.wait_for_function(ROOT+'.diagnostics().edit_pending')
        execute("w.send=saved_send\nfor content,args,kwargs in held_acks: saved_send(content,*args,**kwargs)")
        page.evaluate(ROOT+'.flush()')
        result=page.evaluate("({state:"+ROOT+".snapshot(),diagnostics:"+ROOT+".diagnostics(),events:figgyBrowserTrace.events.filter(e=>/^(edit|state|property)\\./.test(e.stage??''))})")
        (tmp_path/'numeric-edit-events.json').write_text(json.dumps(result,indent=2))
        expected=7 if draft_kind=='snapshot' else 4 if draft_kind=='conflict_property' else 2
        assert style(result['state'],'left_y')['significant_digits']==expected
        assert result['state']['config']['grid']['show_minor_x']
        if draft_kind=='snapshot':
            assert any(event.get('error','').startswith('stale edit:') for event in result['events'])
            for limit in ('min','max'):
                assert result['state']['config']['left_y'][limit]==before_axis[limit]
        assert int(execute("print(fig.get_settings()['config']['left_y']['label_style']['significant_digits'])").strip())==expected

        if draft_kind in ('snapshot','conflict_property'):
            assert 'stale edit:' in page.locator('.figgy-error').inner_text()
            digits.fill('3');digits.press('Tab');page.evaluate(ROOT+'.flush()')
            assert style(page.evaluate(ROOT+'.snapshot()'),'left_y')['significant_digits']==3
            assert page.evaluate(ROOT+'.snapshot().config.grid.show_minor_x')

        if draft_kind in ('late_property','conflict_property'):execute('w.send_state=saved_send_state; w.send_state()')

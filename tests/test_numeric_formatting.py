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

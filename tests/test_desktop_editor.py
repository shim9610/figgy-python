"""Real native input regression coverage for editor review findings."""
import copy
import json
import os
import shutil
import subprocess
import time

import numpy as np
import pytest
from PIL import ImageGrab
import figgyplot as figgy
from figgyplot.desktop import poll_events
from object_navigation import ensure_native_control_visible
from native_input import click as send_native_click


@pytest.mark.skipif(not os.environ.get('DISPLAY') or not shutil.which('xdotool') or not shutil.which('xclip'), reason='requires X11, xdotool and xclip')
def test_editor_preserves_canvas_and_edits_in_separate_settings_window(tmp_path):
    figure, ax = figgy.subplots(backend='native')
    x = np.arange(10, dtype=np.float64)
    ax.plot(x, x, id='signal', label='Signal')
    ax.plot(x, 9-x, id='reference', label='Reference')
    ax.set_title('Editor review'); ax.set_xlabel('Time'); ax.legend()
    window = figure.show(block=False)

    def pump():
        for _ in range(30):
            poll_events(); time.sleep(.004)

    def info(): return json.loads(window.info_json())
    def xdo(*args): return subprocess.check_output(['xdotool', *map(str,args)],text=True).strip()
    def click_rect(rect, wid=None):
        xdo('mousemove','--window',wid or chart_id,round(rect[0]+rect[2]/2),round(rect[1]+rect[3]/2));pump()
        send_native_click(xdo);pump()
    def click(name):
        ensure_native_control_visible(info,xdo,pump,chart_id,name)
        click_rect(info()['controls'][name])
    def key(name): xdo('key',name);pump()
    def type_text(rect, value, wid=None):
        click_rect(rect,wid);key('ctrl+a');xdo('type','--clearmodifiers','--',value);pump()
    def data_click(x, y):
        r=info()['decorations']['data_area'];cfg=figure.get_settings()['config']
        px=r[0]+(x-cfg['bottom_x']['min'])/(cfg['bottom_x']['max']-cfg['bottom_x']['min'])*r[2]
        py=r[1]+(cfg['left_y']['max']-y)/(cfg['left_y']['max']-cfg['left_y']['min'])*r[3]
        click_rect([px,py,0,0])
    def screenshot(name): ImageGrab.grab(xdisplay=os.environ['DISPLAY']).save(tmp_path/name)

    try:
        pump(); chart_id=xdo('search','--pid',os.getpid(),'--name','^Figgy$').splitlines()[-1]
        xdo('windowfocus',chart_id);pump()
        before=info(); canvas=before['chart_panel']; size=before['surface_size']
        click_rect(before['decorations']['chart_title'])
        assert info()['chart_panel']==canvas
        assert info()['surface_size']==[size[0]+320,size[1]]
        assert info()['chart_panel'][2]/info()['chart_panel'][3] == pytest.approx(960/600)
        click('close_properties')
        assert info()['surface_size']==size and info()['chart_panel']==canvas

        # Actual GPU hit, navigation, repeat-click toggle, blank-click and Esc.
        data_click(2,2)
        selected=info()['picked_values']; assert selected['series_id']=='signal'
        original=selected['index'];key('Right')
        assert info()['picked_values']['index']==original+1
        assert info()['picked_values']['x']==original+1
        screenshot('selected-values.png')
        key('Up');assert info()['picked_values']['series_id']=='reference'
        key('Escape');assert info()['picked_values'] is None
        assert figure.get_settings()['config'].get('picked_data') is None
        data_click(2,2);data_click(2,2)
        assert info()['selected'] is None and info()['picked_values'] is None
        data_click(2,2);data_click(2,8)
        assert info()['selected'] is None and figure.get_settings()['config'].get('picked_data') is None

        # Visibility can be restored through the object list after the hitbox is hidden.
        click_rect(info()['decorations']['chart_title']);click('visible')
        assert not figure.get_settings()['config']['chart_title']['visible']
        click('object_search');key('ctrl+a');xdo('type','--clearmodifiers','chart_title');pump()
        click('tree:panel/main/chart_title');assert info()['selected']=='chart_title'
        click('visible')
        assert figure.get_settings()['config']['chart_title']['visible']
        # A hidden title can be restored without selecting any chart object or inspector.
        click('visible');data_click(2,8);click('close_properties')
        assert not figure.get_settings()['config']['chart_title']['visible']
        assert info()['selected'] is None and not info()['properties_open']
        click('visibility_menu');click('show_chart_title')
        assert figure.get_settings()['config']['chart_title']['visible']
        for key_name, config_path in [('show_legend', ('legend','visible')), ('show_axis_title_bottom', ('bottom_x','title_option','visible'))]:
            click(key_name)
            node=figure.get_settings()['config']
            for part in config_path:node=node[part]
            assert not node
            click(key_name)
            node=figure.get_settings()['config']
            for part in config_path:node=node[part]
            assert node
        screenshot('visibility-menu.png');key('Escape')
        before_offset=figure.get_settings()['config']['chart_title']['offset_x']
        click_rect(info()['decorations']['chart_title']);key('Right')
        assert figure.get_settings()['config']['chart_title']['offset_x'] > before_offset
        click_rect(info()['decorations']['axis_title_bottom']);click('visible')
        assert not figure.get_settings()['config']['bottom_x']['title_option']['visible']
        click('visible');assert figure.get_settings()['config']['bottom_x']['title_option']['visible']

        # Legend entries are independent fields, with no tab/rule placeholders.
        click_rect(info()['decorations']['legend'])
        assert 'text' not in info()['controls'] and 'legend_label_signal' in info()['controls']
        ensure_native_control_visible(info,xdo,pump,chart_id,'legend_label_signal')
        type_text(info()['controls']['legend_label_signal'],'Reviewed signal')
        state=figure.get_settings()
        assert ''.join(s['text'] for s in state['series'][0]['label']['segments'])=='Reviewed signal'
        assert any(s.get('rule') for s in state['config']['legend']['content']['segments'])
        click('visible');assert not figure.get_settings()['config']['legend']['visible']
        click('visible');assert figure.get_settings()['config']['legend']['visible']
        screenshot('legend-entries.png')

        # Black (s=v=0) exercises the marker at the lower-left edge of the square.
        click_rect(info()['decorations']['chart_title']);click('color')
        assert 'color_picker' in info()['controls'];screenshot('color-picker.png')
        key('Escape');pump()
        if 'color_picker' in info()['controls']:click_rect(info()['decorations']['chart_title'])

        # Advanced JSON is a distinct OS window, shares SSOT, rejects errors atomically.
        baseline=copy.deepcopy(figure.get_settings());click('advanced');pump()
        settings=info()['settings_window'];assert settings['window_role']=='settings'
        assert settings['gpu_context_id']==info()['gpu_context_id']
        settings_id=xdo('search','--pid',os.getpid(),'--name','Advanced chart settings').splitlines()[-1]
        assert settings_id != chart_id
        xdo('windowfocus',settings_id);pump()
        invalid=copy.deepcopy(baseline);invalid['config']['bottom_x']['min']=invalid['config']['bottom_x']['max']
        def paste_settings(value):
            click_rect(info()['settings_window']['controls']['settings_json'],settings_id)
            from native_input import set_clipboard
            set_clipboard(json.dumps(value))
            key('ctrl+a');key('ctrl+v')
            click_rect(info()['settings_window']['controls']['apply_settings'],settings_id)
        paste_settings(invalid)
        assert info()['settings_window']['error']
        assert figure.get_settings()==baseline and not window.closed
        valid=copy.deepcopy(baseline);valid['config']['chart_title']['offset_x'] += 7
        paste_settings(valid)
        assert not info()['settings_window']['error']
        assert figure.get_settings()['config']['chart_title']['offset_x']==valid['config']['chart_title']['offset_x']
        screenshot('separate-settings.png')
        key('alt+F4');pump();assert info()['settings_window'] is None and not window.closed

        # EWMH maximization requires a window manager and wmctrl in the test host.
        xdo('windowfocus',chart_id);pump()
        if info()['properties_open']:click('close_properties')
        if shutil.which('wmctrl'):
            subprocess.run(['wmctrl','-ir',hex(int(chart_id)),'-b','add,maximized_vert,maximized_horz'],check=True);pump()
            assert info()['inspector_overlay']
            maximized=info();click('properties')
            assert info()['chart_panel']==maximized['chart_panel']
            assert info()['surface_size']==maximized['surface_size']
            click('close_properties')
            subprocess.run(['wmctrl','-ir',hex(int(chart_id)),'-b','remove,maximized_vert,maximized_horz'],check=True);pump()

        # Fullscreen properties overlay the same chart, with no resize or reflow.
        xdo('windowfocus',chart_id);pump();data_click(2,8);key('F11');pump()
        assert info()['inspector_overlay']
        if info()['properties_open']:click('close_properties')
        full=info();click('properties')
        assert info()['surface_size']==full['surface_size']
        assert info()['chart_panel']==full['chart_panel']
        screenshot('fullscreen-overlay.png')
        assert info()['column_uploads']==4
        assert info()['rgba_readbacks']==info()['png_encodes']==0
        (tmp_path/'editor-state.json').write_text(json.dumps(info(),indent=2))
    except BaseException:
        screenshot('failure.png')
        (tmp_path/'failure-state.json').write_text(json.dumps(info(),indent=2))
        raise
    finally:
        window.close();pump();figure.close()

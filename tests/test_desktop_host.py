"""Actual X11 surface/input regression, enabled when a display and xdotool exist."""
import json,os,shutil,subprocess,time
from pathlib import Path
import numpy as np
import pytest
from figgy import subplots
from figgy.desktop import poll_events

def test_surface_drag_resize_reopen_and_no_png(tmp_path):
    tool = shutil.which('xdotool')
    if not os.environ.get('DISPLAY') or not tool:
        pytest.skip('requires X11 display and xdotool; run under Xvfb for software-GPU validation')
    fig, ax = subplots(backend='native')
    ax.plot(np.arange(32,dtype=np.float32),np.arange(32,dtype=np.float32),id='signal')
    ax.set_title('Editable title')
    handle = fig.show(block=False)
    def pump():
        for _ in range(12):
            poll_events();time.sleep(.005)
    def xdo(*args):return subprocess.check_output([tool,*map(str,args)],text=True).strip()
    pump()
    wid=xdo('search','--name','Figgy').splitlines()[-1]
    xdo('windowfocus',wid);pump()
    before=fig.revision
    bounds=json.loads(fig._native.bounds_json('chart_title'))['rect']
    x,y=bounds[0]+bounds[2]/2,bounds[1]+bounds[3]/2
    xdo('mousemove','--window',wid,round(x),round(y));pump();xdo('mousedown',1);pump()
    for step in range(1,5):
        xdo('mousemove','--window',wid,round(x+step*5),round(y+step*2));pump()
    xdo('mouseup',1);pump()
    assert fig.revision>before
    assert fig.get_settings()['config']['chart_title']['offset_x']>0
    # The selected title's property text field is below the Object row.
    xdo('mousemove','--window',wid,1040,142);xdo('click',1);pump()
    xdo('key','ctrl+a');xdo('type','Rust edited');pump()
    assert 'Rust edited' in fig.to_code()
    xdo('windowsize',wid,1350,680);pump()
    info=json.loads(handle.info_json())
    assert info['surface_size']==[1350,680]
    assert info['surface_frames']>1 and info['column_uploads']==2
    assert info['rgba_readbacks']==0 and info['png_encodes']==0
    xdo('mousemove','--window',wid,1080,74);xdo('click',1);pump()
    clip=shutil.which('xclip')
    if clip:
        copied=subprocess.check_output([clip,'-selection','clipboard','-o'],text=True,timeout=5)
        assert 'fig.apply_settings' in copied
        exec(copied,{'fig':fig})
    # Resize changed the panel's left edge to 1040 physical pixels.
    xdo('mousemove','--window',wid,1100,96);xdo('click',1);pump()
    xdo('key','ctrl+a');xdo('type',str(tmp_path/'ui.png'));pump()
    xdo('mousemove','--window',wid,1260,96);xdo('click',1);pump()
    assert (tmp_path/'ui.png').read_bytes().startswith(b'\x89PNG')
    fig.savefig(tmp_path/'native.png');pump()
    assert (tmp_path/'native.png').read_bytes().startswith(b'\x89PNG')
    handle.close();pump()
    handle=fig.show(block=False);pump()
    assert json.loads(handle.info_json())['column_uploads']==2
    assert json.loads(handle.info_json())['png_encodes']==2
    # A second Figure shares the event host while keeping its own GPU resources.
    other,other_ax=subplots(backend='native');other_ax.scatter([0,1],[1,0]);second=other.show(block=False);pump()
    assert json.loads(second.info_json())['surface_frames']>0
    second.close();other.close();handle.close();pump();fig.close()

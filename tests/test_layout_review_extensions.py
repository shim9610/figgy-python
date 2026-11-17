"""Accepted geometry and review metadata retain their separate contracts."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import json
import struct
import subprocess
import sys

import pytest
import figgyplot as fg
from figgyplot.review import Session
from test_editor_properties import edit, object_for


@pytest.mark.parametrize('backend',['native','webgpu'])
def test_figure_resize_reflows_grid_and_preserves_data_and_history(backend):
    with fg.Figure(backend=backend,grid=[['left','right']]) as fig:
        fig.subplots['left'].plot([0,1],[2,3],id='one')
        fig.subplots['right'].plot([0,1],[4,5],id='two')
        before=fig.get_settings();uploads=fig.info['column_uploads' if backend=='native' else 'transfer_snapshot_bytes']
        edit(fig,'figure','Figure size/width',1200)
        after=fig.get_settings()
        assert after['identity']['layout']['size']==[1200,600]
        assert after['config']['chart_area']['width']==594
        assert after['config']['subplots'][0]['config']['chart_area']['x']==606
        assert after['series']==before['series']
        assert after['config']['bottom_x']==before['config']['bottom_x']
        assert fig.info['column_uploads' if backend=='native' else 'transfer_snapshot_bytes']==uploads
        fig.undo();assert fig.get_settings()==before
        fig.redo();assert fig.get_settings()==after


@pytest.mark.parametrize('backend',['native','webgpu'])
def test_plot_rectangle_is_distinct_from_panel_geometry(backend):
    with fg.Figure(backend=backend) as fig:
        fig.axes[0].plot([0,1],[2,3],id='one')
        before=fig.get_settings()
        edit(fig,'data_area','Plot area/bounds',[100,100,600,350])
        after=fig.get_settings()
        assert after['config']['chart_area']==before['config']['chart_area']
        for key in ('min','max','scale'):
            assert after['config']['bottom_x'][key]==before['config']['bottom_x'][key]
            assert after['config']['left_y'][key]==before['config']['left_y'][key]
        assert object_for(fig,'data_area')['fields'][next(i for i,f in enumerate(object_for(fig,'data_area')['fields']) if f['id']=='Plot area/bounds')]['value']==[100,100,600,350]
        with pytest.raises(ValueError):edit(fig,'data_area','Plot area/bounds',[100,100,-1,350])
        assert fig.get_settings()==after
        fig.undo();assert fig.get_settings()==before


@pytest.mark.parametrize('backend',['native','webgpu'])
@pytest.mark.parametrize('family',['radar','boxplot','radial','categorical'])
def test_bounded_plot_geometry_can_return_to_automatic(backend,family):
    with fg.Figure(backend=backend) as fig:
        if family=='radar':fig.axes[0].radar(['A','B','C'],[2,3,4])
        elif family=='boxplot':fig.axes[0].boxplot([[1,2,3],[2,4,6]])
        elif family=='radial':fig.axes[0].donut([2,3,4])
        else:fig.axes[0].bar(['A','B','C'],[2,3,4])
        before=fig.get_settings()
        edit(fig,'data_area','Plot area/bounds',[70,60,500,400])
        assert fig.get_settings()[family]['decorations']['data_area']==dict(x=70,y=60,width=500,height=400)
        owner=json.loads(json.dumps(fig.get_settings()[family]));owner['decorations']=before[family]['decorations']
        assert owner==before[family]
        edit(fig,'data_area','Plot area/automatic',True)
        assert fig.get_settings()==before
        edit(fig,'figure','Figure size/width',1200)
        assert fig.get_settings()['config']['chart_area']['width']==1200
        assert fig.get_settings()[family]==before[family]
        if backend=='native':assert fig.render_rgba().shape[1]==1200
        fig.undo();assert fig.get_settings()==before


def test_targeted_ui_comments_are_durable_and_separate_from_ssot(tmp_path):
    with Session(tmp_path,backend='webgpu') as session:
        fig=session.figure(id='plot');fig.axes[0].plot([0,1],[2,3],id='one')
        fig.axes[0].text(.2,.2,'Document text',coords='ratio',id='note')
        session.start();before=fig.get_settings()
        target=next(v['id'] for v in fig.editor_properties() if v['target']=='annotation:note')
        comments=[dict(id='comment-one',target=target,label='Document text',text='주석을 오른쪽으로 옮겨 주세요',channel='ui_target')]
        session._set_target_comments('plot',comments)
        session._set_comment_text('plot','전체 레이아웃도 넓혀 주세요')
        assert fig.get_settings()==before
        with Session.open(tmp_path) as reader:assert reader._review_state('plot')['target_comments']==comments
        session.submit('plot','request_changes')
        feedback=session.feedback(session.events()[0]['work_id'])['round']['documents']['plot']
        assert feedback['approval']['settings']==before and not feedback['approval']['changes']
        assert any(c['target']==target and c['text']==comments[0]['text'] for c in feedback['comments'])


def test_subscription_returns_only_after_the_complete_batch(tmp_path):
    with Session(tmp_path,backend='webgpu') as session:
        for fid in ['left','right']:
            fig=session.figure(id=fid);fig.axes[0].plot([0,1],[2,3],id='one')
        session.start()
        with ThreadPoolExecutor(max_workers=1) as pool:
            def wait():
                with Session.open(tmp_path) as reader:return reader.subscribe(timeout=3)
            pending=pool.submit(wait)
            session.submit('left','request_changes',comments='Make this wider')
            with pytest.raises(TimeoutError):pending.result(timeout=.05)
            session.submit('right','accept')
            assert pending.result(timeout=3)==session.events()[0]
        assert session.subscribe(after=session.events()[0]['work_id'],timeout=0) is None


def test_review_font_uses_the_selected_cjk_face_and_persists(tmp_path):
    from figgyplot._native import font_family_available
    from figgyplot._review_font import font_data
    family='Noto Sans CJK KR' if font_family_available('Noto Sans CJK KR') else 'DejaVu Sans'
    with Session(tmp_path,backend='webgpu',review_font=family,review_font_size=16) as session:
        fig=session.figure(id='plot');fig.axes[0].plot([0,1],[2,3])
        before=fig.get_settings();widget=session.widget(fig)
        assert widget.review['font_family']==family and widget.review['font_size']==16
        assert bytes(widget.review_font_data)==font_data(family)
        assert fig.get_settings()==before
        data=font_data(family)
        assert data[:4]!=b'ttcf' and len(data)%4==0
        assert sum(struct.unpack('>'+str(len(data)//4)+'I',data))&0xffffffff==0xB1B0AFBA
    with Session.open(tmp_path) as resumed:assert resumed.snapshot()['review_style']['font_family']==family


def test_subscription_cli_delivers_the_approval_signal(tmp_path):
    with Session(tmp_path,backend='webgpu') as session:
        fig=session.figure(id='plot');fig.axes[0].plot([0,1],[2,3])
        session.start()
        process=subprocess.Popen([sys.executable,'-m','figgyplot.review','subscribe',str(tmp_path),'--timeout','10'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            with pytest.raises(subprocess.TimeoutExpired):process.communicate(timeout=.2)
            session.submit('plot','request_changes',comments='Make the figure wider')
            stdout,stderr=process.communicate(timeout=10)
            assert process.returncode==0,stderr
            assert json.loads(stdout)==session.events()[0]
        finally:
            if process.poll() is None:process.kill();process.communicate()


def test_resume_rejects_an_unavailable_review_font_before_opening_windows(tmp_path,monkeypatch):
    with Session(tmp_path,backend='native',review_font='DejaVu Sans') as session:
        fig=session.figure(id='plot');fig.axes[0].plot([0,1],[2,3]);session.start()
    def missing(family):raise ValueError('Review font is not installed')
    monkeypatch.setattr('figgyplot._review_font.font_data',missing)
    with Session.open(tmp_path) as resumed:
        with pytest.raises(ValueError,match='font is not installed'):resumed.present()
        assert not resumed._handles

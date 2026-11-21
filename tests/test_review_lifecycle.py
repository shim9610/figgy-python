"""Review acceptance follows actual settings AND data, across complete rounds."""
import json
from pathlib import Path
import runpy
import subprocess
import sys

import pytest

from figgyplot.review import Session
from figgyplot._review_diff import persistent


def builder(path, *, values='[1,2]', width=2.5, dpi=120, donut='[3,2,1]'):
    path.write_text("def build(session):\n"
                    f"    line=session.figure(id='line',dpi={dpi})\n"
                    f"    line.axes[0].plot([0,1],{values},id='signal',linewidth={width})\n"
                    "    ring=session.figure(id='donut')\n"
                    f"    ring.axes[0].donut({donut})\n")


@pytest.mark.parametrize('change',['unchanged','same_bounds_data','style','dpi','accepted_donut_data'])
def test_successor_carries_only_exact_accepted_chart_content(tmp_path,change):
    source=tmp_path/'plots.py';builder(source)
    with Session(tmp_path/'cache',source={'entrypoint':str(source)},backend='webgpu') as session:
        runpy.run_path(str(source))['build'](session);session.start()
        accepted='donut' if change=='accepted_donut_data' else 'line'
        edited='line' if accepted=='donut' else 'donut'
        previous=session.snapshot()['rounds'][-1]
        session.submit(accepted,'accept')
        session.submit(edited,'request_changes',comments='Revise only this chart')
        if change=='same_bounds_data':builder(source,values='[2,1]')
        elif change=='style':builder(source,width=4)
        elif change=='dpi':builder(source,dpi=144)
        elif change=='accepted_donut_data':builder(source,donut='[2,3,1]')
        work=session.events()[0]['work_id'];assert session.regenerate(work)==2
        current=session.snapshot()['rounds'][-1]
        if change=='unchanged':
            with pytest.raises(ValueError,match='already regenerated'):
                session.finish(work)
            assert session.status['pending']==[edited]
            approval=current['documents'][accepted]['approval']
            assert approval['carried_from']['round_id']==previous['id']
            assert approval['settings']==current['documents'][accepted]['baseline']
            assert approval['changes']==[]
            # The unchanged chart remains recoverable, but no new review view opens.
            with Session.open(session.cache_dir) as reopened:
                restored=reopened.restore(accepted)
                assert persistent(restored.get_settings())==persistent(approval['settings'])
        else:
            assert set(session.status['pending'])=={'line','donut'}
            assert current['documents'][accepted]['approval'] is None


def test_finish_is_a_durable_lifecycle_signal_not_a_new_edit_round(tmp_path):
    with Session(tmp_path,backend='webgpu') as session:
        fig=session.figure(id='plot');fig.axes[0].plot([0,1],[2,3],id='signal')
        session.start();before=fig.get_settings()
        session.submit('plot','accept',comments='저장 후 종료',intent='finish')
        event=session.subscribe(timeout=0)
        assert event['intent']=='finish'
        with pytest.raises(ValueError,match='use finish'):
            session.regenerate(event['work_id'])
        assert session.finish(event['work_id'])==1
        assert session.finish(event['work_id'])==1
        assert session.status['state']=='completed' and not session.status['pending']
        assert session.subscribe(timeout=0) is None
        state=session.snapshot()
        assert len(state['rounds'])==1
        assert state['rounds'][0]['documents']['plot']['approval']['settings']==before
        with Session.open(tmp_path) as resumed:
            assert resumed.status['state']=='completed'
            assert persistent(resumed.restore('plot').get_settings())==persistent(before)


def test_source_finish_validates_exact_data_and_never_opens_another_review(tmp_path):
    source=tmp_path/'plots.py';builder(source)
    with Session(tmp_path/'cache',source={'entrypoint':str(source)},backend='webgpu') as session:
        runpy.run_path(str(source))['build'](session);session.start()
        session.submit('line','accept')
        session.submit('donut','accept',comments='Save and close',intent='finish')
        work=session.events()[0]['work_id']
        builder(source,values='[2,1]')  # Same settings/extents, different arrays.
        with pytest.raises(ValueError,match='exact approved settings and data'):
            session.finish(work)
        assert session.status['state']=='ready'
        builder(source)
        assert session.finish(work)==2
        assert session.status['state']=='completed' and not session.status['pending']
        assert not session._handles and not session.events()


def test_finish_cli_requires_the_writer_lease_and_returns_terminal_state(tmp_path):
    with Session(tmp_path,backend='webgpu') as session:
        session.figure(id='plot').axes[0].plot([0,1],[2,3])
        session.start();session.submit('plot','accept',intent='finish')
        work=session.events()[0]['work_id'];claim=session.claim(work,worker_id='cli')
        args=[sys.executable,'-m','figgyplot.review','finish',str(tmp_path),work]
        without=subprocess.run(args,capture_output=True,text=True)
        assert without.returncode!=0 and '--claim-token' in without.stderr
        accepted=subprocess.run(args+['--claim-token',claim['token']],capture_output=True,text=True)
        assert accepted.returncode==0,accepted.stderr
        assert json.loads(accepted.stdout)==dict(round=1,finished=True)
        assert session.status['state']=='completed'


def test_finish_on_one_figure_does_not_override_requested_changes_on_another(tmp_path):
    with Session(tmp_path,backend='webgpu') as session:
        for fid in ('line','donut'):session.figure(id=fid).axes[0].plot([0,1],[2,3])
        session.start()
        session.submit('line','accept',intent='finish')
        session.submit('donut','request_changes',comments='Change the palette')
        assert session.events()[0]['intent']=='revise'
        with pytest.raises(ValueError,match='Finish intent requires'):
            session.submit('donut','request_changes',intent='finish')

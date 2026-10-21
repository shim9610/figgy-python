"""Durability, turn barriers and executable-source reconciliation for review."""
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

import figgyplot as fg
from figgyplot.review import Session
from figgyplot._review_diff import changes, persistent, preserved


def create(session, id='plot', family='line'):
    fig=session.figure(id=id)
    ax=fig.axes[0]
    if family=='line':ax.plot([0,1],[2,3],id='signal')
    elif family=='mapped':ax.scatter([0,1],[2,3],c=[1,2],s=[2,4],id='mapped')
    elif family=='matrix':ax.imshow([[1,2],[3,4]],id='field')
    elif family=='vector':ax.quiver([0,1],[1,2],[2,1],[1,3],id='arrows')
    elif family=='pie':ax.pie([3,2,1])
    elif family=='bar':ax.bar(['A','B'],[3,4])
    elif family=='box':ax.boxplot([[1,2,3],[2,4,6]])
    elif family=='radar':ax.radar(['A','B','C'],[1,2,3])
    elif family=='panels':
        fig.set_layout([['main','other']]);ax.plot([0,1],[1,2],id='one')
        fig.subplots['other'].axes.twinx(id='pressure').plot([0,1],[3,4],id='two')
    return fig


@pytest.mark.parametrize('family',['line','mapped','matrix','vector','pie','bar','box','radar','panels'])
@pytest.mark.parametrize('backend',['native','webgpu'])
def test_complete_binary_checkpoint_restores_all_families(tmp_path,family,backend):
    with Session(tmp_path/'cache',backend=backend) as session:
        fig=create(session,family=family)
        session.start();baseline=fig.get_settings()
        fig.axes[0].set_title('Approved title')
        approved=fig.get_settings();counter='column_uploads' if backend=='native' else 'transfer_snapshot_bytes';uploads=fig.info[counter]
        session.submit('plot','request_changes',comments='Keep this title',expected_revision=fig.revision)
        assert fig.info[counter]==uploads
        signal=session.events()[0]
        assert 'settings' not in signal and 'columns' not in signal
        assert session.events()==[signal]
        checkpoint=session.feedback(signal['work_id'])['round']['documents']['plot']
        assert checkpoint['baseline']==baseline and checkpoint['approval']['settings']==approved
        if family in ('pie','bar','box','radar'):assert checkpoint['bounded_data']
        assert 'Keep this title' not in json.dumps(approved)
    with Session.open(tmp_path/'cache') as resumed:
        recovered=resumed.restore('plot',backend=backend)
        assert recovered.get_settings()==approved
        if backend=='native':assert recovered.to_png().startswith(b'\x89PNG')
        assert resumed.events()==[signal]


def test_all_figure_barrier_comments_and_idempotent_submission(tmp_path):
    with Session(tmp_path,backend='webgpu') as session:
        a=create(session,'a');b=create(session,'b')
        session.start();a.axes[0].set_title('Human edit')
        accepted=session.submit('a','request_changes',comments='Move the legend')
        assert not session.events()
        with pytest.raises(RuntimeError,match='approved'):a.axes[0].set_title('Too late')
        assert session.submit('a','request_changes',comments='Move the legend')==accepted
        session.submit('b','accept')
        first=session.events();assert len(first)==1
        assert Session.open(tmp_path).events()==first
        with pytest.raises(ValueError,match='different'):session.submit('a','accept')
        session.reopen('a')
        assert not session.events()
        with pytest.raises(ValueError,match='Stale'):session.feedback(first[0]['work_id'])
        a.axes[0].set_title('Revised human edit')
        session.submit('a','accept');assert len(session.events())==1


def test_accept_without_changes_and_window_close_are_distinct(tmp_path):
    with Session(tmp_path,backend='webgpu') as session:
        fig=create(session);session.start()
        fig.close()
        assert session.snapshot()['rounds'][-1]['documents']['plot']['approval'] is None
        assert not session.events()
        session.restore('plot');session.submit('plot','accept')
        assert session.snapshot()['rounds'][-1]['status']=='completed'
        assert not session.events()


def test_ui_comment_edits_preserve_separately_targeted_api_comments(tmp_path):
    with Session(tmp_path,backend='webgpu') as session:
        create(session);session.start()
        session.comment('plot','Keep the data',target={'series_id':'signal'})
        session._set_comment_text('plot','Adjust the title')
        session._set_comment_text('plot','')
        doc=session.snapshot()['rounds'][-1]['documents']['plot']
        assert len(doc['comments'])==1
        assert doc['comments'][0]['text']=='Keep the data'
        session.submit('plot','request_changes',comments='Use a larger font')
        comments=session.feedback(session.events()[0]['work_id'])['round']['documents']['plot']['comments']
        assert [c['text'] for c in comments]==['Keep the data','Use a larger font']
        assert comments[0]['target']=={'series_id':'signal'}


def test_cache_creation_and_open_do_not_claim_foreign_directories(tmp_path):
    foreign=tmp_path/'data';foreign.mkdir()
    payload=foreign/('0'*64+'.npy');payload.write_bytes(b'foreign file')
    before=sorted(p.relative_to(tmp_path) for p in tmp_path.rglob('*'))
    with pytest.raises(ValueError,match='empty|dedicated'):Session(tmp_path)
    assert sorted(p.relative_to(tmp_path) for p in tmp_path.rglob('*'))==before
    assert payload.read_bytes()==b'foreign file'
    missing=tmp_path/'absent'
    with pytest.raises(ValueError,match='manifest|cache'):Session.open(missing)
    assert not missing.exists()


def test_approval_retry_closes_views_outside_manifest_lock(tmp_path):
    # A close observer can inspect session state. A nested file lock would hang,
    # so isolate this regression in a process with a finite parent-side timeout.
    code='''
import json,sys
from pathlib import Path
from figgyplot.review import Session
import figgyplot._review_store as storage
cache=Path(sys.argv[1])
with Session(cache,backend='webgpu') as session:
    fig=session.figure(id='plot');fig.axes[0].plot([0,1],[1,2]);session.start()
    class Handle:
        closed=False
        def close(self):
            assert session.status['state']=='ready'
            self.closed=True
    handle=Handle();fig._windows.append(handle)
    original=storage._sync_directory
    def fail(path):
        state=json.loads((cache/'manifest.json').read_text())
        if path==cache and state['rounds'][-1]['documents']['plot']['approval'] is not None:
            raise OSError('post-rename failure')
        original(path)
    storage._sync_directory=fail
    try:
        session.submit('plot','request_changes')
    except OSError:pass
    finally:storage._sync_directory=original
    assert not handle.closed
    session.submit('plot','request_changes')
    assert handle.closed and len(session.events())==1
'''
    subprocess.run([sys.executable,'-c',code,str(tmp_path)],check=True,timeout=15)


def test_atomic_failure_preserves_old_checkpoint_and_keeps_view_open(tmp_path,monkeypatch):
    import figgyplot._review_store as storage
    class Handle:
        closed=False
        def close(self):self.closed=True
    with Session(tmp_path,backend='webgpu') as session:
        fig=create(session);session.start();handle=Handle();fig._windows.append(handle)
        original=(tmp_path/'manifest.json').read_bytes()
        def fail(*args):raise OSError('disk unavailable')
        with monkeypatch.context() as m:
            m.setattr(storage.os,'replace',fail)
            with pytest.raises(OSError,match='disk unavailable'):session.submit('plot','request_changes',comments='Retry me')
        assert (tmp_path/'manifest.json').read_bytes()==original
        assert not handle.closed and not session.events()
        session.submit('plot','request_changes',comments='Retry me')
        assert handle.closed
        assert session.feedback(session.events()[0]['work_id'])['round']['documents']['plot']['comments'][0]['text']=='Retry me'


def test_stale_revision_and_corrupt_data_reject_without_approval(tmp_path):
    with Session(tmp_path,backend='webgpu') as session:
        fig=create(session);session.start();rev=fig.revision
        fig.axes[0].set_title('Newer')
        with pytest.raises(ValueError,match='Stale'):session.submit('plot','accept',expected_revision=rev)
        ref=next(iter(session.snapshot()['rounds'][-1]['documents']['plot']['columns'].values()))
        (tmp_path/ref['file']).write_bytes(b'broken')
        with pytest.raises(ValueError,match='integrity'):session.submit('plot','accept')
        assert session.snapshot()['rounds'][-1]['documents']['plot']['approval'] is None
        with pytest.raises(ValueError,match='integrity'):Session.open(tmp_path)


def test_input_snapshot_survives_user_mutation_transfer_release_and_cleanup(tmp_path):
    with Session(tmp_path,backend='webgpu') as session:
        fig=session.figure(id='plot');x=np.array([1,2,3],dtype=np.float32)
        fig.axes[0].plot(x,x,id='s');session.start()
        doc=session.snapshot()['rounds'][-1]['documents']['plot']
        assert doc['columns']['s/x']['sha256']==doc['columns']['s/y']['sha256']
        x[:]=99;fig._native.acknowledged();assert not fig._native.columns
        orphan=tmp_path/'data'/('0'*64+'.npy');orphan.write_bytes(b'unreferenced')
        resumed=Session.open(tmp_path);assert not orphan.exists()
        ref=doc['columns']['s/x'];assert np.array_equal(resumed._store.get(ref),[1,2,3])
        assert resumed._store.get(ref).dtype==np.dtype('<f4')
        assert (tmp_path/ref['file']).exists()
        session.submit('plot','request_changes');assert (tmp_path/ref['file']).exists()


def test_source_reconciliation_validation_cleanup_and_duplicate_work(tmp_path):
    source=tmp_path/'plots.py'
    def write(width=2.5,values='[1,2]'):
        source.write_text("def build(session):\n    fig=session.figure(id='plot')\n    fig.axes[0].plot([0,1],"+values+",id='signal',linewidth="+str(width)+")\n")
    write()
    with Session(tmp_path/'cache',source={'entrypoint':str(source)},backend='webgpu') as session:
        fig=session.figure(id='plot');fig.axes[0].plot([0,1],[1,2],id='signal')
        session.start();fig.update('signal',linewidth=7)
        expected_width=fig.get_settings()['series'][0]['render_type']['Line']['line']['line_width']
        session.submit('plot','request_changes',comments='Use the edited width')
        event=session.events()[0];work=event['work_id'];old= session.feedback(work)['round']
        old_files={ref['file'] for d in old['documents'].values() for ref in d['columns'].values()}
        with pytest.raises(ValueError,match='did not reproduce'):session.regenerate(work)
        assert session.events()==[event]
        source.write_text('def build(session):\n    raise RuntimeError("bad code")\n')
        with pytest.raises(RuntimeError,match='bad code'):session.regenerate(work)
        assert session.events()==[event]
        write(7,values='[5,6]')
        assert session.regenerate(work)==2
        assert session.regenerate(work)==2
        with pytest.raises(ValueError,match='Stale Figure'):fig.axes[0].set_title('Old window')
        assert not session.events()
        state=session.snapshot();assert len(state['rounds'])==1
        new=state['rounds'][0];assert new['number']==2 and new['status']=='reviewing'
        assert new['documents']['plot']['validated_png_sha256']
        new_files={ref['file'] for d in new['documents'].values() for ref in d['columns'].values()}
        assert all(not (session.cache_dir/p).exists() for p in old_files-new_files)
        assert all((session.cache_dir/p).exists() for p in new_files)
        restored=session.restore('plot');assert restored.get_settings()['series'][0]['render_type']['Line']['line']['line_width']==expected_width


def test_diff_excludes_transients_and_addresses_create_delete_reorder(tmp_path):
    with Session(tmp_path,backend='webgpu') as session:
        fig=create(session)
        fig.axes[0].text(.2,.2,'A',coords='ratio',id='a')
        fig.axes[0].text(.4,.4,'B',coords='ratio',id='b')
        a=fig.get_settings();b=json.loads(json.dumps(a))
        b['config']['active_layer']='Base';b['config']['picked_data']=None
        assert changes(a,b)==[]
        b['config']['annotations']['items'].reverse()
        diff=changes(a,b);assert any(c['op']=='move' for c in diff)
        assert all(preserved(c,b) for c in diff)
        b['config']['annotations']['items'].pop()
        assert any(c['op']=='remove' for c in changes(a,b))
        b['config']['annotations']['items'].append(dict(a['config']['annotations']['items'][0],id='new'))
        assert any(c['op']=='add' for c in changes(a,b))


def test_cli_reconnect_reads_signal_without_binary_payloads(tmp_path):
    with Session(tmp_path,backend='webgpu') as session:
        create(session);session.start();session.submit('plot','request_changes',comments='Try a log axis')
        data=subprocess.check_output([sys.executable,'-m','figgyplot.review','events',str(tmp_path)],text=True)
        event=json.loads(data)[0]
        assert event==session.events()[0]
        assert 'columns' not in data and 'base64' not in data


def test_source_writer_lease_reconnect_expiry_and_stale_token(tmp_path):
    with Session(tmp_path,backend='webgpu') as session:
        create(session);session.start();session.submit('plot','request_changes')
        work=session.events()[0]['work_id'];claim=session.claim(work,worker_id='agent-a')
        other=Session.open(tmp_path)
        with pytest.raises(RuntimeError,match='another'):other.claim(work,worker_id='agent-b')
        assert other.claim(work,worker_id='agent-a')['token']==claim['token']
        # Simulate a disconnected worker with an expired durable lease.
        with session._store.locked():
            state=session._store.read();state['rounds'][-1]['claim']['expires']=0;session._store.write(state)
        new=other.claim(work,worker_id='agent-b');assert new['token']!=claim['token']
        with pytest.raises(ValueError,match='lease'):session.regenerate(work,claim_token=claim['token'])


def test_feedback_schema_and_packaged_skill_discovery(tmp_path):
    import figgyplot.review as review
    with Session(tmp_path,backend='webgpu') as session:
        create(session,family='box');session.start();session.submit('plot','request_changes')
        feedback=session.feedback(session.events()[0]['work_id'])
        schema_path=Path(review.__file__).with_name('review-feedback-v1.schema.json')
        schema=json.loads(schema_path.read_text())
        # jsonschema is part of the notebook test environment, not a runtime dependency.
        from jsonschema import Draft202012Validator
        Draft202012Validator(schema).validate(feedback)
        Draft202012Validator({'$ref':'#/$defs/events','$defs':schema['$defs']}).validate(session.events())
        discovery=json.loads(subprocess.check_output([sys.executable,'-m','figgyplot.review','protocol'],text=True))
        assert discovery['protocol']==1 and Path(discovery['skill']).is_file()
        assert discovery['event_schema'].endswith('#/$defs/events')
        skill=subprocess.check_output([sys.executable,'-m','figgyplot.review','skill'],text=True)
        assert 'claim' in skill and 'separate' in skill


def test_two_controllers_do_not_lose_comments_or_signal_twice(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    with Session(tmp_path,backend='webgpu') as session:
        create(session);session.start()
        def comment(index):
            other=Session.open(tmp_path);other.comment('plot','Note '+str(index))
        with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(comment,range(12)))
        session.submit('plot','request_changes')
        doc=session.feedback(session.events()[0]['work_id'])['round']['documents']['plot']
        assert {c['text'] for c in doc['comments']}=={'Note '+str(i) for i in range(12)}


def test_interrupted_manifest_write_recovers_previous_complete_state(tmp_path):
    with Session(tmp_path,backend='webgpu') as session:
        create(session);session.start();session.submit('plot','request_changes')
        old=(tmp_path/'manifest.json').read_bytes()
    # A terminated process can leave these unpublished files, but cannot change
    # the committed manifest. Reopen/access repairs them without an agent action.
    (tmp_path/'.writing-incomplete').write_bytes(b'{"protocol":')
    (tmp_path/'data'/'.writing-incomplete').write_bytes(b'partial array')
    candidate=tmp_path/('candidate-'+'a'*32+'-abandoned');candidate.mkdir();(candidate/'part').write_bytes(b'partial')
    resumed=Session.open(tmp_path)
    assert (tmp_path/'manifest.json').read_bytes()==old
    assert not candidate.exists() and not list(tmp_path.glob('.writing-*'))
    assert resumed.events()


def test_rename_followed_by_directory_sync_failure_is_retryable(tmp_path,monkeypatch):
    import figgyplot._review_store as storage
    class Handle:
        closed=False
        def close(self):self.closed=True
    with Session(tmp_path,backend='webgpu') as session:
        fig=create(session);session.start();handle=Handle();fig._windows.append(handle)
        original=storage._sync_directory;failed=False
        def sync(path):
            nonlocal failed
            # Fail after manifest rename, once the approved state is visible.
            current=json.loads((tmp_path/'manifest.json').read_text())
            if path==tmp_path and current['rounds'][-1]['documents']['plot']['approval'] is not None and not failed:
                failed=True;raise OSError('directory sync interrupted')
            original(path)
        with monkeypatch.context() as patch:
            patch.setattr(storage,'_sync_directory',sync)
            with pytest.raises(OSError,match='sync interrupted'):session.submit('plot','request_changes')
        assert not handle.closed
        approved=session.snapshot()['rounds'][-1]['documents']['plot']['approval']
        assert session.submit('plot','request_changes')==approved
        assert handle.closed and len(session.events())==1


def test_render_failure_retains_pending_work_and_explicit_supersession(tmp_path):
    source=tmp_path/'source.py';source.write_text("def build(session):\n    f=session.figure(id='plot')\n    f.axes[0].plot([0,1],[1,2],id='signal')\n")
    with Session(tmp_path/'cache',backend='webgpu',source={'entrypoint':str(source)}) as session:
        fig=create(session);session.start();fig.axes[0].set_title('Human title')
        session.submit('plot','request_changes');work=session.events()[0]['work_id']
        diff=session.feedback(work)['round']['documents']['plot']['approval']['changes']
        override={c['id']:'Reviewer requested replacing the old title' for c in diff}
        good_source=source.read_text()
        source.write_text(good_source+"\nfrom figgyplot import Figure\ndef failed_render(*args,**kwargs):\n    raise RuntimeError('render failed')\nFigure.to_png=failed_render\n")
        with pytest.raises(RuntimeError,match='render failed'):session.regenerate(work,superseded=override)
        assert 'render failed' in session.status['error']['message']
        assert session.feedback(work)['round']['documents']['plot']['approval']['settings']==fig.get_settings()
        source.write_text(good_source)
        assert session.regenerate(work,superseded=override)==2


def test_runner_preserves_recorded_cwd_imports_and_controller_state(tmp_path,monkeypatch):
    project=tmp_path/'project';project.mkdir();outside=tmp_path/'outside';outside.mkdir()
    (project/'local_values.py').write_text('VALUES=[2,3]\n')
    (project/'input.txt').write_text('Recovered data')
    source=project/'plots.py';source.write_text("from local_values import VALUES\nfrom pathlib import Path\ndef build(session):\n    f=session.figure(id='plot')\n    f.axes[0].plot([0,1],VALUES,id='signal')\n    f.axes[0].set_title(Path('input.txt').read_text())\n")
    monkeypatch.chdir(project)
    with Session(tmp_path/'cache',backend='webgpu',source={'entrypoint':str(source)}) as session:
        create(session);session.start();session.submit('plot','request_changes',comments='Read the local inputs')
        monkeypatch.chdir(outside);before=list(sys.path)
        assert session.regenerate(session.events()[0]['work_id'])==2
        assert Path.cwd()==outside and sys.path==before


def test_runner_timeout_preserves_approved_work(tmp_path):
    source=tmp_path/'plots.py';source.write_text('import time\ndef build(session):\n    time.sleep(10)\n')
    with Session(tmp_path/'cache',backend='webgpu',source={'entrypoint':str(source)}) as session:
        create(session);session.start();session.submit('plot','request_changes')
        work=session.events()[0]['work_id']
        with pytest.raises(subprocess.TimeoutExpired):session.regenerate(work,timeout=.1)
        assert session.events()[0]['work_id']==work
        assert session.status['error']['type']=='TimeoutExpired'

"""Readable feedback must account for every exact snapshot operation once."""
import copy
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest
from jsonschema import Draft202012Validator

from figgyplot.review import Session
from figgyplot._review_diff import preserved


def validate(value):
    import figgyplot.review as review
    schema = json.loads(Path(review.__file__).with_name('review-feedback-v1.schema.json').read_text())
    Draft202012Validator({'$ref':'#/$defs/'+value['view'], '$defs':schema['$defs']}).validate(value)


def all_ids(summary):
    return [cid for fig in summary['figures'] for obj in fig['objects'] for prop in obj['properties'] for cid in prop['operation_ids']]


def check_complete(session, work):
    full = session.feedback(work)
    small = session.feedback_summary(work)
    validate(small)
    expected = [c for d in full['round']['documents'].values() for c in d['approval']['changes']]
    scoped = [(fig['id'],cid) for fig in small['figures'] for obj in fig['objects'] for p in obj['properties'] for cid in p['operation_ids']]
    expected_scoped = {(fid,c['id']) for fid,d in full['round']['documents'].items() for c in d['approval']['changes']}
    assert len(scoped) == len(set(scoped)) == len(expected)
    assert set(scoped) == expected_scoped
    assert small['counts']['changes'] == len(expected)
    for fig in small['figures']:
        detail = session.feedback_details(work, fig['id'])
        validate(detail)
        assert detail['changes'] == full['round']['documents'][fig['id']]['approval']['changes']
    assert session.feedback(work) == full
    return full, small


def test_summary_groups_character_edits_and_comments_with_exact_detail(tmp_path):
    with Session(tmp_path, backend='webgpu') as session:
        line = session.figure(id='line');line.axes[0].plot([0,1],[1,2],id='signal')
        line.axes[0].set_title('Before')
        ring = session.figure(id='donut');ring.axes[0].donut([3,2,1])
        session.start();line.axes[0].set_title('AFTER!')
        session.comment('line','제목을 짧게',target='panel/main/chart_title')
        session.submit('line','accept')
        session.submit('donut','request_changes',comments='두 번째 조각의 색을 연하게')
        work = session.events()[0]['work_id']
        before = session.snapshot()
        full, small = check_complete(session,work)
        fig = next(f for f in small['figures'] if f['id']=='line')
        assert fig['disposition']=='accept' and fig['change_count']==6
        title, = fig['objects']
        assert title['target']=='panel/main/chart_title' and title['change_count']==6
        field, = title['properties']
        assert field['kind']=='rich_text' and field['text_changed'] and not field['formatting_changed']
        assert field['before']==dict(value='Before',truncated=False)
        assert field['after']==dict(value='AFTER!',truncated=False)
        assert title['comments'][0]['text']=='제목을 짧게'
        detail = session.feedback_details(work,'line',target=title['target'])
        validate(detail)
        obj, = detail['objects']
        assert detail['changes']==full['round']['documents']['line']['approval']['changes']
        assert obj['snapshots']['after']['/config/chart_title']==line.get_settings()['config']['chart_title']
        one = session.feedback_details(work,'line',change_id=field['operation_ids'][0])
        assert len(one['objects'])==1 and len(one['changes'])==1
        assert one['selection']['change_id']==field['operation_ids'][0]
        assert session.snapshot()==before
        assert len(json.dumps(small,ensure_ascii=False)) < len(json.dumps(full,ensure_ascii=False))/3


@pytest.mark.parametrize('change',['add','remove','move','revert','long_text','format'])
def test_summary_preserves_structural_and_rich_text_changes(tmp_path,change):
    with Session(tmp_path,backend='webgpu') as session:
        fig=session.figure(id='plot');ax=fig.axes[0];ax.plot([0,1],[1,2],id='signal')
        ax.text(.2,.3,'Keep',coords='ratio',id='note')
        ax.text(.6,.7,'Other',coords='ratio',id='other')
        ax.set_title('x'*200+'A' if change=='long_text' else 'Before')
        session.start()
        cfg=copy.deepcopy(fig.get_settings()['config'])
        if change=='add':ax.text(.4,.5,'Added',coords='ratio',id='added')
        elif change=='remove':
            cfg['annotations']['items'].pop(0);fig.configure(config={'annotations':cfg['annotations']})
            session.comment('plot','삭제한 주석에 대한 댓글',target='panel/main/annotation/note')
        elif change=='move':
            cfg['annotations']['items'].reverse();fig.configure(config={'annotations':cfg['annotations']})
        elif change=='revert':ax.set_title('Temporary');ax.set_title('Before')
        elif change=='long_text':ax.set_title('x'*200+'B')
        elif change=='format':
            cfg['chart_title']['text']['segments'][0]['bold']=True
            fig.configure(config={'chart_title':cfg['chart_title']})
        session.submit('plot','request_changes',comments='검토')
        work=session.events()[0]['work_id'];full,small=check_complete(session,work)
        objects=small['figures'][0]['objects']
        if change=='revert':assert not objects and small['counts']['changes']==0
        elif change in ('long_text','format'):
            title=next(o for o in objects if o['target']=='panel/main/chart_title')
            field,=title['properties']
            if change=='long_text':
                assert field['before']['truncated'] and field['after']['truncated'] and field['text_changed']
                assert len(field['after']['value'])==160
            else:assert not field['text_changed'] and field['formatting_changed']
        else:
            target='panel/main/annotation/'+('added' if change=='add' else 'other' if change=='move' else 'note')
            detail=session.feedback_details(work,'plot',target=target)
            assert detail['changes']
            if change=='remove':assert not detail['objects'][0]['snapshots']['after']
            if change=='move':assert any(c['op']=='move' for c in detail['changes'])
        for c in full['round']['documents']['plot']['approval']['changes']:
            assert preserved(c,fig.get_settings())


def test_summary_uses_stable_panel_overlay_series_and_annotation_targets(tmp_path):
    with Session(tmp_path,backend='webgpu') as session:
        fig=session.figure(id='plot',grid=[['left','right']])
        ax=fig.subplots['right'];ax.set_title('Before')
        ax.twinx(id='pressure').plot([0,1],[3,4],id='signal')
        fig.axes[0].text(.2,.3,'Note',coords='ratio',id='note')
        session.start()
        ax.set_title('AFTER!')
        fig.configure(series={'signal':{'render_type':{'Line':{'line':{'line_width':4}}}}})
        cfg=fig.get_settings()['config'];cfg['annotations']['items'][0]['kind']['Text']['anchor']['Ratio']['x']=.4
        cfg['subplots'][0]['config']['overlays'][0]['y_axis']['max']=8.
        fig.configure(config=cfg)
        fig.place('right',slot='left')
        session.submit('plot','request_changes')
        work=session.events()[0]['work_id'];_,small=check_complete(session,work)
        targets={v['target'] for v in small['figures'][0]['objects']}
        assert {'panel/right/chart_title','series/signal','panel/left/annotation/note','panel/right/overlay/pressure/axis_right'} <= targets
        for target in targets:
            assert session.feedback_details(work,'plot',target=target)['objects'][0]['target']==target


@pytest.mark.parametrize('family',['radial','categorical','boxplot','radar'])
def test_bounded_titles_and_annotations_use_editor_comment_ids(tmp_path,family):
    with Session(tmp_path,backend='webgpu') as session:
        fig=session.figure(id='plot');ax=fig.axes[0]
        if family=='radial':ax.donut([3,2,1])
        elif family=='categorical':ax.bar(['A','B'],[3,4])
        elif family=='boxplot':ax.boxplot([[1,2,3],[3,4,5]])
        else:ax.radar(['A','B','C'],[2,3,4])
        ax.set_title('Before');ax.text(.2,.3,'Note',coords='ratio',id='note')
        session.start();ax.set_title('AFTER!')
        state=fig.get_settings();state[family]['annotations']['items'][0]['kind']['Text']['anchor']['Ratio']['x']=.4
        fig.apply_settings(state)
        session.comment('plot','요소 댓글',target='bounded/annotation/note')
        session.submit('plot','request_changes')
        _,small=check_complete(session,session.events()[0]['work_id'])
        targets={o['target']:o for o in small['figures'][0]['objects']}
        assert targets['bounded/chart_title']['change_count']
        assert targets['bounded/annotation/note']['change_count'] and targets['bounded/annotation/note']['comments']


def test_summary_cli_details_errors_and_protocol_discovery(tmp_path):
    with Session(tmp_path/'cache with spaces',backend='webgpu') as session:
        fig=session.figure(id='plot');fig.axes[0].plot([0,1],[1,2])
        session.start()
        session.comment('plot','댓글만',target='panel/main/chart_title')
        session.submit('plot','request_changes')
        work=session.events()[0]['work_id']
        base=[sys.executable,'-m','figgyplot.review','feedback',str(session.cache_dir),work]
        run=lambda *args:json.loads(subprocess.check_output(base+list(args),text=True))
        assert run()==session.feedback(work)
        small=run('--summary');validate(small)
        assert small['counts']['changes']==0 and small['counts']['comments']==1
        detail=run('--figure','plot','--target','panel/main/chart_title');validate(detail)
        assert not detail['changes'] and detail['objects'][0]['snapshots']['after']
        for figure,target,change in [('missing',None,None),('plot','missing',None),('plot',None,'missing')]:
            with pytest.raises(ValueError):session.feedback_details(work,figure,target=target,change_id=change)
        for args in [('--target','missing'),('--summary','--figure','plot')]:
            result=subprocess.run(base+list(args),capture_output=True,text=True)
            assert result.returncode==2
        with pytest.raises(ValueError,match='Stale'):session.feedback_summary('stale')
        protocol=json.loads(subprocess.check_output([sys.executable,'-m','figgyplot.review','protocol'],text=True))
        assert protocol['summary_schema'].endswith('#/$defs/summary') and protocol['details_schema'].endswith('#/$defs/details')


@pytest.mark.parametrize('finish',[False,True])
def test_summary_keeps_unchanged_accepted_figures_and_lifecycle_intent(tmp_path,finish):
    with Session(tmp_path,backend='webgpu') as session:
        for fid in ['unchanged','reviewed']:
            fig=session.figure(id=fid);fig.axes[0].plot([0,1],[1,2],id='signal')
        session.start();session.submit('unchanged','accept')
        session.submit('reviewed','accept' if finish else 'request_changes',comments='저장 후 종료' if finish else '선 색상 변경',intent='finish' if finish else 'revise')
        work=session.events()[0]['work_id'];_,small=check_complete(session,work)
        assert small['intent']==('finish' if finish else 'revise')
        unchanged=next(f for f in small['figures'] if f['id']=='unchanged')
        assert unchanged['disposition']=='accept' and unchanged['objects']==[] and unchanged['change_count']==0
        reviewed=next(f for f in small['figures'] if f['id']=='reviewed')
        assert reviewed['comments'][0]['text']==('저장 후 종료' if finish else '선 색상 변경')


def test_equal_edit_ids_in_different_figures_are_queried_with_figure_scope(tmp_path):
    with Session(tmp_path,backend='webgpu') as session:
        figures=[]
        for fid in ['first','second']:
            fig=session.figure(id=fid);fig.axes[0].plot([0,1],[1,2]);fig.axes[0].set_title('Before');figures.append(fig)
        session.start()
        for fig in figures:fig.axes[0].set_title('AFTER!');session.submit(fig.id,'request_changes')
        work=session.events()[0]['work_id'];_,small=check_complete(session,work)
        assert small['counts']['changes']==12 and len(set(all_ids(small)))==6
        for fig in figures:
            detail=session.feedback_details(work,fig.id,change_id=small['figures'][0]['objects'][0]['properties'][0]['operation_ids'][0])
            assert detail['figure_id']==fig.id and len(detail['changes'])==1


def test_summary_reports_binary_data_changes_even_with_identical_bounds(tmp_path):
    with Session(tmp_path,backend='webgpu') as session:
        fig=session.figure(id='plot');fig.axes[0].plot([0,1],[1,2],id='signal')
        session.start()
        opening=fig.get_settings()
        column=fig.get_settings()['series'][0]['y_column']
        fig._native.remove_column(column)
        fig._native.upload_column(column,np.array([2.,1.]))
        assert fig.get_settings()==opening
        session.submit('plot','request_changes')
        work=session.events()[0]['work_id'];full,small=check_complete(session,work)
        assert small['figures'][0]['data_changed']
        assert small['counts']['changes']==0
        doc=full['round']['documents']['plot']
        assert doc['baseline_columns']!=doc['columns']
        assert doc['baseline_columns'][column]['shape']==doc['columns'][column]['shape']
        assert doc['baseline_columns'][column]['sha256']!=doc['columns'][column]['sha256']

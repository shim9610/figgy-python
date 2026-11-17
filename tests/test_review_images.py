"""Reference images belong to review comments, never chart Settings or text blobs."""
import base64
import copy
import io
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys

from PIL import Image
import pytest
from jsonschema import Draft202012Validator

from figgyplot.review import Session
from figgyplot._review_diff import persistent


def picture(format='PNG', color='#E69F00'):
    stream=io.BytesIO()
    Image.new('RGB',(96,64),color).save(stream,format=format)
    return stream.getvalue()


def figure(session):
    fig=session.figure(id='plot');fig.axes[0].plot([0,1],[2,3],id='signal')
    fig.axes[0].text(.3,.3,'Review me',coords='ratio',id='note')
    return fig


@pytest.mark.parametrize('format',['PNG','JPEG','WEBP'])
def test_images_normalize_to_durable_png_and_summary_exposes_viewable_paths(tmp_path,format):
    with Session(tmp_path/'cache',backend='webgpu') as session:
        fig=figure(session);session.start();before=fig.get_settings();revision=fig.revision
        ref=session.attach_image('plot',picture(format),name='배색 참고.'+format.lower())
        session.comment('plot','이 배색을 참고해 주세요',target='panel/main/annotation/note',attachments=[ref])
        session.submit('plot','request_changes')
        work=session.events()[0]['work_id']
        assert fig.get_settings()==before and fig.revision==revision
        raw=session.feedback(work);comment=raw['round']['documents']['plot']['comments'][0]
        image,=comment['attachments']
        assert image['mime_type']=='image/png' and (image['width'],image['height'])==(96,64)
        assert 'data' not in image and 'path' not in image
        with Image.open(session.cache_dir/image['file']) as decoded:
            assert decoded.format=='PNG';decoded.load()
        small=session.feedback_summary(work)
        obj,=small['figures'][0]['objects'];assert obj['target']=='panel/main/annotation/note'
        assert obj['change_count']==0
        exact=session.feedback_details(work,'plot',target=obj['target'])
        assert not exact['changes']
        for view in [small,exact]:
            attachment=view['figures'][0]['objects'][0]['comments'][0]['attachments'][0] if view['view']=='summary' else view['objects'][0]['comments'][0]['attachments'][0]
            assert Path(attachment['path'])==session.cache_dir/image['file']
            assert 'data:image' not in json.dumps(view) and len(json.dumps(view))<12000
        import figgyplot.review as review
        schema=json.loads(Path(review.__file__).with_name('review-feedback-v1.schema.json').read_text())
        Draft202012Validator(schema).validate(raw)
        for view in [small,exact]:Draft202012Validator({'$ref':'#/$defs/'+view['view'],'$defs':schema['$defs']}).validate(view)
        assert session.feedback(work)==raw
    with Session.open(tmp_path/'cache') as resumed:
        assert resumed.feedback_summary(work)['figures'][0]['objects'][0]['comments'][0]['attachments'][0]['path']==str(resumed.cache_dir/image['file'])


def test_image_only_general_and_target_comments_recover_and_remove_independently(tmp_path):
    with Session(tmp_path,backend='webgpu') as session:
        fig=figure(session);session.start();before=copy.deepcopy(fig.get_settings())
        raw=dict(data=base64.b64encode(picture()).decode(),name='Reference.png')
        session._set_comment_images('plot',[raw])
        canonical=session._review_state('plot')['attachments']
        session._set_comment_text('plot','Keep this palette')
        assert session._review_state('plot')['attachments']==canonical
        session._set_target_comments('plot',[dict(id='comment-1',target='panel/main/annotation/note',text='',attachments=canonical)])
        session._set_comment_text('plot','')
        session._set_comment_images('plot',[])
        assert session._review_state('plot')['attachments']==[]
        assert len(session._review_state('plot')['target_comments'][0]['attachments'])==1
        assert fig.get_settings()==before
        session.submit('plot','request_changes')
        work=session.events()[0]['work_id']
    with Session.open(tmp_path) as recovered:
        detail=recovered.feedback_details(work,'plot',target='panel/main/annotation/note')
        assert detail['objects'][0]['comments'][0]['text']==''
        assert Path(detail['objects'][0]['comments'][0]['attachments'][0]['path']).is_file()


def test_jpeg_orientation_matches_the_review_preview(tmp_path):
    from PIL import ImageOps
    source=Image.new('RGB',(96,64),'white')
    for x in range(48):
        for y in range(64):source.putpixel((x,y),(230,159,0))
    exif=Image.Exif();exif[274]=6
    payload=io.BytesIO();source.save(payload,format='JPEG',exif=exif)
    expected=ImageOps.exif_transpose(Image.open(io.BytesIO(payload.getvalue()))).convert('RGB')
    with Session(tmp_path,backend='webgpu') as session:
        figure(session);session.start()
        ref=session.attach_image('plot',payload.getvalue(),name='Portrait.jpg')
        assert (ref['width'],ref['height'])==(64,96)
        with Image.open(session.cache_dir/ref['file']) as actual:
            actual=actual.convert('RGB')
            assert actual.size==expected.size
            for point in [(10,10),(10,80)]:
                assert all(abs(a-b)<=3 for a,b in zip(actual.getpixel(point),expected.getpixel(point)))


def test_staged_upload_survives_collection_and_duplicate_images_share_one_file(tmp_path):
    with Session(tmp_path,backend='webgpu') as session:
        figure(session);session.start()
        ref=session.attach_image('plot',picture(),name='first.png')
        again=session.attach_image('plot',picture(),name='second.png')
        assert ref['file']==again['file']
        for _ in range(3):session.snapshot()
        assert (session.cache_dir/ref['file']).exists()
        assert len(list((tmp_path/'attachments').glob('*.png')))==1
        session._set_comment_images('plot',[ref,again]);assert len(session._review_state('plot')['attachments'])==1


@pytest.mark.parametrize('bad',['not an image','truncated_png','path_escape','bad_metadata','oversized_dimensions'])
def test_invalid_images_fail_without_mutating_review_comments(tmp_path,bad):
    with Session(tmp_path,backend='webgpu') as session:
        figure(session);session.start();before=session.snapshot()
        if bad=='path_escape':
            ref=session.attach_image('plot',picture());ref['file']='../outside.png';image=ref
        elif bad=='bad_metadata':
            ref=session.attach_image('plot',picture());ref['width']+=1;image=ref
        elif bad=='oversized_dimensions':
            image=io.BytesIO();Image.new('RGB',(8193,1)).save(image,format='PNG');image=image.getvalue()
        elif bad=='truncated_png':image=picture()[:30]
        else:image=bad.encode()
        comments=copy.deepcopy(session.snapshot()['rounds'][-1]['documents']['plot']['comments'])
        with pytest.raises((ValueError,OSError)):
            session._set_comment_images('plot',[image])
        assert session.snapshot()['rounds'][-1]['documents']['plot']['comments']==comments


def test_corrupt_image_is_detected_before_recovery_cleanup(tmp_path):
    with Session(tmp_path,backend='webgpu') as session:
        figure(session);session.start();session._set_comment_images('plot',[picture()])
        ref=session._review_state('plot')['attachments'][0]
        path=session.cache_dir/ref['file'];path.write_bytes(path.read_bytes()[:-1]+b'!')
        manifest=(tmp_path/'manifest.json').read_bytes()
        with pytest.raises(ValueError,match='image integrity'):
            Session.open(tmp_path)
        assert path.exists() and (tmp_path/'manifest.json').read_bytes()==manifest


def test_images_retained_on_failed_rebuild_then_collected_after_successor_commit(tmp_path):
    source=tmp_path/'plots.py'
    source.write_text("def build(s):\n    s.figure(id='plot').axes[0].plot([0,1],[2,3],id='signal')\n")
    with Session(tmp_path/'cache',backend='webgpu',source={'entrypoint':str(source)}) as session:
        runpy.run_path(str(source))['build'](session);session.start()
        session.comment('plot','Reference',attachments=[picture()]);session.submit('plot','request_changes')
        work=session.events()[0]['work_id'];path=Path(session.feedback_summary(work)['figures'][0]['comments'][0]['attachments'][0]['path'])
        original=source.read_text();source.write_text("def build(s):\n    raise RuntimeError('retry me')\n")
        with pytest.raises(RuntimeError,match='retry me'):session.regenerate(work)
        assert path.is_file() and session.status['state']=='ready'
        source.write_text(original);session.regenerate(work)
        assert not path.exists() and session.status['round']==2


def test_widget_upload_uses_binary_buffers_and_canonical_comment_refs(tmp_path):
    with Session(tmp_path,backend='webgpu') as session:
        fig=figure(session);session.start();widget=session.widget(fig);sent=[]
        widget.send=lambda message,**kwargs:sent.append(message)
        widget._command(widget,dict(action='review_image',request='upload-1',name='sample.jpg'),[memoryview(picture('JPEG'))])
        response=sent[-1];assert response['action']=='review_image_result' and response['request']=='upload-1'
        ref=response['attachment'];assert 'data' not in ref
        widget._command(widget,dict(action='review_comment',comments='',attachments=[ref],target_comments=[]),[])
        assert session._review_state('plot')['attachments']==[ref]
        before=fig.get_settings()
        widget._command(widget,dict(action='review_submit',disposition='request_changes',comments='',attachments=[ref],target_comments=[],revision=fig.revision),[])
        assert session.status['state']=='ready' and fig.get_settings()==before
        assert session.feedback_summary(session.events()[0]['work_id'])['figures'][0]['comments'][0]['attachments'][0]['path']

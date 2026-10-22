"""Actual key input must preserve live text, recovery and unrelated chart state."""
import copy
import json
import os
import shutil

import pytest

from figgyplot.review import Session
from native_input import set_clipboard
from test_radial_desktop import Inputs


def assert_rich_text(text, expected):
    # The renderer's Unicode parser represents U+00B2 as a styled "2".
    segments = text['segments']
    assert ''.join(s['text'] for s in segments) == expected.replace('²','2')
    if expected.endswith('²'):
        assert segments[-1]['text'] == '2' and segments[-1]['superscript']
        assert not segments[-1]['subscript']


@pytest.mark.skipif(not os.environ.get('DISPLAY') or not all(shutil.which(x) for x in ('xdotool','xclip','wmctrl')), reason='requires real X11 input')
@pytest.mark.parametrize('mode', ['inline', 'inspector', 'review', 'target'])
def test_native_typing_does_not_rebuild_unrelated_chart_work(tmp_path, monkeypatch, mode):
    monkeypatch.setenv('FIGGY_PROFILE_HOST', '1')
    with Session(cache_dir=tmp_path/'review', backend='native') as session:
        fig = session.figure(id='plot')
        ax = fig.axes[0]
        ax.plot([0,1,2], [0,2,1], id='signal')
        ax.text(.2,.4,'Original',coords='ratio',id='note')
        ax.text(.7,.7,'Keep this',coords='ratio',id='fixed')
        session.present()
        handle = session._handles['plot']
        inputs = Inputs(handle)
        try:
            # Keep the inspector open even for comment/inline drafts: typing
            # there must not reconstruct an unchanged document's object tree.
            inputs.click('properties')
            rect = json.loads(fig._native.bounds_json('annotation:note'))['rect']
            panel = inputs.info()['chart_panel']
            x = panel[0]+(rect[0]+rect[2]/2)*panel[2]/960
            y = panel[1]+(rect[1]+rect[3]/2)*panel[3]/600
            inputs.input_frame('mousemove','--window',inputs.wid,round(x),round(y))
            if mode == 'review':
                inputs.click('review_comments')
            elif mode == 'target':
                inputs.input_frame('click',3)
                key = next(k for k in inputs.info()['controls'] if k.startswith('review_target:'))
                inputs.click(key)
                inputs.click('review_target_text')
            elif mode == 'inline':
                inputs.input_frame('click','--repeat',2,'--delay',100,1)
                assert 'inline_text' in inputs.info()['controls']
            else:
                inputs.input_frame('click',1)
                inputs.click('annotation_text')
                inputs.key('ctrl+a')
            before = fig.get_settings()
            work = fig.info['host_work']
            builds = inputs.info()['property_catalog_builds']
            uploads = fig.info['column_uploads']
            typed = ''
            for char in 'Typing':
                inputs.input_frame('type','--clearmodifiers','--delay',0,char)
                typed += char
                if mode == 'inspector':
                    item = fig.get_settings()['config']['annotations']['items'][0]
                    assert_rich_text(item['kind']['Text']['text'], typed)
                else:
                    assert fig.get_settings() == before
            set_clipboard(' 한글 α²')
            inputs.key('ctrl+v')
            typed += ' 한글 α²'
            after_work = fig.info['host_work']
            for stage in ('annotation_view','native_axis_refresh','native_styles','apply_settings'):
                assert after_work.get(stage,{}).get('count',0) == work.get(stage,{}).get('count',0), (stage,work,after_work)
            if mode != 'inspector':
                assert after_work.get('native_navigation',{}).get('count',0) == work.get('native_navigation',{}).get('count',0)
                assert inputs.info()['property_catalog_builds'] == builds
            else:
                assert inputs.info()['property_catalog_builds']-builds <= len('Typing')+1
            assert fig.info['column_uploads'] == uploads
            if mode in ('inline','inspector'):
                inputs.key('Return')
                after = fig.get_settings()
                text = after['config']['annotations']['items'][0]['kind']['Text']['text']
                assert_rich_text(text, typed)
                expected = copy.deepcopy(before)
                expected['config']['annotations']['items'][0]['kind']['Text']['text']['segments'] = text['segments']
                assert after == expected
            elif mode == 'target':
                inputs.click('review_target_save')
                assert json.loads(handle.review_draft_json())['target_comments'][0]['text'] == typed
            else:
                assert json.loads(handle.review_draft_json())['comments'] == typed
            # UI comments and accepted SSOT remain durably recoverable after
            # polling; no debouncing/dropping of characters is used as a fix.
            session.poll()
            restored = Session.open(session.cache_dir)
            doc = restored.snapshot()['rounds'][-1]['documents']['plot']
            if mode in ('inline','inspector'):
                assert doc['draft'] == fig.get_settings()
                inputs.click('undo')
                old = fig.get_settings()['config']['annotations']['items'][0]
                assert_rich_text(old['kind']['Text']['text'], 'Original')
                inputs.click('redo')
                new = fig.get_settings()['config']['annotations']['items'][0]
                assert_rich_text(new['kind']['Text']['text'], typed)
            else:
                channel = 'ui_target' if mode == 'target' else 'ui'
                assert any(c['text'] == typed and c['channel'] == channel for c in doc['comments'])
                assert fig.get_settings() == before
            assert not inputs.info()['error']
            (tmp_path/'typing-work.json').write_text(json.dumps(dict(before=work,after=after_work),indent=2))
        finally:
            session.close()
            Inputs.pump()

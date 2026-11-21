"""A native review popup must occlude the selected chart's focus outline."""
import json
import os

import numpy as np
from PIL import ImageGrab

from figgyplot.review import Session
from test_radial_desktop import Inputs, requires_x11


@requires_x11
def test_review_popup_occludes_chart_focus_outline(tmp_path):
    panels = ['a', 'b', 'c', 'd', 'e', 'ch']
    with Session(tmp_path / 'cache', backend='native', review_font_size=18) as session:
        fig = session.figure(id='spectra', figsize=(16, 9), dpi=100,
                             grid=[panels[:3], panels[3:]])
        for name in panels:
            ax = fig.subplots[name].axes
            ax.plot([0, 1, 2], [0, 1, 0], id='data-' + name)
            ax.set_title(name)
        session.present()
        handle = session._handles['spectra']
        inputs = Inputs(handle)
        inputs.xdo('windowsize', inputs.wid, 1600, 1000)
        inputs.pump()
        stage = inputs.info()['chart_panel']
        inputs.input_frame('mousemove', '--window', inputs.wid,
                           round(stage[0] + stage[2] * .86),
                           round(stage[1] + stage[3] * .75))
        inputs.input_frame('click', 1)
        title = inputs.info()['decorations']['subplot_4:chart_title']
        inputs.input_frame('mousemove', '--window', inputs.wid,
                           round(title[0] + title[2] / 2),
                           round(title[1] + title[3] / 2))
        inputs.input_frame('click', 3)
        inputs.click('review_target:panel/ch/chart_title')
        inputs.click('review_target_text')
        inputs.input_frame('type', '--clearmodifiers', '--delay', 0,
                           'Review only this different wavelength band. Keep the '
                           'original wavelengths; label the true maximum in nm '
                           'and leave the other five panels unchanged.')
        inputs.pump()
        info = inputs.info()
        assert info['focused_panel'] == 'ch'
        text = info['controls']['review_target_text']
        # The right edge of the selected last panel crosses the popup's white
        # padding just below its text input. This used to paint blue on top of
        # the input, title bar and padding despite an opaque window background.
        stage = info['chart_panel']
        edge = round(stage[0] + stage[2] - 2)
        assert text[0] + 5 < edge < text[0] + text[2] - 5
        y = round(text[1] + text[3] + 4)
        # Obtain client-to-root coordinates from real pointer translation;
        # getwindowgeometry can include the WM frame offsets a second time.
        inputs.input_frame('mousemove', '--window', inputs.wid, 0, 0)
        pointer = dict(line.split('=', 1) for line in
                       inputs.xdo('getmouselocation', '--shell').splitlines())
        x0, y0 = int(pointer['X']), int(pointer['Y'])
        image = ImageGrab.grab(xdisplay=os.environ['DISPLAY'])
        image.save(tmp_path / 'review-popup.png')
        patch = np.asarray(image.convert('RGB'))[y0+y-1:y0+y+2, x0+edge-1:x0+edge+2]
        (tmp_path / 'popup-probe.json').write_text(json.dumps({
            'edge': edge, 'y': y, 'text': text, 'origin': [x0, y0], 'pixels': patch.tolist(),
        }))
        assert patch.shape == (3, 3, 3)
        assert patch.min() >= 245, 'Chart focus outline is painted over the opaque review popup'
        visible_y = round(stage[1] + stage[3] - 12)
        visible = np.asarray(image.convert('RGB'))[
            y0+visible_y-1:y0+visible_y+2, x0+edge-1:x0+edge+2]
        assert np.any(np.all(visible == [38, 99, 173], axis=-1)), \
            'The focus outline must remain visible outside the popup'
        inputs.click('review_target_save')
        draft = json.loads(handle.review_draft_json())
        assert draft['target_comments'][0]['target'] == 'panel/ch/chart_title'

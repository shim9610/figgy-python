"""The same independent feature expectations on the displayed WebGPU canvas."""
import io
import json
import os
from pathlib import Path

import numpy as np
from PIL import Image
import pytest

from browser_timing import DISPLAY_SETTLED
from feature_visual_assertions import FEATURES, assert_feature_image
from jupyter_harness import notebook


@pytest.mark.skipif(not os.environ.get('DISPLAY') or os.environ.get('FIGGY_TEST_JUPYTER')!='1',
                    reason='requires real Jupyter WebGPU')
@pytest.mark.parametrize('feature',FEATURES)
def test_displayed_feature_has_expected_geometry_and_colors(tmp_path,feature):
    source=f'''import sys
sys.path.insert(0,{str(Path(__file__).resolve().parent)!r})
import figgyplot as fg
from feature_visual_assertions import populate
fig=fg.Figure(backend='webgpu',figsize=(9.6,6),dpi=100)
populate(fig,{feature!r})
display(fig.widget())
'''
    with notebook(tmp_path/feature,source) as (page,execute):
        page.wait_for_function(DISPLAY_SETTLED,polling=100,timeout=180000)
        canvas=page.locator('.figgy-editor canvas')
        # Jupyter's fractional output origin otherwise produces a 601-row
        # enclosing screenshot for a 600px canvas. Align the entire widget to
        # the device grid; keep every canvas pixel and retain its exact size.
        alignment=canvas.evaluate('''c=>{
            const r=c.getBoundingClientRect(),dx=Math.ceil(r.x)-r.x,dy=Math.ceil(r.y)-r.y;
            c.closest('.figgy-editor').style.transform=`translate(${dx}px,${dy}px)`;
            return {before:[r.x,r.y,r.width,r.height],translation:[dx,dy]};
        }''')
        geometry=canvas.evaluate('c=>({css:[c.getBoundingClientRect().width,c.getBoundingClientRect().height],backing:[c.width,c.height],dpr:devicePixelRatio})')
        assert geometry==dict(css=[960,600],backing=[960,600],dpr=1),geometry
        png=canvas.screenshot(path=str(tmp_path/f'{feature}-canvas.png'))
        image=np.asarray(Image.open(io.BytesIO(png)).convert('RGBA'))
        assert_feature_image(image,feature)
        (tmp_path/'visual-contract.json').write_text(json.dumps(dict(feature=feature,geometry=geometry,alignment=alignment)))

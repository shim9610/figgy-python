"""Real-widget observations and controlled queue ordering for inline editing."""
import json
import re
from pathlib import Path

import figgyplot

ROOT = "document.querySelector('.figgy-editor').figgy"


def instrumented_source(folder):
    """Expose live state and a queue barrier without changing editing behavior."""
    source = (Path(figgyplot.__file__).parent / 'webgpu.js').read_text()
    source,count=re.subn(r'(inlineInput\.style\.fontSize=.*?;)',r'\1\n    globalThis.__figgyInlinePass={cssWidth:r.width,backingWidth:canvas.width,font:inlineInput.style.fontSize};',source,count=1)
    assert count==1
    marker = 'root.figgy={stats,diagnostics,'
    assert source.count(marker) == 1
    probe = """root.figgy={
      testRendererState:()=>enqueue(()=>snapshot(),true),
      testHoldQueue:()=>new Promise(started=>{let release;const gate=new Promise(r=>release=r);
        root.figgy.testReleaseQueue=release;enqueue(()=>{started();return gate;});}),
      stats,diagnostics,"""
    path = folder / 'inline-editor-observer.js'
    path.write_text(source.replace(marker, probe))
    return """from pathlib import Path
from figgyplot.widget import FigureWidget
class ObservedWidget(FigureWidget):
    _esm=Path(%r)
widget=ObservedWidget(fig)
fig._widgets.add(widget)
display(widget)
""" % str(path)


OBSERVE = """()=>{
    const root=document.querySelector('.figgy-editor'),canvas=root.querySelector('canvas');
    const rect=e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height};};
    const input=root.querySelector('[data-inline-text]');
    return {canvas:rect(canvas),backing:[canvas.width,canvas.height],viewport:[innerWidth,innerHeight,devicePixelRatio],
        box:rect(root.querySelector('.figgy-inline-text')),input:rect(input),hint:rect(root.querySelector('.figgy-inline-text small')),
        font:parseFloat(getComputedStyle(input).fontSize),value:input.value,
        focused:document.activeElement===input,selection:[input.selectionStart,input.selectionEnd],
        accepted:root.figgy.snapshot(),host:root.figgy.diagnostics()};
}"""


def wait_surface(page, viewport, dpr=1):
    # Size readiness is independent of font, containment and assertion success.
    page.wait_for_function("""([width,height,dpr])=>{
        const c=document.querySelector('.figgy-editor canvas'),r=c.getBoundingClientRect();
        return innerWidth===width&&innerHeight===height&&devicePixelRatio===dpr&&
            c.width===Math.round(r.width*dpr)&&c.height===Math.round(r.height*dpr);
    }""", arg=[*viewport, dpr], polling=20)


def observe(page, folder, label):
    state = page.evaluate(OBSERVE)
    state['renderer'] = page.evaluate(ROOT + '.testRendererState()')
    (folder / (label + '.json')).write_text(json.dumps(state, ensure_ascii=False, indent=2))
    return state


def assert_contained(state):
    c = state['canvas']
    for name in ('box', 'input', 'hint'):
        r = state[name]
        assert r['x'] >= c['x']-1, (name, state)
        assert r['y'] >= c['y']-1, (name, state)
        assert r['x']+r['width'] <= c['x']+c['width']+1, (name, state)
        assert r['y']+r['height'] <= c['y']+c['height']+1, (name, state)


def open_existing(page):
    entries = page.evaluate(ROOT + '.annotations()')
    rect = entries[0]['rect']
    point = page.locator('canvas').evaluate("""(c,p)=>{
        const r=c.getBoundingClientRect();return [r.x+p[0]*r.width/c.width,r.y+p[1]*r.height/c.height];
    }""", [rect[0]+8, rect[1]+6])
    page.mouse.dblclick(*point)
    entry = page.locator('[data-inline-text]')
    entry.wait_for(state='visible')
    return entry

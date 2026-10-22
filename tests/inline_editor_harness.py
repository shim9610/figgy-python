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


def annotation_point(page, index=0, offset=(8,6)):
    """Prepare geometry and map it through the live DOM in one browser operation.

    A protocol bounding box read separately can describe the preceding layout.
    The point must be visible and hit the canvas before sending real mouse input.
    """
    return page.evaluate("""async ({index,offset})=>{
        const root=document.querySelector('.figgy-editor'),c=root.querySelector('canvas');
        const entries=await root.figgy.annotations(),annotation=entries.find(v=>v.index===index)??entries[index];
        if(!annotation)throw Error('Missing annotation '+index);
        const r=c.getBoundingClientRect(),state=root.figgy.snapshot();
        const units=root.figgy.diagnostics().kind==='cartesian'?[c.width,c.height]:
            [state.config.chart_area.width,state.config.chart_area.height];
        const point=[r.x+(annotation.rect[0]+offset[0])*r.width/units[0],
            r.y+(annotation.rect[1]+offset[1])*r.height/units[1]];
        const result={annotation:annotation.rect,canvas:{x:r.x,y:r.y,width:r.width,height:r.height},
            units,point,viewport:[innerWidth,innerHeight],backing:[c.width,c.height]};
        if(point[0]<0||point[0]>=innerWidth||point[1]<0||point[1]>=innerHeight||
            document.elementFromPoint(...point)!==c)
            throw Error('Annotation input target is outside the visible canvas: '+JSON.stringify(result));
        return result;
    }""", {'index':index,'offset':list(offset)})


def open_existing(page):
    target = annotation_point(page)
    page.mouse.dblclick(*target['point'])
    entry = page.locator('[data-inline-text]')
    entry.wait_for(state='visible')
    return entry

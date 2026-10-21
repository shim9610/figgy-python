"""CI observations; never alter the measured assertions or schedule a redraw."""
import json
import time


SNAPSHOT = r"""() => {
    const root=document.querySelector('.figgy-editor');
    const read=e=>{
        if(!e)return null;
        const r=e.getBoundingClientRect(),s=getComputedStyle(e),p=e.offsetParent;
        return {tag:e.tagName,classes:e.className,rect:r.toJSON(),
            backing:[e.width,e.height],scroll:[e.scrollWidth,e.scrollHeight,e.scrollTop],
            offsetParent:p?{tag:p.tagName,classes:p.className,rect:p.getBoundingClientRect().toJSON()}:null,
            css:Object.fromEntries(['left','top','width','height','maxWidth','maxHeight','position','transform','overflow','boxSizing'].map(k=>[k,s[k]]))};
    };
    return {now:performance.now(),timeOrigin:performance.timeOrigin,
        viewport:[innerWidth,innerHeight,devicePixelRatio],active:document.activeElement?.outerHTML,
        resizeEvents:window.figgyLayoutResizeEvents,
        nodes:Object.fromEntries(['canvas','.figgy-stage','.figgy-inline-text','[data-inline-text]'].map(k=>[k,read(root?.querySelector(k))])),
        stats:root?.figgy?.stats,gpu:window.figgyGPUWork};
}"""


def arm_browser(page):
    # No getBoundingClientRect, RAF, ResizeObserver or renderer calls here.
    page.evaluate("""()=>{
        window.figgyLayoutResizeEvents=[];
        window.addEventListener('resize',()=>{
            window.figgyLayoutResizeEvents.push({now:performance.now(),viewport:[innerWidth,innerHeight]});
        });
    }""")


def browser_readings(page, entry, folder):
    """Keep the original two sequential Playwright measurements unchanged."""
    start=time.monotonic_ns()
    rect=entry.bounding_box()
    middle=time.monotonic_ns()
    canvas=page.locator('canvas').bounding_box()
    end=time.monotonic_ns()
    original_pass=rect['x']>=canvas['x']-1 and rect['x']+rect['width']<=canvas['x']+canvas['width']+1
    result={'original_pass':original_pass,'sequential':{'entry':rect,'canvas':canvas,
            'python_monotonic_ns':[start,middle,end]},'atomic_samples':[]}
    # All extra reads occur AFTER both original measurements. Do not use their
    # result to retry, replace, or relax the original assertion.
    try:
        for delay in (0,100,400):
            if delay:page.wait_for_timeout(delay)
            result['atomic_samples'].append(page.evaluate(SNAPSHOT))
    except Exception as error:
        result['probe_error']=repr(error)
    (folder/'inline-layout-probe.json').write_text(json.dumps(result,default=str,indent=2))
    print('FIGGY LAYOUT PROBE '+json.dumps(result,default=str),flush=True)
    return rect,canvas


def native_sample(inputs, samples, label):
    samples.append({'label':label,'python_monotonic_ns':time.monotonic_ns(),'info':inputs.info()})


def save_native(inputs, samples, folder):
    """Called in finally after the original assertion, including failure paths."""
    try:
        native_sample(inputs,samples,'finally_before_pump')
        for n in range(3):
            inputs.pump()
            native_sample(inputs,samples,f'finally_after_pump_{n}')
        (folder/'native-layout-probe.json').write_text(json.dumps(samples,default=str,indent=2))
        summary=[]
        for sample in samples:
            info=sample['info']
            summary.append({'label':sample['label'],'python_monotonic_ns':sample['python_monotonic_ns'],
                **{k:info.get(k) for k in ('surface_frames','selected','revision','scale_factor','surface_size','error')},
                'frames':info.get('layout_probe',[])[-6:]})
        print('FIGGY NATIVE LAYOUT PROBE '+json.dumps(summary,default=str),flush=True)
        from PIL import ImageGrab
        import os
        ImageGrab.grab(xdisplay=os.environ['DISPLAY']).save(folder/'native-layout-probe.png')
    except Exception as error:
        print('FIGGY NATIVE LAYOUT PROBE ERROR '+repr(error),flush=True)

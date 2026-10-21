"""Opt-in passive timings; no extra GPU fences, frames or screenshot retries."""
import json
import os
from pathlib import Path
import time

TIMING_INIT = r"""(() => {
    const started=performance.now(),limit=512,events=[],submissions=[],fences=[],pipelines=[],samples=[],longTasks=[];
    const queues=new WeakMap(),pendingRAF=new Map(),operations=new Map();
    let queueId=0,fenceId=0,stopped=false,lastSample=started,lastGeometry=null,lastRAFStamp=null;
    const raf={requested:0,called:0,cancelled:0,frames:0,lastAt:null,maxGapMs:0};
    const timer={samples:0,maxGapMs:0,geometryChanges:0};
    const push=(list,value)=>{list.push(value);if(list.length>limit)list.shift();};
    const record=(kind,details={})=>{if(!stopped)push(events,{t:performance.now(),kind,...details});};
    function queueState(queue){let q=queues.get(queue);if(!q){q={id:++queueId,submitted:0,lastSubmit:null};queues.set(queue,q);}return q;}
    function geometry(){
        const root=document.querySelector('.figgy-editor'),canvas=root?.querySelector('canvas');
        if(!root||!canvas)return null;
        const r=root.getBoundingClientRect(),c=canvas.getBoundingClientRect();
        return {root:[r.x,r.y,r.width,r.height],canvas:[canvas.width,canvas.height,c.x,c.y,c.width,c.height],
            visibility:document.visibilityState,focused:document.hasFocus(),status:root.querySelector('[data-status]')?.textContent};
    }
    const snapshot=()=>({version:1,started,now:performance.now(),raf:{...raf,pending:pendingRAF.size},timer:{...timer},geometry:geometry(),
        events:[...events],submissions:[...submissions],fences:[...fences],pipelines:[...pipelines],samples:[...samples],longTasks:[...longTasks]});
    window.figgyTiming={snapshot,mark:(stage,details={})=>record('mark',{stage,...details}),stop:()=>{stopped=true;clearInterval(heartbeat);for(const p of observers)p.disconnect();}};
    const observers=[];
    if(typeof PerformanceObserver!=='undefined')for(const type of ['longtask','long-animation-frame']){
        try{const observer=new PerformanceObserver(list=>{for(const e of list.getEntries())push(longTasks,{type:e.entryType,t:e.startTime,durationMs:e.duration,
            blockingDuration:e.blockingDuration,renderStart:e.renderStart,styleAndLayoutStart:e.styleAndLayoutStart});});observer.observe({type,buffered:true});observers.push(observer);}catch(_){}
    }
    const heartbeat=setInterval(()=>{
        const now=performance.now(),g=geometry(),key=JSON.stringify(g?.root),gap=now-lastSample;lastSample=now;
        timer.samples++;timer.maxGapMs=Math.max(timer.maxGapMs,gap);
        const changed=lastGeometry!==null&&key!==lastGeometry;if(changed)timer.geometryChanges++;lastGeometry=key;
        push(samples,{t:now,gapMs:gap,rafAgeMs:raf.lastAt===null?null:now-raf.lastAt,geometry:g});
        if(changed||gap>250)record('heartbeat',{gapMs:gap,changed,geometry:g});
    },100);
    if(typeof window.requestAnimationFrame==='function'){
        const request=window.requestAnimationFrame,cancel=window.cancelAnimationFrame;
        window.requestAnimationFrame=function(callback){
            const requestedAt=performance.now();raf.requested++;let id;
            id=request.call(this,function(stamp){
                pendingRAF.delete(id);const now=performance.now();raf.called++;
                if(lastRAFStamp!==stamp){const gap=raf.lastAt===null?0:now-raf.lastAt;raf.frames++;raf.maxGapMs=Math.max(raf.maxGapMs,gap);raf.lastAt=now;lastRAFStamp=stamp;if(gap>250)record('raf-gap',{gapMs:gap});}
                if(now-requestedAt>250)record('raf-delayed',{delayMs:now-requestedAt});
                return callback.call(this,stamp);
            });pendingRAF.set(id,requestedAt);return id;
        };
        window.cancelAnimationFrame=function(id){raf.cancelled++;pendingRAF.delete(id);return cancel.call(this,id);};
    }
    const host=window.__figgyTrace;
    window.__figgyTrace=function(stage,details={}){
        const result=host?.apply(this,arguments),now=performance.now();
        if(stage==='queue.started')operations.set(details.operationId,{t:now,stage:null});
        const op=operations.get(details.operationId);
        if(stage==='queue.finished'&&op){record('host-operation',{operationId:details.operationId,durationMs:now-op.t});operations.delete(details.operationId);}
        if(/^(display|surface|request|response|ready_frame|export)\./.test(stage)){const {kind:chartKind,...rest}=details;record('host-stage',{stage,chartKind,...rest});}
        return result;
    };
    if(typeof GPUQueue!=='undefined'){
        const submit=GPUQueue.prototype.submit,done=GPUQueue.prototype.onSubmittedWorkDone;
        GPUQueue.prototype.submit=function(...args){
            const q=queueState(this),start=performance.now();
            try{const value=submit.apply(this,args);const at=performance.now(),canvas=document.querySelector('.figgy-editor canvas');
                q.lastSubmit={queue:q.id,submission:++q.submitted,t:start,cpuMs:at-start,canvas:canvas?[canvas.width,canvas.height]:null};push(submissions,{...q.lastSubmit});return value;
            }catch(error){record('submit-error',{queue:q.id,error:String(error)});throw error;}
        };
        GPUQueue.prototype.onSubmittedWorkDone=function(...args){
            const q=queueState(this),start=performance.now(),submission=q.lastSubmit?{...q.lastSubmit}:null;
            const entry={id:++fenceId,queue:q.id,submission:submission?.submission,canvas:submission?.canvas,t:start,status:'pending'};push(fences,entry);
            let promise;try{promise=done.apply(this,args);}catch(error){entry.status='threw';entry.error=String(error);throw error;}
            return promise.then(value=>{const end=performance.now();Object.assign(entry,{status:'completed',end,waitMs:end-start,submitToCompleteMs:submission?end-submission.t:null});return value;},error=>{
                Object.assign(entry,{status:'rejected',end:performance.now(),error:String(error)});throw error;});
        };
    }
    if(typeof GPUDevice!=='undefined')for(const name of ['createShaderModule','createRenderPipeline','createRenderPipelineAsync','createComputePipeline','createComputePipelineAsync']){
        const original=GPUDevice.prototype[name];if(typeof original!=='function')continue;
        GPUDevice.prototype[name]=function(...args){
            const start=performance.now(),descriptor=args[0]??{},entry={name,t:start,label:descriptor.label??'',shaderBytes:descriptor.code?.length,
                entry:descriptor.fragment?.entryPoint??descriptor.compute?.entryPoint,samples:descriptor.multisample?.count??1,status:'started'};push(pipelines,entry);
            let result;try{result=original.apply(this,args);}catch(error){Object.assign(entry,{status:'threw',cpuMs:performance.now()-start,error:String(error)});throw error;}
            entry.cpuMs=performance.now()-start;
            if(name.endsWith('Async'))return result.then(value=>{Object.assign(entry,{status:'completed',elapsedMs:performance.now()-start});return value;},error=>{Object.assign(entry,{status:'rejected',elapsedMs:performance.now()-start,error:String(error)});throw error;});
            entry.status='completed';entry.elapsedMs=entry.cpuMs;return result;
        };
    }
    record('timing-started',{timeOrigin:performance.timeOrigin});
})()"""


def screenshot_editor(page, path):
    """Measure the existing screenshot call without changing its timeout or waits."""
    if os.environ.get('FIGGY_TEST_TIMING') != '1':
        return page.locator('.figgy-editor').screenshot(path=str(path))
    path = Path(path)
    started = time.monotonic()
    outcome = 'failed'
    try:
        page.evaluate("name=>window.figgyTiming?.mark('screenshot.start',{name})", path.name)
    except Exception:
        pass
    try:
        result = page.locator('.figgy-editor').screenshot(path=str(path))
        outcome = 'passed'
        return result
    finally:
        elapsed = (time.monotonic()-started)*1000
        try:
            timing = page.evaluate("data=>{window.figgyTiming?.mark('screenshot.end',data);return window.figgyTiming?.snapshot();}",
                                   {'name': path.name, 'outcome': outcome, 'elapsedMs': elapsed})
            path.with_suffix('.timing.json').write_text(json.dumps({'screenshot_ms': elapsed, 'outcome': outcome, 'timing': timing}))
        except Exception:
            # Collection must preserve the screenshot's original exception.
            pass


def timing_summary(timing):
    """Deduplicate fences observing the same submission; preserve pending work."""
    now=timing['now'];unique={}
    for fence in timing.get('fences',[]):
        key=(fence.get('queue'),fence.get('submission'))
        entry=unique.setdefault(key,{'queue':key[0],'submission':key[1],'canvas':fence.get('canvas'),'status':'pending','waitMs':0})
        if fence['status']=='completed':
            entry['status']='completed'
            entry['submitToCompleteMs']=max(entry.get('submitToCompleteMs',0),fence.get('submitToCompleteMs') or 0)
        entry['waitMs']=max(entry['waitMs'],fence.get('waitMs',now-fence['t']))
    samples=timing.get('samples',[]);stable_ms=0
    if samples:
        latest=samples[-1].get('geometry')
        for sample in reversed(samples):
            if sample.get('geometry')!=latest:break
            stable_ms=now-sample['t']
    return {'now':now,'raf':timing.get('raf'),'timer':timing.get('timer'),'stableGeometryMs':stable_ms,
            'submissions':list(unique.values()),'submitCpuMaxMs':max((s['cpuMs'] for s in timing.get('submissions',[])),default=0),
            'pipelines':timing.get('pipelines',[]),'longTasks':timing.get('longTasks',[])[-10:],
            'marks':[e for e in timing.get('events',[]) if e.get('kind')=='mark']}

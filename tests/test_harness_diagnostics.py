"""Diagnostic observers preserve GPU behavior and survive failed WASM snapshots."""
import json
import shutil
import subprocess

import pytest

from jupyter_harness import GPU_TRACE_INIT, DIAGNOSTIC_SNAPSHOT, save_browser_diagnostics


def run_node(script):
    node = shutil.which('node')
    if node is None:
        pytest.skip('Node is required for the JavaScript observer contract')
    result = subprocess.run([node, '--input-type=module'], input=script, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr


def test_gpu_observers_keep_calls_results_errors_and_bounded_history():
    run_node(r"""
import assert from 'node:assert/strict';
globalThis.window=globalThis;
const canvas={width:960,height:600};
globalThis.document={querySelector:()=>canvas};
const counts={submit:0,fence:0,map:0};
let rejectFence=false,rejectMap=false,resolveFence;
const failure=new Error('original GPU failure');
class Queue {
 submit(){counts.submit++;return 'submitted';}
 onSubmittedWorkDone(){counts.fence++;return rejectFence?Promise.reject(failure):new Promise(resolve=>{resolveFence=resolve;});}
}
class Buffer {
 constructor(){this.size=256;this.label='readback';}
 mapAsync(){counts.map++;return rejectMap?Promise.reject(failure):Promise.resolve('mapped');}
 getMappedRange(){return 'range';}unmap(){return 'unmapped';}
}
globalThis.GPUQueue=Queue;globalThis.GPUBuffer=Buffer;
const queue=new Queue(),device={queue,label:'device',features:new Set(['timestamp-query']),addEventListener(){},lost:new Promise(()=>{})};
const adapter={info:{vendor:'test-vendor',architecture:'test-arch',isFallbackAdapter:false},requestDevice:async()=>device};
Object.defineProperty(globalThis,'navigator',{value:{gpu:{requestAdapter:async()=>adapter}}});
""" + GPU_TRACE_INIT + r"""
const actual=await (await navigator.gpu.requestAdapter()).requestDevice();
assert.equal(actual,device);assert.deepEqual(counts,{submit:0,fence:0,map:0});
assert.equal(queue.submit([]),'submitted');
const completion=queue.onSubmittedWorkDone();
assert.equal(figgyGPUWork.completed,0);assert.equal(figgyBrowserTrace.queues[0].pendingFences,1);
resolveFence('done');assert.equal(await completion,'done');
assert.deepEqual(figgyGPUWork,{submitted:1,completed:1,completedCanvas:[960,600]});
assert.equal(figgyBrowserTrace.queues[0].pendingFences,0);
const buffer=new Buffer();assert.equal(await buffer.mapAsync(1),'mapped');
assert.equal(buffer.getMappedRange(),'range');assert.equal(buffer.unmap(),'unmapped');
rejectFence=true;rejectMap=true;
await assert.rejects(queue.onSubmittedWorkDone(),error=>error===failure);
await assert.rejects(buffer.mapAsync(1),error=>error===failure);
assert.deepEqual(counts,{submit:1,fence:2,map:2});
for(const kind of ['adapter-ready','device-ready','submit','fence-start','fence-end','fence-error','map-start','map-end','map-error','getMappedRange','unmap'])
 assert.ok(figgyBrowserTrace.events.some(e=>e.kind===kind),kind);
assert.equal(figgyBrowserTrace.adapters[0].vendor,'test-vendor');
__figgyTrace('request.received',{requestId:'request-1'});
for(let i=0;i<450;i++)__figgyTrace('queue.finished',{index:i});
assert.equal(figgyBrowserTrace.events.length,400);assert.ok(figgyBrowserTrace.dropped>0);
assert.equal(figgyBrowserTrace.events.at(-1).index,449);
assert.equal(figgyBrowserTrace.hostStages.at(-1).requestId,'request-1');
__figgyTrace('edit.post',{sequence:2,revision:7});
for(let i=0;i<450;i++)__figgyTrace('queue.finished',{index:i});
assert.equal(figgyBrowserTrace.hostStages.at(-1).stage,'edit.post');
assert.equal(figgyBrowserTrace.hostStages.at(-1).revision,7);
for(let i=0;i<120;i++)__figgyTrace('prepare.completed',{requestId:i});
assert.equal(figgyBrowserTrace.hostStages.length,100);assert.equal(figgyBrowserTrace.hostStages.at(-1).requestId,119);
assert.ok(figgyBrowserTrace.events.every(e=>Number.isFinite(e.t)));
assert.deepEqual(counts,{submit:1,fence:2,map:2});
""")


def test_snapshot_borrow_failure_keeps_independent_host_gpu_and_gate_metadata():
    run_node(r"""
import assert from 'node:assert/strict';
globalThis.window=globalThis;globalThis.devicePixelRatio=1;
const canvas={width:960,height:600,getBoundingClientRect:()=>({x:0,y:0,width:960,height:600})};
const f={stats:{frames:3},diagnostics:()=>({phase:'prepare',pendingFrame:true}),snapshot(){throw Error('already borrowed');}};
const root={figgy:f,querySelector:s=>s==='canvas'?canvas:{textContent:'Preparing'}};
globalThis.document={querySelector:()=>root,visibilityState:'visible',hasFocus:()=>true};
window.figgyGPUWork={submitted:4,completed:3};
window.figgyBrowserTrace={events:[{kind:'fence-start',t:1}],queues:[{pendingFences:1}]};
window.figgyPreparationGate={armedAt:1,entered:true,enteredAt:2,releasedAt:8};
const collect=(""" + DIAGNOSTIC_SNAPSHOT + r""");const result=collect();
assert.match(result.state_error,/already borrowed/);assert.equal(result.host.phase,'prepare');
assert.equal(result.gpu_work.submitted,4);assert.equal(result.preparation_gate.durationMs,7);
assert.equal(result.canvas.width,960);assert.equal(result.status,'Preparing');
""")


@pytest.mark.parametrize('outcome', ['passed', 'failed'])
def test_diagnostic_artifact_saved_when_page_collection_fails(tmp_path, capsys, outcome):
    class BrokenPage:
        def evaluate(self, script):
            raise RuntimeError('page unavailable')
    original = ValueError('original test failure')
    with pytest.raises(ValueError, match='original test failure'):
        try:
            raise original
        finally:
            save_browser_diagnostics(BrokenPage(), tmp_path, {'version': '156'}, outcome, [], [])
    saved = json.loads((tmp_path/'diagnostics.json').read_text())
    assert saved['outcome'] == outcome
    assert saved['browser']['version'] == '156'
    assert 'page unavailable' in saved['collection_error']
    assert (tmp_path/'widget-state.json').exists()
    assert ('FIGGY FAILURE DIAGNOSTICS' in capsys.readouterr().out) == (outcome == 'failed')


def test_timing_observers_preserve_gpu_and_frame_calls_without_adding_work():
    from browser_timing import TIMING_INIT
    run_node(r"""
import assert from 'node:assert/strict';
globalThis.window=globalThis;
const rect={x:0,y:0,width:960,height:600};
const canvas={width:960,height:600,getBoundingClientRect:()=>({...rect})};
const root={getBoundingClientRect:()=>({...rect}),querySelector:s=>s==='canvas'?canvas:{textContent:'Ready'}};
globalThis.document={querySelector:s=>s==='.figgy-editor'?root:canvas,visibilityState:'visible',hasFocus:()=>true};
let tick,frame,frameThis,resolveFence;
const counts={submit:0,fence:0,pipeline:0,raf:0,cancel:0};
globalThis.setInterval=callback=>{tick=callback;return 1;};globalThis.clearInterval=()=>{};
globalThis.requestAnimationFrame=function(callback){counts.raf++;frame=callback;return 7;};
globalThis.cancelAnimationFrame=function(id){assert.equal(id,7);counts.cancel++;};
const result={},failure=new Error('original failure');
class Queue {
 submit(){assert.equal(this,queue);counts.submit++;return result;}
 onSubmittedWorkDone(){assert.equal(this,queue);counts.fence++;return new Promise(resolve=>resolveFence=resolve);}
}
class Device {
 createRenderPipeline(descriptor){counts.pipeline++;if(descriptor.fail)throw failure;return result;}
 createRenderPipelineAsync(){counts.pipeline++;return Promise.resolve(result);}
}
globalThis.GPUQueue=Queue;globalThis.GPUDevice=Device;
const queue=new Queue(),device=new Device();
let hostCalls=0;window.__figgyTrace=()=>hostCalls++;
""" + TIMING_INIT + r"""
assert.deepEqual(counts,{submit:0,fence:0,pipeline:0,raf:0,cancel:0});
assert.equal(queue.submit([]),result);
const fence=queue.onSubmittedWorkDone();assert.equal(figgyTiming.snapshot().fences[0].status,'pending');
resolveFence(result);assert.equal(await fence,result);
assert.equal(device.createRenderPipeline({label:'radial'}),result);
assert.equal(await device.createRenderPipelineAsync({label:'radial async'}),result);
assert.throws(()=>device.createRenderPipeline({fail:true}),e=>e===failure);
const id=window.requestAnimationFrame(function(stamp){assert.equal(stamp,12);frameThis=this;});assert.equal(id,7);
const context={};frame.call(context,12);assert.equal(frameThis,context);
window.cancelAnimationFrame(id);tick();tick();rect.x=1;tick();
__figgyTrace('queue.started',{operationId:1});__figgyTrace('queue.finished',{operationId:1});
__figgyTrace('display.submitted',{kind:'radial'});figgyTiming.mark('screenshot.start',{name:'plot.png'});
const stats=figgyTiming.snapshot();
assert.equal(hostCalls,3);assert.ok(stats.events.some(e=>e.kind==='host-stage'&&e.chartKind==='radial'));assert.equal(stats.events.at(-1).stage,'screenshot.start');assert.equal(stats.raf.frames,1);assert.equal(stats.raf.pending,0);
assert.equal(stats.timer.geometryChanges,1);assert.equal(stats.fences[0].status,'completed');
assert.equal(stats.submissions.length,1);assert.equal(stats.pipelines.length,3);
assert.deepEqual(counts,{submit:1,fence:1,pipeline:3,raf:1,cancel:1});
figgyTiming.stop();
""")


def test_timing_summary_deduplicates_fences_and_reports_pending_submissions():
    from browser_timing import timing_summary
    result=timing_summary({'now':1000,'fences':[
        {'id':1,'queue':1,'submission':2,'canvas':[960,600],'t':100,'status':'completed','waitMs':400,'submitToCompleteMs':450},
        {'id':2,'queue':1,'submission':2,'canvas':[960,600],'t':110,'status':'completed','waitMs':390,'submitToCompleteMs':450},
        {'id':3,'queue':1,'submission':3,'canvas':[699,437],'t':600,'status':'pending'},
    ],'samples':[{'t':200,'geometry':{'root':[0,0,960,600]}},{'t':500,'geometry':{'root':[0,0,699,437]}},{'t':900,'geometry':{'root':[0,0,699,437]}}]})
    assert len(result['submissions'])==2
    assert result['submissions'][0]['submitToCompleteMs']==450
    assert result['submissions'][1]['status']=='pending' and result['submissions'][1]['waitMs']==400
    assert result['stableGeometryMs']==500


@pytest.mark.parametrize('failure', [False, True])
def test_timed_screenshot_keeps_original_result_deadline_and_exception(tmp_path, monkeypatch, failure):
    from browser_timing import screenshot_editor
    monkeypatch.setenv('FIGGY_TEST_TIMING','1')
    original=TimeoutError('original screenshot timeout')
    calls=[]
    class Page:
        def wait_for_function(self,script,**kwargs):
            from browser_timing import DISPLAY_SETTLED
            assert script==DISPLAY_SETTLED
            assert kwargs=={'polling':100,'timeout':180000}
        def evaluate(self,*args):
            raise RuntimeError('diagnostics unavailable')
        def locator(self,selector):
            assert selector=='.figgy-editor';return self
        def screenshot(self,**kwargs):
            calls.append(kwargs)
            if failure:raise original
            return b'png'
    if failure:
        with pytest.raises(TimeoutError) as caught:screenshot_editor(Page(),tmp_path/'plot.png')
        assert caught.value is original
    else:assert screenshot_editor(Page(),tmp_path/'plot.png')==b'png'
    assert calls==[{'path':str(tmp_path/'plot.png')}]


def test_capture_requires_current_surface_completion_and_propagates_display_errors():
    from browser_timing import DISPLAY_SETTLED
    run_node(r"""
import assert from 'node:assert/strict';
globalThis.devicePixelRatio=2;
let state={busy:0,queued:0,dirty:false,frame_pending:false,edit_inflight:null,edit_pending:false};
const canvas={width:960,height:600,getBoundingClientRect:()=>({width:480,height:300})};
globalThis.document={querySelector:()=>({figgy:{diagnostics:()=>state},querySelector:()=>canvas})};
const settled=("""+DISPLAY_SETTLED+r""");
assert.equal(settled(),true);
for(const flag of ['busy','queued','dirty','frame_pending','edit_inflight','edit_pending']){
 state[flag]=1;assert.equal(settled(),false,flag);state[flag]=0;
}
canvas.width=699;assert.equal(settled(),false);canvas.width=960;
state.frame_error='device lost';assert.throws(settled,/device lost/);state.frame_error=null;
state.disposed=true;assert.throws(settled,/disposed/);
""")


def test_property_draft_rebase_preserves_unrelated_values_and_rejects_conflicts():
    from pathlib import Path
    source=(Path(__file__).resolve().parents[1]/'python'/'figgyplot'/'webgpu.js').read_text()+'\nexport {propertyDraft,rebasePropertyDraft};'
    run_node("const source="+json.dumps(source)+";\n"+r"""
import assert from 'node:assert/strict';
const {propertyDraft,rebasePropertyDraft}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
const base={identity:{figure:'figure-a',panels:[{id:'main',overlays:[]}]},config:{digits:7,grid:false},series:[{id:'a',width:1},{id:'b',width:1}],values:[1e-200,1e200]};
const requested=structuredClone(base);requested.config.digits=2;
const original=structuredClone(base),draft=propertyDraft(base,requested);
const accepted=structuredClone(base);accepted.config.grid=true;accepted.values=[2e-200,2e200];
const saved=structuredClone(accepted),result=rebasePropertyDraft(draft,accepted);
assert.equal(result.config.digits,2);assert.equal(result.config.grid,true);
assert.deepEqual(result.values,[2e-200,2e200]);
assert.deepEqual(base,original);assert.deepEqual(accepted,saved);
const conflict=structuredClone(accepted);conflict.config.digits=4;
assert.equal(rebasePropertyDraft(draft,conflict),null);
const replaced=structuredClone(accepted);replaced.identity.figure='figure-b';
assert.equal(rebasePropertyDraft(draft,replaced),null);
const moved=structuredClone(accepted);moved.identity.panels[0].id='other';
assert.equal(rebasePropertyDraft(draft,moved),null);
const already=structuredClone(accepted);already.config.digits=2;
assert.deepEqual(rebasePropertyDraft(draft,already),already);
const arrayEdit=structuredClone(base);arrayEdit.series[0].width=2;
const reordered=structuredClone(base);reordered.series.reverse();
assert.equal(rebasePropertyDraft(propertyDraft(base,arrayEdit),reordered),null);
const deleted=structuredClone(base);delete deleted.config.digits;
const deletion=rebasePropertyDraft(propertyDraft(base,deleted),accepted);
assert.equal(Object.hasOwn(deletion.config,'digits'),false);assert.equal(deletion.config.grid,true);
const inserted=structuredClone(base);inserted.config.newStyle={alpha:0.25};
assert.deepEqual(rebasePropertyDraft(propertyDraft(base,inserted),accepted).config.newStyle,{alpha:0.25});
""")

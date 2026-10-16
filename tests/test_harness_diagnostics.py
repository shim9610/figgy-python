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

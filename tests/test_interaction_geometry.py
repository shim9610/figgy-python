"""Accepted annotation geometry must not depend on display-GPU completion."""
import json

import pytest

from jupyter_harness import notebook
from test_interaction_parity import NEEDS_UI, ROOT


@pytest.mark.skipif(NEEDS_UI, reason='requires a live notebook WebGPU surface')
def test_cartesian_annotation_geometry_refreshes_while_display_gpu_is_pending(tmp_path):
    source = """import json
import figgyplot as fg
fig,ax=fg.subplots(backend='webgpu')
ax.plot([0,1],[1,2],id='signal')
ax.text(.2,.2,'Probe',coords='ratio',id='probe')
display(fig.widget())
"""
    with notebook(tmp_path/'geometry-during-display', source) as (page, execute):
        before = page.evaluate(ROOT+'.annotations()')[0]['rect']
        uploads = page.evaluate(ROOT+'.stats.column_uploads')
        page.evaluate("""()=>{
            const prototype=GPUQueue.prototype,original=prototype.onSubmittedWorkDone;
            let release;const held=new Promise(resolve=>{release=resolve;});
            window.figgyGeometryGate={entered:false,release:()=>{
                prototype.onSubmittedWorkDone=original;release();
            }};
            prototype.onSubmittedWorkDone=function(...args){
                const completion=original.apply(this,args);
                window.figgyGeometryGate.entered=true;
                return completion.then(()=>held);
            };
        }""")
        try:
            execute("ax.set_title('Pending display'); await fig.sync(timeout=5)")
            page.wait_for_function('window.figgyGeometryGate.entered', polling=100)
            submitted = page.evaluate('window.figgyGPUWork.submitted')
            execute("state=fig.get_settings(); state['config']['annotations']['items'][0]['kind']['Text']['anchor']={'Ratio':{'x':.6,'y':.7}}; fig.apply_settings(state); await fig.sync(timeout=5)")
            # Start the geometry read without awaiting it in Playwright. The
            # following existing five-second sync barrier detects a blocked
            # host queue, and finally always releases the real GPU fence.
            page.evaluate("()=>{window.figgyGeometryResult=null;window.figgyGeometryRead="+ROOT+".annotations().then(value=>{window.figgyGeometryResult=value;});}")
            execute('await fig.sync(timeout=5)')
            entries = page.evaluate('window.figgyGeometryResult')
            (tmp_path/'geometry-read.json').write_text(json.dumps({
                'before': before, 'entries': entries,
                'host': page.evaluate(ROOT+'.diagnostics()'),
                'submissions_before_read': submitted,
                'submissions_after_read': page.evaluate('window.figgyGPUWork.submitted'),
                'column_uploads_before': uploads,
                'column_uploads_after': page.evaluate(ROOT+'.stats.column_uploads'),
                'accepted': page.evaluate(ROOT+'.snapshot()'),
            }, indent=2))
            assert len(entries) == 1 and entries[0]['id'] == 'probe'
            after = entries[0]['rect']
            assert after[0] > before[0] and after[1] > before[1]
            assert page.evaluate(ROOT+'.diagnostics().frame_pending')
            assert page.evaluate('window.figgyGPUWork.submitted') == submitted
            assert page.evaluate(ROOT+'.stats.column_uploads') == uploads
            state = json.loads(execute('print(json.dumps(fig.get_settings()))'))
            assert state['config']['annotations']['items'][0]['kind']['Text']['anchor'] == {'Ratio':{'x':.6,'y':.7}}
        finally:
            page.evaluate('window.figgyGeometryGate.release()')

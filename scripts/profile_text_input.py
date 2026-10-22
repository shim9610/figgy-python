"""Profile actual native typing, including the durable review controller.

Requires an installed release wheel, X11, xdotool and the test dependencies.
Run with an output JSON path. Host stages exclude input-driver waits; they
are CPU wall times, not physical GPU timings or a hardware FPS estimate.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import time

os.environ['FIGGY_PROFILE_HOST'] = '1'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tests'))

from figgyplot.desktop import poll_events
from figgyplot.review import Session
from test_radial_desktop import Inputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result = dict(kind='CPU wall time; driver_poll_ms includes the driver and is not frame time', cases=[])
    for mode in ['inline','inspector','review','target']:
        with Session(backend='native') as session:
            fig = session.figure(id='plot', figsize=(10,6), dpi=120)
            ax = fig.axes[0]
            for i in range(12):
                ax.plot([0,1,2],[i,i+2,i+1],id=f's{i}')
            for i in range(16):
                ax.text(.2+(i%4)*.14,.2+(i//4)*.14,f'Note {i}',coords='ratio',id=f'n{i}')
            session.present()
            handle = session._handles['plot']
            inputs = Inputs(handle)

            def send(*command):
                before = json.loads(handle.info_json())['surface_frames']
                inputs.xdo(*command)
                deadline = time.monotonic()+10
                while json.loads(handle.info_json())['surface_frames'] <= before:
                    session.poll()
                    assert time.monotonic()<deadline, command

            try:
                if mode == 'review':
                    inputs.click('review_comments')
                else:
                    bounds = json.loads(fig._native.bounds_json('annotation:n0'))['rect']
                    panel = inputs.info()['chart_panel']
                    x = round(panel[0]+(bounds[0]+bounds[2]/2)*panel[2]/1200)
                    y = round(panel[1]+(bounds[1]+bounds[3]/2)*panel[3]/720)
                    send('mousemove','--window',inputs.wid,x,y)
                    if mode == 'inline':
                        send('click','--repeat',2,'--delay',100,1)
                        assert 'inline_text' in inputs.info()['controls']
                    elif mode == 'inspector':
                        send('click',1)
                        inputs.click('properties')
                        inputs.click('annotation_text')
                        inputs.key('ctrl+a')
                    else:
                        send('click',3)
                        key = next(k for k in inputs.info()['controls'] if k.startswith('review_target:'))
                        inputs.click(key)
                        inputs.click('review_target_text')
                before = fig.info['host_work']
                ssot = fig.get_settings()
                poll_ms = []
                for char in 'Typinglatencymeasurement':
                    started = time.perf_counter()
                    send('type','--clearmodifiers','--delay','0',char)
                    poll_ms.append((time.perf_counter()-started)*1000)
                after = fig.info['host_work']
                stages = {}
                for key, value in after.items():
                    calls = value['count']-before.get(key,{}).get('count',0)
                    if calls:
                        stages[key] = dict(calls=calls, total_ms=value['total_ms']-before.get(key,{}).get('total_ms',0), p95_ms=value['p95_ms'])
                changed = fig.get_settings() != ssot
                assert changed == (mode == 'inspector')
                entry = dict(mode=mode, stages=stages, driver_poll_ms=poll_ms, revision_changed=changed)
                result['cases'].append(entry)
                print(json.dumps(entry),flush=True)
            finally:
                session.close()
                poll_events()
    args.output.write_text(json.dumps(result,indent=2)+'\n')


if __name__ == '__main__':
    main()

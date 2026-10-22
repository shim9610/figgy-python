"""Measure real native input without using input-driver wait time as frame time.

Run an installed release wheel with DISPLAY and FIGGY_PROFILE_HOST=1. Requires
xdotool and an X11 window manager. Stage times are CPU wall times on this host;
they include renderer API calls but are not hardware GPU timestamps or FPS.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time

import figgyplot as fg
from figgyplot.desktop import poll_events

CONTROLLER = None


def pump():
    for _ in range(4):
        if CONTROLLER is not None:CONTROLLER.poll()
        else:poll_events()
        time.sleep(.003)


def main():
    global CONTROLLER
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--moves', type=int, default=32)
    parser.add_argument('--burst', action='store_true', help='queue all pointer motions before pumping a frame')
    parser.add_argument('--review', action='store_true', help='also pump the durable review controller')
    args = parser.parse_args()
    os.environ['FIGGY_PROFILE_HOST'] = '1'
    result = {'kind': 'CPU wall time, excludes input-driver waits; not physical GPU FPS', 'burst':args.burst, 'review':args.review, 'cases': []}
    writes=[]
    if args.review:
        from figgyplot.review import Session
        from figgyplot import _review_store
        original=_review_store.atomic_write
        def timed_write(*a,**kw):
            started=time.perf_counter()
            try:return original(*a,**kw)
            finally:writes.append((time.perf_counter()-started)*1000)
        _review_store.atomic_write=timed_write
    for width, height, kind in [(960, 600, 'Text'), (1440, 900, 'Text'), (960, 600, 'Arrow')]:
        owner=Session(backend='native') if args.review else fg.Figure(figsize=(width/120,height/120),dpi=120,backend='native')
        with owner:
            fig=owner.figure(id='plot',figsize=(width/120,height/120),dpi=120) if args.review else owner
            ax = fig.axes[0]
            ax.plot([0, 1, 2], [0, 2, 1], id='signal')
            ax.text(.7, .7, 'Preserve this annotation', coords='ratio', id='fixed')
            if kind == 'Text':
                ax.text(.3, .4, 'Move this annotation', coords='ratio', id='moving')
            else:
                ax.arrow(.3, .4, .15, .1, coords='ratio', id='moving')
            if args.review:
                owner.present();window=owner._handles['plot'];CONTROLLER=owner
            else:window=fig.show(block=False)
            try:
                for _ in range(12):
                    pump()
                wid = subprocess.check_output(['xdotool', 'search', '--pid', str(os.getpid()), '--name', '^Figgy$'], text=True).splitlines()[-1]
                def send(*command):
                    before = json.loads(window.info_json())['surface_frames']
                    subprocess.run(['xdotool', *map(str, command)], check=True)
                    deadline = time.monotonic()+10
                    while True:
                        pump()
                        if json.loads(window.info_json())['surface_frames'] > before:
                            return
                        if time.monotonic() > deadline:
                            raise RuntimeError(('input not presented', command, window.info_json()))
                subprocess.run(['xdotool', 'windowmove', wid, '10', '10', 'windowraise', wid, 'windowfocus', wid], check=True)
                pump()
                bounds = json.loads(fig._native.bounds_json('annotation:moving'))['rect']
                panel = json.loads(window.info_json())['chart_panel']
                x = round(panel[0]+(bounds[0]+bounds[2]/2)*panel[2]/width)
                y = round(panel[1]+(bounds[1]+bounds[3]/2)*panel[3]/height)
                send('mousemove', '--window', wid, x, y)
                send('mousedown', 1)
                send('mouseup', 1)
                time.sleep(.5)  # Avoid interpreting the next press as a double click.
                send('mousedown', 1)
                before = fig.get_settings()
                counters = fig.info['host_work']
                writes_before=len(writes)
                if args.burst:
                    commands = []
                    for step in range(1, args.moves+1):
                        commands += ['mousemove', '--window', wid, str(x+step*2), str(y+step)]
                    subprocess.run(['xdotool', *commands], check=True)
                    deadline = time.monotonic()+10
                    while True:
                        pump()
                        observed = json.loads(window.info_json()).get('pointer_input', {}).get('position')
                        if observed == [x+args.moves*2, y+args.moves]:
                            break
                        assert time.monotonic()<deadline, window.info_json()
                else:
                    for step in range(1, args.moves+1):
                        send('mousemove', '--window', wid, x+step*2, y+step)
                after_counters = fig.info['host_work']
                drag_writes=writes[writes_before:]
                send('mouseup', 1)
                after = fig.get_settings()
                old = json.loads(json.dumps(before))
                new = json.loads(json.dumps(after))
                a = old['config']['annotations']['items'][1]
                b = new['config']['annotations']['items'][1]
                assert a['kind'] != b['kind'], (kind, window.info_json())
                b['kind'] = a['kind']
                assert old == new, 'drag changed unrelated SSOT'
                stages = {}
                for name, value in after_counters.items():
                    prev = counters.get(name, {})
                    count = value['count']-prev.get('count', 0)
                    total = value['total_ms']-prev.get('total_ms', 0)
                    stages[name] = dict(calls=count, total_ms=total, mean_ms=total/count if count else None)
                entry = dict(width=width, height=height, annotation=kind, moves=args.moves,
                             stages=stages, recent=after_counters, info=fig.info,
                             durable_writes=dict(count=len(drag_writes),total_ms=sum(drag_writes),max_ms=max(drag_writes,default=0)))
                result['cases'].append(entry)
                print(json.dumps({k: v for k, v in entry.items() if k not in ('info', 'recent')}), flush=True)
            finally:
                window.close()
                CONTROLLER=None
                pump()
    args.output.write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    main()

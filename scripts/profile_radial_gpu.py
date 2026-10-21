"""Measure resident GPU frame latency with fixed data and two display sizes.

Run from a checkout with its installed wheel and Jupyter test runtime.
Observers add no GPU fences. Each phase waits for the host's existing completion.
"""
import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tests'))
from jupyter_harness import notebook

ROOT = "document.querySelector('.figgy-editor')"


def wait_idle(page):
    page.wait_for_function(
        "(()=>{const d=" + ROOT + ".figgy.diagnostics();"
        "return !d.busy&&!d.queued&&!d.dirty&&!d.frame_pending&&!d.frame_error;})()",
        polling=100, timeout=180000,
    )


def wait_next_frame(page, previous):
    page.wait_for_function(
        "n=>" + ROOT + ".figgy.stats.surface_frames>n",
        arg=previous, polling=100, timeout=180000,
    )
    wait_idle(page)


def record(page, rows, output, kind, phase):
    timing = page.evaluate('window.figgyTiming.snapshot()')
    rows.append({'kind': kind, 'phase': phase, 'timing': timing})
    (output / 'results.json').write_text(json.dumps(rows))
    print(json.dumps({
        'kind': kind, 'phase': phase, 'canvas': timing['geometry']['canvas'][:2],
        'last_fences': timing['fences'][-2:],
    }), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output
    output.mkdir(parents=True)
    os.environ['FIGGY_TEST_TIMING'] = '1'
    rows = []
    for kind, setup in [('radial', 'ax.donut([2,3,4])'),
                        ('cartesian', 'ax.plot([0,1,2],[1,3,2])')]:
        source = ("import figgyplot as figgy\n"
                  "fig,ax=figgy.subplots(backend='webgpu')\n" + setup +
                  "\ndisplay(fig.widget())")
        with notebook(output / kind, source) as (page, execute):
            wait_idle(page)
            for phase, width in [('half', 502), ('full', 982)]:
                previous = page.evaluate(ROOT + '.figgy.stats.surface_frames')
                page.evaluate("data=>{window.figgyTiming.mark(data.phase,{width:data.width});"
                              "document.querySelector('.figgy-editor').style.width=data.width+'px';}",
                              {'phase': phase, 'width': width})
                wait_next_frame(page, previous)
                record(page, rows, output, kind, phase)
            previous = page.evaluate(ROOT + '.figgy.stats.surface_frames')
            page.evaluate("window.figgyTiming.mark('warm-edit')")
            if kind == 'radial':
                execute("fig.set_radial_style(hover_brightness=.05);print('updated')")
            else:
                execute("fig.configure(config={'chart_title':{'offset_x':1}});print('updated')")
            wait_next_frame(page, previous)
            record(page, rows, output, kind, 'warm-edit')


if __name__ == '__main__':
    main()

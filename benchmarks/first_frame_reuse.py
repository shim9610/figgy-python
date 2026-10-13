"""Completed first-frame cost of process-first, shared and reset native Figures."""
import argparse
import hashlib
import json
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path

import numpy as np


def timed(operation):
    start = time.perf_counter()
    result = operation()
    return time.perf_counter()-start, result


def worker(args):
    import figgy
    # Imports and input creation are excluded, just like compare.py.
    x = np.linspace(0, 100, args.size, dtype=np.float64)
    y = np.sin(x) + .2*np.cos(x*4)
    if args.signal == 'noisy':
        y += np.random.default_rng(20261013).normal(0, .1, args.size)
    assert not figgy.release_gpu()
    rows, reference, identities = [], None, []
    for index in range(args.following+1):
        initialize, (figure, ax) = timed(lambda: figgy.subplots(backend='native'))
        try:
            register, _ = timed(lambda: ax.plot(x, y, linewidth=1.5, color='#1f77b4', id='signal')
                                if args.kind == 'line' else ax.scatter(x, y, s=9, color='#1f77b4', id='signal'))
            draw, pixels = timed(figure.render_rgba)
            # All validation is outside the measured interval. The same data
            # must produce the same complete pixels on every new Figure.
            assert pixels.shape == (600, 960, 4)
            crop = pixels[100:500, 100:800, :3]
            assert np.count_nonzero(crop.max(axis=2)-crop.min(axis=2) > 25) > 100
            digest = hashlib.sha256(pixels.tobytes()).hexdigest()
            if reference is None:
                reference = digest
            assert digest == reference, 'new Figure changed rendered pixels'
            info = figure.info
            assert info['column_uploads'] == 2 and info['rgba_readbacks'] == 1 and info['png_encodes'] == 0
            assert info['preparation'] is None and info['columns'] == 2
            identities.append(info['gpu_context_id'])
            rows.append({'index':index, 'initialize_s':initialize, 'register_and_fit_s':register,
                         'first_draw_s':draw, 'first_frame_total_s':initialize+register+draw,
                         'gpu_context_id':info['gpu_context_id'], 'pool_capacity_bytes':info['pool_capacity_bytes'],
                         'pool_used_bytes':info['pool_used_bytes'], 'pixel_sha256':digest,
                         'column_uploads':info['column_uploads'], 'rgba_readbacks':info['rgba_readbacks'],
                         'png_encodes':info['png_encodes']})
        finally:
            figure.close()
        if args.worker == 'reset':
            assert figgy.release_gpu()
    if args.worker == 'shared':
        assert len(set(identities)) == 1
        figgy.release_gpu()
    else:
        assert len(set(identities)) == len(identities)
    return {'mode':args.worker, 'kind':args.kind, 'signal':args.signal, 'size':args.size,
            'adapter':info['adapter'], 'rows':rows}


def summarize(runs):
    summaries = []
    keys = sorted({(r['kind'], r['signal'], r['size']) for r in runs})
    metrics = ('initialize_s', 'register_and_fit_s', 'first_draw_s', 'first_frame_total_s')
    for kind, signal, size in keys:
        matching = [r for r in runs if (r['kind'], r['signal'], r['size']) == (kind, signal, size)]
        row = {'kind':kind, 'signal':signal, 'size':size}
        for category in ('process_first', 'shared_following', 'reset_following'):
            samples = [frame for run in matching for frame in run['rows']
                       if (category == 'process_first' and frame['index'] == 0)
                       or (frame['index'] > 0 and category == run['mode']+'_following')]
            row[category] = {'samples':len(samples), 'median':{m:statistics.median(s[m] for s in samples) for m in metrics}}
        row['shared_vs_process_first_speedup'] = row['process_first']['median']['first_frame_total_s']/row['shared_following']['median']['first_frame_total_s']
        row['shared_vs_reset_following_speedup'] = row['reset_following']['median']['first_frame_total_s']/row['shared_following']['median']['first_frame_total_s']
        paired = []
        for repeat in sorted({r['repeat'] for r in matching}):
            medians = {r['mode']:statistics.median(frame['first_frame_total_s'] for frame in r['rows'][1:])
                       for r in matching if r['repeat'] == repeat}
            paired.append(medians['reset']/medians['shared'])
        row['paired_following_speedups'] = paired
        row['paired_following_speedup_median'] = statistics.median(paired)
        summaries.append(row)
    return summaries


def plot_report(report, output):
    import figgy
    with figgy.Figure(backend='native', figsize=(9, 5), dpi=120) as figure:
        ax = figure.axes[0]
        for key, label, color in [('process_first','First Figure in fresh process','#d55232'),
                                  ('reset_following','Following: reset GPU context','#9561b7'),
                                  ('shared_following','Following: shared GPU context','#1765ad')]:
            for index, kind in enumerate(sorted({r['kind'] for r in report['summary']})):
                rows = sorted((r for r in report['summary'] if r['kind'] == kind), key=lambda r:r['size'])
                ax.plot([r['size']/1_000_000 for r in rows], [r[key]['median']['first_frame_total_s']*1000 for r in rows],
                        'o-', color=color, label=label + (' / '+kind if len({r['kind'] for r in report['summary']})>1 else ''),
                        linestyle='-' if index == 0 else '--', linewidth=1.8, markersize=6)
        adapter = report['runs'][0]['adapter']
        ax.set_title(f"Completed first RGBA frame / {adapter['backend']} ({adapter['device_type']})", fontsize=17)
        ax.set_xlabel('Input samples (millions; float64)', fontsize=12)
        ax.set_ylabel('Initialize + upload/fit + draw/readback (ms)', fontsize=12)
        ax.legend()
        state = figure.get_settings()
        state['config']['left_y']['out_margin'] = 110
        state['config']['legend']['corner'] = 'TopLeft'
        state['config']['legend']['content']['font_size'] = 13
        figure.apply_settings(state)
        figure.savefig(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sizes', nargs='+', type=int, default=[100_000, 1_000_000, 5_000_000])
    parser.add_argument('--kinds', nargs='+', choices=['line','scatter'], default=['line'])
    parser.add_argument('--signal', choices=['smooth','noisy'], default='smooth')
    parser.add_argument('--repeats', type=int, default=5)
    parser.add_argument('--following', type=int, default=3)
    parser.add_argument('--timeout', type=float, default=180)
    parser.add_argument('--output', type=Path, default=Path('benchmarks/results/first-frame-reuse.json'))
    parser.add_argument('--plot', type=Path)
    parser.add_argument('--worker', choices=['shared','reset'])
    parser.add_argument('--kind', choices=['line','scatter'], default='line')
    parser.add_argument('--size', type=int, default=100_000)
    args = parser.parse_args()
    if min(args.sizes+[args.size,args.repeats,args.following]) < 1:
        parser.error('sizes, repeats and following must be positive')
    if args.worker:
        print(json.dumps(worker(args)))
        return
    import figgy
    report = {'metric':'completed first RGBA; initialize + registration/fit + render/readback',
              'os':platform.platform(), 'python':sys.version.split()[0], 'figgy_version':figgy.__version__,
              'repeats':args.repeats, 'following_per_process':args.following, 'input_dtype':'float64',
              'size_px':[960,600], 'explicit_prepare':False, 'automatic_downsampling':False,
              'driver_cache_cleared':False, 'import_and_input_creation_timed':False,
              'modes':'shared retains context after close; reset calls release_gpu after each close',
              'runs':[]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for kind in args.kinds:
        for size in args.sizes:
            for repeat in range(args.repeats):
                # Alternate mode order. Each invocation starts a fresh worker.
                for mode in (('shared','reset') if repeat%2 == 0 else ('reset','shared')):
                    command = [sys.executable, str(Path(__file__).resolve()), '--worker',mode,'--kind',kind,
                               '--size',str(size),'--following',str(args.following),'--signal',args.signal]
                    completed = subprocess.run(command, capture_output=True, text=True, timeout=args.timeout)
                    if completed.returncode:
                        raise RuntimeError(f'{kind}/{size}/{mode}: {completed.stderr[-4000:]}')
                    run = json.loads(completed.stdout.strip().splitlines()[-1])
                    previous = [r for r in report['runs'] if (r['kind'],r['signal'],r['size']) == (kind,args.signal,size)]
                    if previous:
                        assert run['rows'][0]['pixel_sha256'] == previous[0]['rows'][0]['pixel_sha256'], 'reset/shared pixel mismatch'
                    run['repeat'] = repeat
                    report['runs'].append(run)
                    args.output.write_text(json.dumps(report, indent=2)+'\n')
                    milliseconds = [round(r['first_frame_total_s']*1000,2) for r in run['rows']]
                    print(f'{kind} {size:,} repeat={repeat+1} {mode}: {milliseconds} ms', flush=True)
    report['summary'] = summarize(report['runs'])
    report['cross_process_reset_shared_pixels_identical'] = True
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    if args.plot:
        args.plot.parent.mkdir(parents=True, exist_ok=True)
        plot_report(report, args.plot)
    print(json.dumps(report['summary'], indent=2))


if __name__ == '__main__':
    main()

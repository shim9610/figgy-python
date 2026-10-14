"""Measure native context reuse; constructor/preparation times are not UI FPS."""
import argparse
import json
import statistics
import time
from pathlib import Path

import numpy as np
import figgyplot as figgy


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--figures', type=int, default=8)
    parser.add_argument('--points', type=int, default=100_000)
    parser.add_argument('--output', type=Path, default=Path('benchmarks/results/shared-context.json'))
    args = parser.parse_args()
    if args.figures < 2 or args.points < 2:
        parser.error('use at least 2 Figures and 2 points')
    figgy.release_gpu()
    figures, times, reports = [], [], []
    x = np.linspace(0, 10, args.points, dtype=np.float32)
    y = np.sin(x)
    try:
        for index in range(args.figures):
            start = time.perf_counter()
            figure = figgy.Figure(backend='native')
            times.append((time.perf_counter()-start)*1000)
            figures.append(figure)
            figure.axes[0].plot(x, y, id='signal')
            if index == 0:
                reports.append(figure.prepare())
        reports.append(figures[-1].prepare())
        identities = {figure.info['gpu_context_id'] for figure in figures}
        assert len(identities) == 1
        result = {
            'metric':'first vs subsequent native Figure construction, not render FPS',
            'adapter':figures[0].info['adapter'], 'figures':args.figures,
            'points_per_figure':args.points, 'context_ids':list(identities),
            'constructor_ms':times, 'first_constructor_ms':times[0],
            'subsequent_constructor_median_ms':statistics.median(times[1:]),
            'prewarm_stage_events':[len(report['stages']) for report in reports],
            'initial_preparation_ms':reports[0]['elapsed_ms'],
            'subsequent_preparation_ms':reports[1]['elapsed_ms'],
            'shared_pool_capacity_bytes':figures[0].info['pool_capacity_bytes'],
            'shared_pool_used_bytes':figures[0].info['pool_used_bytes'],
            'total_column_uploads':sum(figure.info['column_uploads'] for figure in figures),
            'no_cpu_source_retention':True, 'persistent_cache_supported':False,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps(result, indent=2))
    finally:
        for figure in figures:
            figure.close()
        figgy.release_gpu()


if __name__ == '__main__':
    main()

"""Renderer 0.18 features on native or notebook hosts, without a review session."""
import argparse
from pathlib import Path
import numpy as np
import figgyplot as figgy


def make_figures(backend='auto'):
    dashboard = figgy.Figure(backend=backend, id='dashboard', figsize=(12, 7),
                            grid=[['overview', 'field'], ['overview', 'residual']])
    x = np.linspace(0, 6, 61)
    overview = dashboard.subplots['overview'].axes
    overview.fill_between(x, np.sin(x)+2, np.cos(x)*.3+1, color='blue', id='envelope')
    overview.scatter(x[::5], np.sin(x[::5])+2, c=x[::5], s=x[::5]+1, id='observations')
    overview.set_title('Mapped observations and reference fill')
    overview.axhline(2, color='red', id='threshold')
    overview.text(.1, .1, 'Editable annotation', coords='ratio', id='note')
    secondary = overview.twinx(id='pressure')
    secondary.plot(x, x*100, color='red', id='pressure_values', label='Pressure')
    secondary.set_ylabel('Pressure')
    field = dashboard.subplots['field'].axes
    gx, gy = np.linspace(-1, 1, 5), np.linspace(-1, 1, 4)
    xx, yy = np.meshgrid(gx, gy)
    field.quiver(gx, gy, -yy, xx, values=np.hypot(xx, yy), scale=20, id='flow')
    field.set_title('Grid vectors')
    residual = dashboard.subplots['residual'].axes
    residual.step(x, np.sin(x), where='post', id='residual_values')
    residual.set_title('Step line')
    dashboard.share_axes('x', ['overview', 'residual'], id='time')
    dashboard.fit()

    polar, ax = figgy.subplots(backend=backend, subplot_kw={'projection': 'polar'})
    ax.plot(np.linspace(0, 360, 17), 2+np.sin(np.linspace(0, 4*np.pi, 17)), id='orbit', fill=0)
    ax.set_title('Polar coordinates')
    ax.arrow(.2, .2, .15, .15, coords='ratio', id='direction')

    radar, ax = figgy.subplots(backend=backend)
    ax.radar(['Speed', 'Quality', 'Cost', 'Reach'], [[3, 5, 2, 4], [4, 3, 4, 2]],
             labels=['First', 'Second'])
    ax.set_title('Independent rich radar title', fontsize=18, color='purple')
    ax.text(.05, .05, 'Review manually', coords='ratio', id='note')
    return dashboard, polar, radar


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    figures = make_figures('native')
    try:
        if args.output:
            args.output.mkdir(parents=True, exist_ok=True)
            for name, figure in zip(('dashboard', 'polar', 'radar'), figures):
                figure.savefig(args.output/(name+'.png'))
                (args.output/(name+'.py')).write_text(figure.to_code(), encoding='utf-8')
        else:
            for figure in figures:
                figure.show(block=False)
            from figgyplot.desktop import run_events
            run_events()
    finally:
        for figure in figures:
            figure.close()

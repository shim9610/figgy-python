"""Manual editor example: named panels, mapped points, annotations and history.

Run against the current checkout's wheel: python examples/editor_commands.py
Select objects on the chart or in the tree, then use Properties, Undo/Redo and
Figure > Reset edits. Copy Python or save from the window; no review session is
needed. In a notebook, use backend='webgpu' and display(fig.widget()) instead.
"""
import numpy as np
import figgyplot as fg


def build(backend='native'):
    fig = fg.Figure(backend=backend, id='editor-example', grid=[['trend', 'samples']])
    x = np.linspace(0, 10, 21)
    trend, samples = fig.subplots['trend'].axes, fig.subplots['samples'].axes
    trend.step(x, np.sin(x), where='mid', label='Signal', id='signal')
    trend.set_title('Steps and annotations'); trend.set_xlabel('Time (s)')
    trend.set_ylim(-1.3, 1.3); trend.legend()
    trend.text(.1, .12, 'Drag or double-click this text', coords='ratio', id='note')
    samples.scatter(x, np.sin(x), c=x, s=60, id='measurements')
    samples.set_title('Values control color'); samples.set_xlabel('Time (s)')
    samples.set_ylim(-1.3, 1.3)
    fig.share_axes('x', ['trend', 'samples'], id='time')
    trend.set_xlim(-.5, 10.5)
    return fig


if __name__ == '__main__':
    fig = build()
    try:
        fig.show()
    finally:
        fig.close()

"""Adapt public rich titles to the upstream bounded model's legacy fallback.

``chart_title`` owns the displayed text. ``title`` is only a single-line,
160-character fallback for older consumers; it must never limit the rich text.
Native model validation still enforces the rich title's own limits atomically.
"""
import copy


def title_options(chart):
    from .figure import _segments
    if chart.get('chart_title') is None:
        chart['chart_title'] = dict(visible=True, text=dict(
            segments=_segments(chart['title']), font_size=chart['font_size'] * 1.5,
            font=chart['font_family'],
            color=copy.deepcopy(chart.get('text_color', chart.get('label_color'))),
            align='Left'))
    return chart['chart_title']


def set_title_text(chart, text=None, *, segments=None):
    from .figure import _segments, _text
    title = title_options(chart)
    title['text']['segments'] = _segments(text) if segments is None else copy.deepcopy(segments)
    # Unicode super/subscripts retain their original spelling where recoverable.
    plain = _text(title['text'])
    chart['title'] = plain.replace('\n', ' ').replace('\r', ' ')[:160]


def inherit_title(chart, config):
    title = config['chart_title']
    # Leave untouched defaults in the bounded renderer's own typography. Any
    # existing title (including explicitly hidden text) keeps its rich styles.
    if title['text']['segments']:
        chart['chart_title'] = dict(visible=title['visible'], text=copy.deepcopy(title['text']))
        set_title_text(chart, segments=title['text']['segments'])


def category_label(value):
    label = str(value)
    if '\n' in label or '\r' in label:
        raise ValueError('category labels must be single-line; use a short label and put details in the chart title')
    return label

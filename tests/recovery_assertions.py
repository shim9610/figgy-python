"""Independent array expectations at cache, upload and GPU-readback boundaries."""
from contextlib import contextmanager
import json

import numpy as np
import figgyplot as fg


class RecordedUploads:
    def __init__(self, native, arrays):
        self.native, self.arrays = native, arrays

    def __getattr__(self, name):
        return getattr(self.native, name)

    def upload_column(self, name, array):
        assert name not in self.arrays, ('duplicate upload', name)
        original = np.array(array, copy=True)
        self.native.upload_column(name, array)
        self.arrays[name] = original


@contextmanager
def record_uploads(monkeypatch):
    arrays = {}
    original = fg.Figure.__init__

    def create(figure, *args, **kwargs):
        original(figure, *args, **kwargs)
        figure._native = RecordedUploads(figure._native, arrays)

    with monkeypatch.context() as patch:
        patch.setattr(fg.Figure, '__init__', create)
        yield arrays


def assert_arrays(expected, actual, stage):
    assert set(actual) == set(expected), (stage, 'column identities', set(actual), set(expected))
    for name, original in expected.items():
        recovered = actual[name]
        assert recovered.dtype == original.dtype, (stage, name, 'dtype', recovered.dtype, original.dtype)
        assert recovered.shape == original.shape, (stage, name, 'shape', recovered.shape, original.shape)
        np.testing.assert_array_equal(recovered, original, err_msg=f'{stage}: {name}')
        # Also preserve signed zero and NaN payload bits at lossless boundaries.
        assert recovered.tobytes() == original.tobytes(), (stage, name, 'payload bits')


def assert_cached_columns(cache, checkpoint, expected):
    # Read the actual NPY files independently of Store.get (the restore reader).
    for key in ('columns', 'baseline_columns'):
        arrays = {name: np.load(cache / ref['file'], allow_pickle=False)
                  for name, ref in checkpoint[key].items()}
        assert_arrays(expected, arrays, key)
        for name, value in arrays.items():
            ref = checkpoint[key][name]
            assert ref['dtype'] == value.dtype.str and ref['shape'] == list(value.shape)


def assert_cached_bounded(cache, checkpoint, family):
    # Literal expectations for the public inputs in test_review.create.
    expected = {}
    if family == 'pie':
        expected = {f'/radial/slices/{i}/value': np.array([value])
                    for i, value in enumerate((3.,2.,1.))}
    elif family in ('bar','radar'):
        kind, values = ('categorical',[3.,4.]) if family=='bar' else ('radar',[1.,2.,3.])
        expected = {f'/{kind}/series/0/values': np.array(values)}
    elif family == 'box':
        stats = (dict(q1=1.5,median=2.,q3=2.5,whisker_low=1.,whisker_high=3.,mean=2.,sample_count=3),
                 dict(q1=3.,median=4.,q3=5.,whisker_low=2.,whisker_high=6.,mean=4.,sample_count=3))
        expected = {f'/boxplot/series/0/values/{i}/{key}': np.array([value])
                    for i, row in enumerate(stats) for key, value in row.items()}
    for key in ('bounded_data','baseline_bounded_data'):
        arrays = {name: np.load(cache / ref['file'], allow_pickle=False)
                  for name, ref in checkpoint[key].items()}
        assert_arrays(expected, arrays, key)
        for name, array in arrays.items():
            ref = checkpoint[key][name]
            assert ref['dtype'] == array.dtype.str and ref['shape'] == list(array.shape)


def assert_renderer_columns(figure, expected):
    if figure.backend == 'webgpu':
        actual = {name: np.frombuffer(data, dtype=np.dtype(dtype).newbyteorder('<')).copy()
                  for name, (dtype, data) in figure._native.columns.items()}
        assert_arrays(expected, actual, 'browser transfer')
        return

    # Post-restore inspection only. Probe series reference the existing buffers;
    # they upload no samples and are discarded with this test Figure. Read every
    # column through the production GPU selection readback, not the review cache.
    native = figure._native
    while isinstance(native, RecordedUploads) or hasattr(native, 'native'):
        native = native.native
    uploads = figure.info['column_uploads']
    for number, (name, original) in enumerate(expected.items()):
        sid = f'recovery_readback_{number}'
        native.add_series(json.dumps(dict(series_id=sid, label=None, x_column=name, y_column=name,
            render_type={'Line': {'line': dict(line_color=dict(r=0,g=0,b=0,a=1),
                line_width=1,line_style='Solid',interpolation='Linear')}})))
        state = json.loads(native.settings_json())
        for index, value in enumerate(original):
            state['config']['picked_data'] = {'refs': [dict(kind='point', series_id=sid, point_index=index)]}
            native.apply_settings(json.dumps(state))
            sample = json.loads(native.selection_details_json())
            for axis in ('x', 'y'):
                if np.isfinite(value):
                    # Native columns use a pair of f32 values for f64 arithmetic.
                    np.testing.assert_allclose(sample[axis], value, rtol=2e-14, atol=0,
                                               err_msg=f'GPU column {name}[{index}]')
                else:
                    assert sample[axis] is None, (name, index, sample)
    assert figure.info['column_uploads'] == uploads

"""Temporary binary snapshots for a separate browser WebGPU device."""
import json
import numpy as np
from ._native import NotebookFigure

class NotebookData:
    def __init__(self, width, height, pool_bytes, retain):
        self.model = NotebookFigure(width, height, pool_bytes)
        self.columns = {}
        self.retain = retain
        self.sealed = False

    def __getattr__(self, key):
        return getattr(self.model, key)

    def upload_column(self, id, array):
        if self.sealed:
            raise RuntimeError("Notebook columns are sealed after display; create a new Figure to change source data")
        self.model.upload_column(id, array)
        # Independent snapshot: later user mutations must not alter transferred data.
        little = np.asarray(array, dtype=array.dtype.newbyteorder("<"))
        self.columns[id] = (str(array.dtype), little.tobytes(order="C"))

    def add_series_fitted(self, spec_json, config=None, bounds=None):
        # Only bounded extent metadata survives transfer release, never sample arrays.
        spec = json.loads(spec_json)
        style = next(iter(spec['render_type'].values()))
        if 'err_x' in style or 'err_y' in style:
            def array(name):
                dtype, data = self.columns[name]
                return np.frombuffer(data, dtype=np.dtype(dtype).newbyteorder('<')).astype(np.float64)
            x, y = array(spec['x_column']), array(spec['y_column'])
            valid = np.isfinite(x) & np.isfinite(y)
            extents = []
            for axis, values in [('x', x), ('y', y)]:
                ref = style.get('err_'+axis)
                if ref is None:
                    values = values[valid]
                else:
                    if 'Symmetric' in ref:
                        lo = hi = array(ref['Symmetric']['column'])
                    else:
                        lo, hi = (array(ref['Asymmetric'][k]) for k in ('lower', 'upper'))
                    values = np.concatenate((values[valid], (values-lo)[valid], (values+hi)[valid]))
                values = values[np.isfinite(values)]
                if not values.size:
                    raise ValueError('errorbar has no finite paired samples')
                positive = values[values>0]
                extents.append((float(values.min()), float(values.max()), float(positive.min()) if positive.size else None))
            self.model.cache_fit_extent(spec['series_id'], *extents)
        return self.model.add_series_fitted(spec_json, config, bounds)

    def remove_column(self, id):
        self.model.remove_column(id)
        self.columns.pop(id, None)

    def payload(self):
        if self.sealed and not self.columns and not any(json.loads(self.model.settings_json()).get(k) for k in ('radial', 'categorical', 'boxplot')):
            raise RuntimeError("Notebook transfer snapshots were released; create a new Figure, or set retain_notebook_data=True before upload")
        self.sealed = True
        manifest, buffers = [], []
        for id, (dtype, data) in self.columns.items():
            manifest.append({"id": id, "dtype": dtype, "bytes": len(data)})
            buffers.append(data)
        return manifest, buffers

    def acknowledged(self):
        if not self.retain:
            self.columns.clear()

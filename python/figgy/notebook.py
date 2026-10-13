"""Temporary binary snapshots for a separate browser WebGPU device."""
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

    def remove_column(self, id):
        self.model.remove_column(id)
        self.columns.pop(id, None)

    def payload(self):
        if self.sealed and not self.columns:
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

# figgyplot

Plot NumPy data with the Rust Figgy renderer, edit the chart directly, and reuse
its settings as executable Python. Native windows use winit/wgpu; Jupyter uses
packaged WASM and browser WebGPU. No CDN or separate WASM build is needed.

```sh
pip install figgyplot
# Optional Jupyter editor:
pip install 'figgyplot[notebook]'
```

```python
import numpy as np
import figgyplot as plt

x = np.linspace(0, 20, 100_000, dtype=np.float32)
fig, ax = plt.subplots(backend="native")
ax.plot(x, np.sin(x), id="signal")
ax.set_title("Edit, copy Python, and reuse")
fig.show()
fig.savefig("edited.png")
fig.close()
```

![Scientific chart](https://raw.githubusercontent.com/shim9610/figgy-python/main/docs/images/gallery/line-signals.png)

CPython 3.8–3.15. A compatible wheel needs no Rust compiler; source builds need
Rust 1.99+ and a C/C++ toolchain. Native rendering needs a supported GPU driver.
Jupyter needs a WebGPU-capable browser over HTTPS or localhost. Native window
creation and event pumping must run on the main thread.

[Documentation](https://github.com/shim9610/figgy-python/tree/main/docs) ·
[Examples](https://github.com/shim9610/figgy-python/tree/main/examples) ·
[Platform compatibility and verification](https://github.com/shim9610/figgy-python/blob/main/docs/DISTRIBUTION.md)

The distribution and import name are both **figgyplot**. This is independent of
the unrelated `figgy` distribution on PyPI. MIT OR Apache-2.0.

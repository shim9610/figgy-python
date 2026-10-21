# Editor catalog measurements

Measured on Linux x86_64, Python 3.12.14, renderer 0.18.0, on 2026-10-21 UTC.
The [raw five-sample record](measurements/editor-catalog-20261021.json) includes
payload sizes, timing samples and the measured wheel's SHA-256.

The fixtures declare N scatter series with 2N distinct source names. They measure
typed metadata generation and serialization only: no chart is rendered, source
arrays are not uploaded, and the figures do not instantiate a GPU. Timings are
observations on this machine, not GPU throughput, frame-rate estimates or CI
thresholds. Payload sizes are compared within the same build and input document.

| Series | Full catalog (bytes) | Browser transport (bytes) | Selected object (bytes) |
| --- | ---: | ---: | ---: |
| 10 | 77,710 | 74,394 | 2,734 |
| 50 | 283,590 | 170,994 | 4,654 |
| 200 | 2,544,840 | 534,644 | 12,454 |
| 500 | 14,388,540 | 1,263,344 | 28,654 |

The full public catalog repeats available source choices for explicit Python
introspection. It is not sent on every native frame. The native inspector
resolves only the selected object; the browser transport sends column choices
once and references them from its fields. Both modes retain the complete
property descriptions rather than truncating controls for larger documents.

Reproduce after installing the current wheel:

```bash
python scripts/benchmark_editor_catalog.py --output /tmp/editor-catalog.json
```

The input JSON and command fixtures are generated in the script. Parsing the
complete document and enumerating resident source names remain part of the
selected-object cost. The measurements do not establish a rendering-performance
limit or justify changing an interaction timeout.

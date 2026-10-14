# Documentation

## Using Figgy from Python

| Guide | Contents |
| --- | --- |
| [Project README](../README.md) | Installation, quick start, interactive demo and chart gallery |
| [Example index](../examples/README.md) | Runnable chart recipes, image links and commands |
| [Chart and style API](CHART_TYPES.md) | Pies/donuts, procedural materials, handwriting and star modes |
| [Desktop editor](DESKTOP_EDITOR.md) | Zoom/pan, selection, visibility, properties, code export and windows |
| [Edit and reuse demo](README_DEMO.md) | Real clipboard paste, batch application and recording reproduction |
| [Hosts](HOSTS.md) | Native surface and browser WebGPU behavior, data transfer and export |
| [GPU preparation](PREPARATION.md) | Explicit prewarming and cache boundaries |
| [Native resource sharing](NATIVE_SHARING.md) | Ownership, pool capacity, synchronization and release |

## Validation and performance

| Record | Environment and scope |
| --- | --- |
| [Host validation](HOST_VALIDATION.md) | Installed packages, native input and notebook checks by checkpoint |
| [Randomized validation](RANDOMIZED_VALIDATION.md) | Invalid state, recovery, concurrency and real-host campaigns |
| [Linux GPU benchmarks](../benchmarks/LINUX_GPU_RESULTS.md) | Radeon 8060S / Vulkan and OpenGL |
| [Windows GPU comparison](../benchmarks/WINDOWS_GPU_RESULTS.md) | RTX 4070 Ti, Figgy and other GPU plotting paths |
| [Earlier Windows benchmarks](../benchmarks/WINDOWS_RESULTS.md) | RTX 4070 Ti, Agg and QPainter comparison |
| [Software Vulkan benchmarks](../benchmarks/RESULTS.md) | llvmpipe campaign and historical package checks |
| [First-frame reuse](../benchmarks/FIRST_FRAME_REUSE_RESULTS.md) | Process-local shared context versus reset |

Validation records describe the build and environment at each checkpoint.
Historical Qt desktop checks do not establish coverage of the current winit
host. Rendering benchmarks, surface submission rates and display latency are
separate measurements.

The Python package uses the upstream [Figgy renderer](https://github.com/shim9610/figgy).
For renderer internals and chart families beyond the exposed Python API, see
the upstream documentation. Asset licenses and provenance are listed in
[third-party notices](../THIRD_PARTY_NOTICES.md).

[Distribution and platform compatibility](DISTRIBUTION.md) covers the figgyplot name, Python versions, manual wheel matrix and release gates.
[TestPyPI publishing](PUBLISHING.md) gives the exact Trusted Publisher form values,
GitHub environment settings and manual build/upload/installation sequence.

"""Main-thread Rust winit host sharing the resident renderer."""
import threading
from ._native import poll_events as _poll, run_events as _run

def _main_thread():
    if threading.current_thread() is not threading.main_thread():
        raise RuntimeError("winit windows and event pumping must run on the main thread")

def show(figure, *, block=True):
    if not isinstance(block, bool):
        raise ValueError("block must be a boolean (True or False)")
    _main_thread()
    figure._require_open()
    if figure.backend != "native":
        raise RuntimeError("Desktop show requires backend='native'; browser data belongs to its WebGPU device")
    handle = figure._native.show(False)
    figure._windows.append(handle)
    if block:
        _run()
    return handle

def poll_events():
    """Pump all Figgy windows once; call frequently after show(block=False)."""
    _main_thread()
    return _poll()

def run_events():
    """Run until all Figgy windows close. Releases the GIL."""
    _main_thread()
    _run()

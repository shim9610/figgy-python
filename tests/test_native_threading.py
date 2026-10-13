"""PyO3's shared core must not hold the GIL while waiting for its mutex."""
import subprocess,sys

def test_shared_native_core_with_concurrent_python_calls():
    # A subprocess bounds the failure case: a GIL/mutex deadlock must not hang pytest.
    code='''import threading
import numpy as np
from figgy._native import NativeFigure
core=NativeFigure()
x=np.linspace(0,1,100_000)
core.upload_column("x",x)
start=threading.Barrier(2)
errors=[]
def render():
    try:
        start.wait()
        for _ in range(12):core.render_rgba()
    except Exception as e:errors.append(e)
worker=threading.Thread(target=render)
worker.start();start.wait()
for _ in range(80):core.settings_json()
worker.join();assert not errors, errors
print("concurrent core calls completed")
'''
    result=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    assert 'completed' in result.stdout

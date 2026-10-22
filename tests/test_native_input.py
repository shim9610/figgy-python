"""The X11 clipboard owner must outlive its writer without retaining CI logs."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from native_input import set_clipboard


@pytest.mark.skipif(not os.environ.get('DISPLAY') or not shutil.which('xclip'),reason='requires an X11 clipboard')
def test_clipboard_owner_preserves_unicode_without_retaining_writer_output():
    path=str(Path(__file__).parent)
    text='한글 리뷰 · μm · 10⁻⁶'
    inherited="import subprocess;subprocess.run(['xclip','-selection','clipboard','-t','UTF8_STRING'],input='negative control',text=True,check=True);print('writer returned',flush=True)"
    writer=subprocess.Popen([sys.executable,'-c',inherited],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        # The interpreter really exits successfully; an inherited pipe is the
        # only thing keeping communicate()/tee open. This is not a speed test.
        assert writer.wait(timeout=10)==0
        with pytest.raises(subprocess.TimeoutExpired):writer.communicate(timeout=.2)
    finally:
        set_clipboard('Release the negative-control selection owner')
        stdout,stderr=writer.communicate(timeout=10)
        writer.stdout.close();writer.stderr.close()
    assert 'writer returned' in stdout
    assert not stderr
    code="import sys;sys.path.insert(0,sys.argv[1]);from native_input import set_clipboard;set_clipboard(sys.argv[2]);print('writer returned',flush=True)"
    result=subprocess.run([sys.executable,'-c',code,path,text],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr
    assert result.stdout.strip()=='writer returned'
    # Redirecting the owner's descriptors must not kill the clipboard owner.
    accepted=subprocess.check_output(['xclip','-selection','clipboard','-o','-t','UTF8_STRING'],text=True,timeout=10)
    assert accepted==text

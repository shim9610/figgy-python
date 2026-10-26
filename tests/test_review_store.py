"""Storage tests also run on Windows without a renderer or a native wheel."""
import errno
import importlib.util
from pathlib import Path
import multiprocessing
import os
import sys
from types import SimpleNamespace

import pytest


def storage_module():
    path=Path(__file__).resolve().parents[1]/'python/figgyplot/_review_store.py'
    spec=importlib.util.spec_from_file_location('review_storage_under_test',path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def storage_writer(path,start,iterations):
    store=storage_module().Store(path)
    assert start.wait(10)
    for _ in range(iterations):
        with store.locked():
            state=store.read()
            state['counter']+=1
            store.write(state)


def storage_reader(path,start):
    store=storage_module().Store(path)
    assert start.wait(10)
    previous=-1
    for _ in range(80):
        with store.locked():
            state=store.read()
            assert state['generation']>=previous
            previous=state['generation']


def test_image_cleanup_retries_windows_preview_sharing_contention(tmp_path,monkeypatch):
    module=storage_module();store=module.Store(tmp_path)
    image=tmp_path/'attachments'/('a'*64+'.png');image.write_bytes(b'unreferenced image')
    state=dict(protocol=1,generation=0,rounds=[
        dict(number=1,status='completed',documents={'plot':{'comments':[{'attachments':[{'file':'attachments/'+image.name}]}]}}),
        dict(number=2,status='reviewing',documents={})])
    store.write(state)
    original=Path.unlink;attempts=[]
    def unlink(path,*args,**kwargs):
        if path==image:
            attempts.append(path)
            if len(attempts)==1:raise PermissionError(errno.EACCES,'preview reader still closing')
        return original(path,*args,**kwargs)
    monkeypatch.setattr(module,'_WINDOWS',True)
    monkeypatch.setattr(Path,'unlink',unlink)
    store.collect(state)
    assert len(attempts)==2 and not image.exists()
    assert [r['number'] for r in store.read()['rounds']]==[2]


def test_process_subscribers_and_controllers_share_a_durable_head(tmp_path):
    store=storage_module().Store(tmp_path)
    with store.locked():store.write(dict(protocol=1,generation=0,counter=0,rounds=[]))
    context=multiprocessing.get_context('spawn')
    start=context.Event()
    processes=[context.Process(target=storage_writer,args=(str(tmp_path),start,20)) for _ in range(3)]
    processes.append(context.Process(target=storage_reader,args=(str(tmp_path),start)))
    try:
        for process in processes:process.start()
        start.set()
        for process in processes:
            process.join(30)
            assert process.exitcode==0
        with store.locked():state=store.read()
        assert state['counter']==60 and state['generation']==61
        assert not list(tmp_path.glob('.writing-*'))
        # The shared byte is never read/initialized before a lock is owned.
        assert (tmp_path/'.lock').stat().st_size==0
    finally:
        for process in processes:
            if process.is_alive():process.terminate();process.join(5)


def test_nested_lock_keeps_the_outer_lock_and_releases_after_exception(tmp_path):
    store=storage_module().Store(tmp_path)
    with pytest.raises(ValueError,match='deliberate'):
        with store.locked():
            with store.locked():
                store.write(dict(protocol=1,generation=0,rounds=[]))
                raise ValueError('deliberate')
    with store.locked():assert store.read()['generation']==1


def test_windows_byte_lock_retries_without_touching_locked_bytes(tmp_path,monkeypatch):
    module=storage_module();monkeypatch.setattr(module,'_WINDOWS',True)
    calls=[]
    def locking(fd,mode,length):
        calls.append(mode)
        assert os.fstat(fd).st_size==0 and length==1
        if mode==1 and calls.count(1)<3:raise PermissionError(errno.EACCES,'competing lock')
    monkeypatch.setitem(sys.modules,'msvcrt',SimpleNamespace(LK_NBLCK=1,LK_UNLCK=2,locking=locking))
    store=module.Store(tmp_path)
    with store.locked():
        with store.locked():pass
    assert calls==[1,1,1,2]


def test_windows_replace_sharing_denials_keep_the_previous_complete_manifest(tmp_path,monkeypatch):
    module=storage_module();path=tmp_path/'manifest.json'
    path.write_bytes(b'previous')
    monkeypatch.setattr(module,'_WINDOWS',True)
    replace=module.os.replace;calls=[]
    def sharing(source,target):
        calls.append(1)
        if len(calls)<4:
            assert path.read_bytes()==b'previous'
            exc=PermissionError(errno.EACCES,'sharing violation');exc.winerror=32
            raise exc
        replace(source,target)
    monkeypatch.setattr(module.os,'replace',sharing)
    module.atomic_write(path,b'next complete state')
    assert len(calls)==4 and path.read_bytes()==b'next complete state'
    assert not list(tmp_path.glob('.writing-*'))


@pytest.mark.parametrize('windows,code',[(False,errno.EACCES),(True,errno.ENOSPC)])
def test_nonsharing_errors_are_not_retried(monkeypatch,windows,code):
    module=storage_module();monkeypatch.setattr(module,'_WINDOWS',windows)
    def fail():raise OSError(code,'cannot write')
    monkeypatch.setattr(module.time,'sleep',lambda seconds:pytest.fail('unrelated error was retried'))
    with pytest.raises(OSError) as exc:module._windows_retry(fail)
    assert exc.value.errno==code


def test_windows_lock_timeout_preserves_the_error(monkeypatch):
    module=storage_module();monkeypatch.setattr(module,'_WINDOWS',True)
    clock=iter([0,1,2,3]);monkeypatch.setattr(module.time,'monotonic',lambda:next(clock))
    monkeypatch.setattr(module.time,'sleep',lambda _:None)
    error=PermissionError(errno.EACCES,'still locked')
    def busy():raise error
    with pytest.raises(PermissionError) as exc:module._windows_retry(busy,timeout=2)
    assert exc.value is error

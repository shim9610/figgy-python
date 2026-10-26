"""Crash-safe review manifests and immutable numeric payloads."""
from contextlib import contextmanager
import hashlib
import errno
import io
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import threading
import time
import base64
import struct

import numpy as np

_WINDOWS = os.name == 'nt'


def _windows_retry(operation, *, timeout=30):
    """Retry sharing/byte-lock contention, retaining the original error on timeout.

    Permission failures on Unix and unrelated Windows I/O errors are not retried.
    A sharing denial can be reported as EACCES without winerror by the CRT.
    """
    deadline = time.monotonic()+timeout
    while True:
        try:
            return operation()
        except OSError as exc:
            transient = _WINDOWS and (getattr(exc,'winerror',None) in (5,32,33)
                                     or exc.errno in (errno.EACCES,errno.EAGAIN,errno.EDEADLK))
            remaining = deadline-time.monotonic()
            if not transient or remaining<=0:
                raise
            time.sleep(min(.02,remaining))


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def _sync_directory(path):
    if hasattr(os, 'O_DIRECTORY'):
        fd = os.open(str(path), os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def atomic_write(path, data):
    fd, temporary = tempfile.mkstemp(prefix='.writing-', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        _windows_retry(lambda: os.replace(temporary, path))
        _sync_directory(path.parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class Store:
    @staticmethod
    def image_references(doc):
        yield from doc.get('image_assets', [])
        for comment in doc.get('comments', []):
            yield from comment.get('attachments', [])

    @staticmethod
    def references(doc):
        for key in ('columns','baseline_columns','bounded_data','baseline_bounded_data'):
            yield from doc.get(key,{}).values()

    def __init__(self, path):
        self.path = Path(path).resolve()
        self.path.mkdir(parents=True, exist_ok=True)
        (self.path/'data').mkdir(exist_ok=True)
        (self.path/'attachments').mkdir(exist_ok=True)
        self.mutex = threading.RLock()
        self._local = threading.local()
        self._seen_generation = None
        self._verified_images = {}

    @contextmanager
    def locked(self):
        with self.mutex:
            if getattr(self._local,'held',False):
                yield
                return
            # Windows permits locking beyond EOF. Do not read or initialize
            # byte zero before locking: a peer may already own that byte.
            with (self.path/'.lock').open('a+b') as stream:
                if _WINDOWS:
                    import msvcrt
                    stream.seek(0)
                    _windows_retry(lambda: msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1))
                else:
                    import fcntl
                    fcntl.flock(stream, fcntl.LOCK_EX)
                self._local.held=True
                try:
                    yield
                finally:
                    self._local.held=False
                    if _WINDOWS:
                        stream.seek(0)
                        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        fcntl.flock(stream, fcntl.LOCK_UN)

    def read(self):
        state = json.loads((self.path/'manifest.json').read_text(encoding='utf-8'))
        if state.get('protocol') != 1:
            raise ValueError('Unsupported review protocol; expected version 1')
        if state['generation'] != self._seen_generation:
            # Also complete durability after a writer lost its fsync response
            # following rename. Every controller confirms a newly observed head.
            _sync_directory(self.path/'data')
            _sync_directory(self.path)
            self._seen_generation=state['generation']
        return state

    def write(self, state):
        state['generation'] += 1
        _sync_directory(self.path/'data')
        _sync_directory(self.path/'attachments')
        atomic_write(self.path/'manifest.json', encoded(state))
        self._seen_generation=state['generation']

    def put(self, array):
        array = np.ascontiguousarray(array)
        if array.dtype.kind not in 'fiu' or array.ndim != 1:
            raise ValueError('Review columns must be one-dimensional numeric arrays')
        array = array.astype(array.dtype.newbyteorder('<'), copy=False)
        stream = io.BytesIO()
        np.save(stream, array, allow_pickle=False)
        data = stream.getvalue()
        sha = hashlib.sha256(data).hexdigest()
        path = self.path/'data'/(sha+'.npy')
        if not path.exists():
            atomic_write(path, data)
        elif hashlib.sha256(path.read_bytes()).hexdigest() != sha:
            raise ValueError('Corrupt existing review data: '+sha)
        return dict(file='data/'+path.name, sha256=sha, bytes=len(data), dtype=array.dtype.str, shape=list(array.shape))

    def get(self, reference):
        sha = reference['sha256']
        if not isinstance(sha, str) or not re.fullmatch('[0-9a-f]{64}', sha) or reference['file'] != 'data/'+sha+'.npy':
            raise ValueError('Invalid review data reference')
        data = (self.path/reference['file']).read_bytes()
        if len(data) != reference['bytes'] or hashlib.sha256(data).hexdigest() != sha:
            raise ValueError('Review data integrity check failed: '+sha)
        array = np.load(io.BytesIO(data), allow_pickle=False)
        if array.dtype.str != reference['dtype'] or list(array.shape) != reference['shape']:
            raise ValueError('Review data dtype/shape differs from manifest')
        return array

    def collect(self, state):
        # Unfinished work owns its baseline and approval; retain it until a
        # complete successor is committed. Each retained round is self-contained.
        rounds = state['rounds']
        latest = max((r['number'] for r in rounds), default=0)
        retained = [r for r in rounds if r['number'] == latest or r['status'] not in ('completed', 'cancelled')]
        if len(retained) != len(rounds):
            state['rounds'] = retained
            self.write(state)
        live = {ref['file'] for r in retained for doc in r['documents'].values() for ref in self.references(doc)}
        for path in (self.path/'data').iterdir():
            if path.name.startswith('.writing-') or ('data/'+path.name not in live and re.fullmatch('[0-9a-f]{64}\\.npy', path.name)):
                path.unlink()
        images = {ref['file'] for r in retained for doc in r['documents'].values() for ref in self.image_references(doc)}
        for path in (self.path/'attachments').iterdir():
            if ('attachments/'+path.name not in images and re.fullmatch('[0-9a-f]{64}\\.png',path.name)) or path.name.startswith('.writing-'):
                _windows_retry(path.unlink)
        for path in self.path.glob('.writing-*'):
            path.unlink()
        active={r.get('claim',{}).get('token') for r in retained
                if r['status']=='ready' and r.get('claim',{}).get('expires',0)>time.time()}
        for path in self.path.glob('candidate-*'):
            match=re.fullmatch('candidate-([0-9a-f]{32})-.+',path.name)
            if match and match[1] not in active and path.is_dir():
                try:shutil.rmtree(path)
                except OSError:pass  # Retry on access if an expired writer still has files open.

    def put_image(self, data, name='Review image.png'):
        from ._native import review_image_json
        if not isinstance(data, bytes):data=bytes(data)
        image=json.loads(review_image_json(data,str(name)))
        payload=base64.b64decode(image.pop('data'),validate=True)
        sha=hashlib.sha256(payload).hexdigest()
        image.update(id=sha,sha256=sha,file='attachments/'+sha+'.png')
        path=self.path/image['file']
        if not path.exists():atomic_write(path,payload)
        self.get_image(image)
        return image

    def get_image(self, reference):
        sha=reference.get('sha256')
        if (not isinstance(sha,str) or not re.fullmatch('[0-9a-f]{64}',sha)
                or reference.get('file')!='attachments/'+sha+'.png' or reference.get('id')!=sha
                or reference.get('mime_type')!='image/png' or not isinstance(reference.get('name'),str)):
            raise ValueError('Invalid review image reference')
        data=(self.path/reference['file']).read_bytes()
        if (len(data)!=reference.get('bytes') or hashlib.sha256(data).hexdigest()!=sha
                or data[:8]!=b'\x89PNG\r\n\x1a\n' or len(data)<24
                or tuple(struct.unpack('>II',data[16:24]))!=(reference.get('width'),reference.get('height'))):
            raise ValueError('Review image integrity check failed: '+sha)
        return data

    def verify_image(self, reference):
        sha=reference.get('sha256')
        if not isinstance(sha,str) or not re.fullmatch('[0-9a-f]{64}',sha) or reference.get('file')!='attachments/'+sha+'.png':
            raise ValueError('Invalid review image reference')
        stat=(self.path/reference['file']).stat()
        stamp=(stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns,reference.get('id'),reference.get('name'),reference.get('mime_type'),reference.get('bytes'),reference.get('width'),reference.get('height'))
        if self._verified_images.get(sha)!=stamp:
            self.get_image(reference)
            self._verified_images[sha]=stamp

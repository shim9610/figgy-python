"""Isolated review builder: source imports/cwd and GPU work stay out of the UI."""
import hashlib
import os
from pathlib import Path
import runpy
import sys

from .review import Session


def build(cache):
    with Session.open(cache) as session:
        session._validation=True
        source=session.snapshot()['rounds'][-1]['source']
        os.chdir(source['cwd'])
        sys.path.insert(0,str(Path(source['entrypoint']).parent))
        namespace=runpy.run_path(source['entrypoint'],run_name='__figgy_review__')
        namespace[source['function']](session,**source['arguments'])
        session.start()
        for fid in list(session._figures):
            fig=session._figures[fid]
            if fig.backend!='native':fig=session.restore(fid,backend='native')
            png=fig.to_png()
            with session._store.locked():
                state=session._store.read()
                state['rounds'][-1]['documents'][fid]['validated_png_sha256']=hashlib.sha256(png).hexdigest()
                session._store.write(state)


if __name__=='__main__':build(sys.argv[1])

"""Opt-in, durable, turn-based chart review. No LLM runtime is required."""
from __future__ import annotations

import argparse
from contextlib import ExitStack, contextmanager
import asyncio
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import numpy as np

from ._review_diff import changes, persistent, preserved
from ._review_store import Store, digest


def _id():
    return uuid.uuid4().hex


def _ui_comment(doc):
    return next((c['text'] for c in doc['comments'] if c.get('channel')=='ui'),'')


def _replace_ui_comment(doc, text):
    doc['comments']=[c for c in doc['comments'] if c.get('channel')!='ui']
    if text:doc['comments'].append(dict(id=_id(),text=text,target=None,channel='ui'))


def _same_approved_content(previous, current):
    """Approval covers exact persistent settings AND every source payload."""
    approval=previous['approval']
    return (approval is not None
            and approval['persistent_hash']==current['baseline_hash']
            and previous['columns']==current['baseline_columns']
            and previous.get('bounded_data',{})==current.get('baseline_bounded_data',{})
            and previous['dpi']==current['dpi'])


def _carry_approval(previous, current, round_id):
    current['approval']=dict(previous['approval'],revision=current['baseline_revision'],
        settings=copy.deepcopy(current['baseline']),instance_id=current['instance_id'],
        changes=[],comment_text='',carried_from=dict(round_id=round_id,approval_id=previous['approval']['id']))


def _source(value):
    value = copy.deepcopy(value or {})
    if value.get('entrypoint'):
        path = Path(value['entrypoint']).resolve()
        value.update(entrypoint=str(path), digest=hashlib.sha256(path.read_bytes()).hexdigest())
    value.setdefault('function', 'build')
    value.setdefault('arguments', {})
    value.setdefault('cwd',str(Path.cwd()))
    return value


class _CapturedData:
    def __init__(self, native, session, figure_id, round_id, instance_id):
        self.native, self.session, self.figure_id = native, session, figure_id
        self.round_id = round_id
        self.instance_id = instance_id

    def __getattr__(self, name):
        value = getattr(self.native, name)
        if name=='show':
            def show(*args, **kwargs):
                self.session._assert_mutable(self.figure_id,self.round_id,self.instance_id)
                if self.session._validation:
                    raise RuntimeError('Source builders create Figures; the controller presents review windows')
                if self.session.status['state']=='building':
                    raise RuntimeError('Seal the review set with start() or present() before opening windows')
                fig=self.session._figures[self.figure_id]
                if any(not handle.closed for handle in fig._windows):
                    raise RuntimeError('A review Figure already has an open native view')
                return value(*args, **kwargs)
            return show
        mutations = {'apply_settings','add_series','add_series_fitted','add_series_batch',
                     'set_radial','set_bounded','fit','fit_active','drag','resize_handle',
                     'undo','redo','reset_edits'}
        if name not in mutations:
            return value
        def mutate(*args, **kwargs):
            self.session._assert_mutable(self.figure_id,self.round_id,self.instance_id)
            return value(*args, **kwargs)
        return mutate

    def upload_column(self, name, array):
        with self.session._store.locked():
            state = self.session._store.read()
            if state['rounds'][-1]['id']!=self.round_id:raise ValueError('Stale Figure from a previous review round')
            doc = self.session._mutable(state, self.figure_id)
            if doc['instance_id']!=self.instance_id:raise ValueError('Stale Figure instance; restore the current checkpoint')
            reference = self.session._store.put(array)
            self.native.upload_column(name, array)
            try:
                doc['columns'][name] = reference
                self.session._store.write(state)
            except Exception:
                self.native.remove_column(name)
                raise

    def remove_column(self, name):
        with self.session._store.locked():
            state = self.session._store.read()
            if state['rounds'][-1]['id']!=self.round_id:raise ValueError('Stale Figure from a previous review round')
            doc = self.session._mutable(state, self.figure_id)
            if doc['instance_id']!=self.instance_id:raise ValueError('Stale Figure instance; restore the current checkpoint')
            self.native.remove_column(name)
            doc['columns'].pop(name, None)
            self.session._store.write(state)


class Session:
    """A recoverable review round, with explicit approval and separate comments.

    Create source data through ``session.figure`` so it is captured before native
    uploads or notebook transfer release. Sessions and their cache are opt-in.
    """
    protocol = 1

    def __init__(self, cache_dir=None, *, source=None, backend='native', review_font=None, review_font_size=14):
        if review_font is not None:
            if not isinstance(review_font,str) or not review_font.strip():raise ValueError('review_font must name an installed font family')
            from ._review_font import font_data
            font_data(review_font)
        if not isinstance(review_font_size,(int,float)) or not 8<=review_font_size<=72:raise ValueError('review_font_size must be between 8 and 72')
        cache=Path(cache_dir) if cache_dir is not None else Path(tempfile.mkdtemp(prefix='figgyplot-review-'))
        if cache.exists() and (not cache.is_dir() or any(cache.iterdir())):
            raise ValueError('Use a dedicated empty review cache directory; use Session.open() for an existing cache')
        self._store = Store(cache)
        self._figures = {}
        self._handles = {}
        self._widgets = {}
        self._live_round = None
        self._validation = False
        self._worker_id = _id()
        with self._store.locked():
            if (self.cache_dir/'manifest.json').exists():
                raise ValueError('Review cache already exists; use Session.open(cache_dir)')
            if backend not in ('native','webgpu'):
                raise ValueError('Review backend must be native or webgpu')
            state = dict(protocol=1, session_id=_id(), generation=0, completed_work={},
                         review_style=dict(font_family=review_font,font_size=review_font_size),
                         rounds=[dict(id=_id(),number=1,status='building',source=_source(source),
                                      backend=backend,documents={},work_id=None)])
            self._store.write(state)

    @classmethod
    def open(cls, cache_dir):
        if not (Path(cache_dir)/'manifest.json').is_file():
            raise ValueError('Review cache manifest does not exist')
        session = cls.__new__(cls)
        session._store = Store(cache_dir)
        session._figures,session._handles,session._widgets = {},{},{}
        session._live_round,session._validation = None,False
        session._worker_id = _id()
        with session._store.locked():
            state = session._store.read()
            # Check retained data before maintenance so corrupt recovery cannot
            # delete another complete checkpoint's only available payload.
            for r in state['rounds']:
                for doc in r['documents'].values():
                    for ref in session._store.references(doc):session._store.get(ref)
            session._store.collect(state)
        return session

    @property
    def cache_dir(self):
        return self._store.path

    def snapshot(self):
        with self._store.locked():
            state = self._store.read()
            self._store.collect(state)
            return copy.deepcopy(state)

    def _mutable(self, state, figure_id):
        r = state['rounds'][-1]
        if r['status'] not in ('building','reviewing'):
            raise RuntimeError('Review round is sealed; wait for the next round or reopen a Figure')
        doc = r['documents'][figure_id]
        if doc.get('approval') is not None:
            raise RuntimeError('Figure is approved; reopen it before editing')
        return doc

    def _assert_mutable(self, figure_id, round_id, instance_id):
        with self._store.locked():
            state=self._store.read()
            if state['rounds'][-1]['id']!=round_id:raise ValueError('Stale Figure from a previous review round')
            doc=self._mutable(state,figure_id)
            if doc['instance_id']!=instance_id:raise ValueError('Stale Figure instance; restore the current checkpoint')

    def figure(self, *, id, **kwargs):
        from .figure import Figure
        if not isinstance(id,str) or not id:
            raise ValueError('Review Figures require a non-empty stable ID')
        with self._store.locked():
            state = self._store.read();r = state['rounds'][-1]
            if r['status'] != 'building':
                raise RuntimeError('The review set is sealed; create Figures before present()')
            if id in r['documents']:raise ValueError('Duplicate review Figure ID: '+id)
            fig = Figure(id=id,backend=kwargs.pop('backend',r['backend']),**kwargs)
            settings=fig.get_settings()
            r['documents'][id]=dict(baseline=settings,baseline_revision=fig.revision,
                baseline_hash=digest(persistent(settings)),draft=settings,draft_revision=fig.revision,
                dpi=fig.dpi,backend=fig.backend,columns={},comments=[],approval=None,instance_id=_id())
            try:self._store.write(state)
            except Exception:fig.close();raise
        self._bind(fig,id)
        return fig

    def _bind(self, fig, figure_id):
        previous=self._figures.get(figure_id)
        if previous is not None and previous is not fig:previous.close()
        with self._store.locked():
            r=self._store.read()['rounds'][-1];round_id=r['id'];instance_id=r['documents'][figure_id]['instance_id']
        fig._native = _CapturedData(fig._native,self,figure_id,round_id,instance_id)
        fig._review_session = self
        self._figures[figure_id] = fig

    def _seal(self):
        with self._figure_transaction():
            state=self._store.read();r=state['rounds'][-1]
            if r['status']=='building':
                if not r['documents']:raise ValueError('A review round needs at least one Figure')
                for fid,doc in r['documents'].items():
                    fig=self._figures[fid];settings=fig.get_settings()
                    doc.update(baseline=settings,baseline_revision=fig.revision,
                        baseline_hash=digest(persistent(settings)),draft=settings,draft_revision=fig.revision)
                    doc['baseline_columns']=copy.deepcopy(doc['columns'])
                    doc['baseline_instance_id']=doc['instance_id']
                    doc['bounded_data']=self._bounded_data(settings)
                    doc['baseline_bounded_data']=copy.deepcopy(doc['bounded_data'])
                r['status']='reviewing';self._store.write(state)
            return r['number']

    def _bounded_data(self, settings):
        # Bounded models own canonical f64/statistical values in SSOT, rather
        # than GPU columns. Cache those values separately without uploading them.
        result={}
        def collect(value,path):
            if isinstance(value,dict):
                for key,item in value.items():collect(item,path+'/'+key)
            elif isinstance(value,list):
                if value and all(isinstance(v,(int,float)) and not isinstance(v,bool) for v in value):
                    result[path]=self._store.put(np.asarray(value,dtype=np.float64))
                else:
                    for index,item in enumerate(value):collect(item,path+'/'+str(index))
            elif isinstance(value,(int,float)) and not isinstance(value,bool):
                result[path]=self._store.put(np.asarray([value]))
        for family in ('radial','categorical','boxplot','radar'):
            if family not in settings:continue
            chart=settings[family]
            if family=='radial':
                for index,item in enumerate(chart['slices']):collect(item['value'],f'/radial/slices/{index}/value')
                for index,item in enumerate((chart.get('split') or {}).get('children',[])):
                    collect(item['value'],f'/radial/split/children/{index}/value')
            else:
                for index,item in enumerate(chart['series']):collect(item['values'],f'/{family}/series/{index}/values')
        return result

    @contextmanager
    def _figure_transaction(self):
        # Figure mutations already acquire Figure -> store locks. Preserve this
        # order while collecting multiple native/browser snapshots as well.
        with ExitStack() as stack:
            for fid in sorted(self._figures):stack.enter_context(self._figures[fid]._lock)
            stack.enter_context(self._store.locked())
            yield

    def start(self):
        """Seal all Figures and their baselines without opening a view."""
        self._seal()
        return self

    def present(self):
        """Seal the review set and show its complete pending native/notebook set."""
        number=self._seal()
        if self._validation:return self
        if threading.current_thread() is not threading.main_thread():
            raise RuntimeError('Review presentation runs on the main thread')
        state=self.snapshot();r=state['rounds'][-1]
        family=state.get('review_style',{}).get('font_family')
        if family:
            from ._review_font import font_data
            font_data(family)
        prepared=[]
        try:
            for fid,doc in r['documents'].items():
                if doc['approval'] is not None:continue
                fig=self._figures.get(fid) or self.restore(fid)
                if fig.backend=='native':fig.prepare()
                prepared.append(fig)
            for fig in prepared:
                if fig.backend=='native':
                    old=self._handles.get(fig.id)
                    if old is None or old.closed:
                        handle=fig.show(block=False)
                        handle.configure_review(json.dumps(self._review_state(fig.id)))
                        self._handles[fig.id]=handle
                else:
                    from IPython.display import display
                    display(self.widget(fig))
            self._live_round=number
        except Exception:
            for handle in self._handles.values():handle.close()
            raise
        return self

    def widget(self, figure):
        """The ordinary live editor plus a separate review panel (not PNG fallback)."""
        self._live_round=self._seal()
        if isinstance(figure,str):figure=self._figures.get(figure) or self.restore(figure,backend='webgpu')
        if figure.backend!='webgpu':raise ValueError('Notebook review requires backend=webgpu')
        if figure.id not in self._figures or self._figures[figure.id] is not figure:
            raise ValueError('Figure does not belong to this review session')
        widget=figure.widget();review=self._review_state(figure.id)
        family=review.get('font_family')
        if family:
            from ._review_font import font_data
            widget.review_font_data=font_data(family)
        widget.review=review
        self._widgets[figure.id]=widget
        return widget

    def _review_state(self, figure_id):
        state=self.snapshot();doc=state['rounds'][-1]['documents'][figure_id]
        return dict(enabled=True,figure_id=figure_id,comments=_ui_comment(doc),
            target_comments=[c for c in doc['comments'] if c.get('channel')=='ui_target'],
            **state.get('review_style',{}))

    def _set_target_comments(self, figure_id, comments):
        if not isinstance(comments,list):raise ValueError('Target comments must be a list')
        ids=set()
        for item in comments:
            if not isinstance(item,dict) or set(item)-{'id','text','target','channel','label'} or not all(isinstance(item.get(k),str) and item[k].strip() for k in ('id','text','target')) or item['id'] in ids or ('label' in item and not isinstance(item['label'],str)):
                raise ValueError('Target comments require unique IDs, nonempty text and a stable target')
            ids.add(item['id'])
        with self._store.locked():
            state=self._store.read();doc=self._mutable(state,figure_id)
            updated=[c for c in doc['comments'] if c.get('channel')!='ui_target']+[dict(c,channel='ui_target') for c in comments]
            if updated!=doc['comments']:doc['comments']=updated;self._store.write(state)

    def subscribe(self, *, after=None, timeout=60):
        """Wait for one complete durable batch; does not pump UI or invoke a model."""
        if not isinstance(timeout,(int,float)) or not 0<=timeout<=3600:raise ValueError('timeout must be between 0 and 3600 seconds')
        deadline=time.monotonic()+timeout
        while True:
            events=[event for event in self.events() if event['work_id']!=after]
            if events:return events[0]
            if self.status['state'] in ('completed','cancelled'):return None
            remaining=deadline-time.monotonic()
            if remaining<=0:return None
            time.sleep(min(.05,remaining))

    def connect(self, *, after=None, timeout=None):
        """Present native review and wait for its feedback in the same process.

        The agent keeps this call pending. A separate native UI controller and
        subscriber are unnecessary; ordinary present/run_events remain available.
        """
        if timeout is not None and (not isinstance(timeout,(int,float)) or not 0<=timeout<=3600):
            raise ValueError('timeout must be between 0 and 3600 seconds or None')
        current=self.snapshot()['rounds'][-1]
        if current['backend']!='native':
            raise ValueError('connect() hosts native windows; use watch() and subscribe() for notebook review')
        if current['status']=='building' and any(fid not in self._figures for fid in current['documents']):
            raise RuntimeError('Call session.start() in the builder process before connecting to its cache')
        self.present()
        deadline=None if timeout is None else time.monotonic()+timeout
        while True:
            self.poll()
            events=[event for event in self.events() if event['work_id']!=after]
            if events:return events[0]
            if self.status['state'] in ('completed','cancelled'):return None
            if deadline is not None and time.monotonic()>=deadline:return None
            time.sleep(.02)

    def _comment_text(self, figure_id):
        return _ui_comment(self.snapshot()['rounds'][-1]['documents'][figure_id])

    def comment(self, figure_id, text, *, target=None):
        if not isinstance(text,str):raise ValueError('Review comment must be text')
        with self._store.locked():
            state=self._store.read();doc=self._mutable(state,figure_id)
            doc['comments'].append(dict(id=_id(),text=text,target=target,channel='api'))
            self._store.write(state)

    def _set_comment_text(self, figure_id, text):
        if not isinstance(text,str):raise ValueError('Review comments must be text')
        with self._store.locked():
            state=self._store.read();doc=self._mutable(state,figure_id)
            previous=_ui_comment(doc)
            if previous!=text:
                _replace_ui_comment(doc,text)
                self._store.write(state)

    def submit(self, figure_id, disposition, *, comments=None, expected_revision=None, intent='revise'):
        """Durably approve accepted state, then close views; never approve on close."""
        if disposition not in ('accept','request_changes','skip'):
            raise ValueError('Disposition must be accept, request_changes or skip')
        fig=self._figures.get(figure_id)
        if fig is None:raise ValueError('Restore the Figure before submitting it')
        if fig.backend=='webgpu' and any(not w._closed for w in fig._widgets):
            raise RuntimeError('Use await session.submit_async() to flush notebook edits')
        return self._submit(figure_id,disposition,comments,expected_revision,intent)

    async def submit_async(self, figure_id, disposition, *, comments=None, expected_revision=None, intent='revise'):
        fig=self._figures[figure_id]
        if fig.backend=='webgpu':await fig.sync()
        return self._submit(figure_id,disposition,comments,expected_revision,intent)

    def _submit(self, figure_id, disposition, comments, expected_revision, intent='revise'):
        if disposition not in ('accept','request_changes','skip'):
            raise ValueError('Unknown review disposition')
        if intent not in ('revise','finish') or (intent=='finish' and disposition!='accept'):
            raise ValueError('Finish intent requires an accepted Figure')
        if comments is not None and not isinstance(comments,str):raise ValueError('Review comments must be text')
        fig=self._figures[figure_id]
        with fig._lock, self._store.locked():
            approval=self._commit_approval(figure_id,disposition,comments,expected_revision,intent)
        # Closing a view may call observers that read the session. Release the
        # manifest lock before closing, on both first delivery and retries.
        self._close_views(fig,disposition)
        return copy.deepcopy(approval)

    def _commit_approval(self, figure_id, disposition, comments, expected_revision, intent='revise'):
        state=self._store.read();r=state['rounds'][-1];doc=r['documents'][figure_id]
        # Repeated delivery of the same approval never creates another work ID.
        if doc['approval'] is not None:
            if doc['approval']['disposition']!=disposition or doc['approval'].get('intent','revise')!=intent or (comments is not None and doc['approval']['comment_text']!=comments):
                raise ValueError('Figure already approved with different feedback')
            self._store.write(state)
            return doc['approval']
        self._mutable(state,figure_id)
        fig=self._figures[figure_id]
        if doc['instance_id']!=fig._native.instance_id:raise ValueError('Stale Figure instance; restore the current checkpoint')
        if any(not hasattr(widget,'_clients') for widget in fig._widgets):
            raise RuntimeError('Close the PNG fallback view before approving; use a live review view')
        clients=sum(len(widget._clients) for widget in fig._widgets if not widget._closed)
        if clients>1 or sum(not handle.closed for handle in fig._windows)>1:
            raise RuntimeError('Close duplicate review views before approving this Figure')
        if r['status']=='building':raise RuntimeError('Present/seal the complete review set before approval')
        fig._native.end_edit()
        revision=fig.revision
        if expected_revision is not None and revision!=expected_revision:
            raise ValueError('Stale review revision; refresh before approving')
        approved=fig.get_settings()
        doc['bounded_data']=self._bounded_data(approved)
        if comments is not None:
            _replace_ui_comment(doc,comments)
        for ref in self._store.references(doc):self._store.get(ref)
        approval=dict(id=_id(),disposition=disposition,intent=intent,revision=revision,settings=approved,
            instance_id=doc['instance_id'],
            persistent_hash=digest(persistent(approved)),changes=changes(doc['baseline'],approved),
            comment_text=_ui_comment(doc))
        doc.update(approval=approval,draft=approved,draft_revision=revision)
        if all(d['approval'] is not None for d in r['documents'].values()):
            needs_work=any(d['approval']['disposition']=='request_changes' or d['approval']['changes'] or d['comments'] for d in r['documents'].values())
            finishing=any(d['approval'].get('intent')=='finish' for d in r['documents'].values()) and not any(d['approval']['disposition']=='request_changes' for d in r['documents'].values())
            r['intent']='finish' if finishing else 'revise'
            needs_work=needs_work or finishing
            r.update(status='ready' if needs_work else 'completed',work_id=_id() if needs_work else None)
        self._store.write(state)
        self._store.collect(state)
        return approval

    def _close_views(self, fig, disposition):
        for window in list(fig._windows):window.close()
        for widget in list(fig._widgets):
            widget.review=dict(enabled=True,approved=True,disposition=disposition)
            widget.close()

    def events(self):
        state=self.snapshot()
        return [dict(protocol=1,session_id=state['session_id'],round_id=r['id'],work_id=r['work_id'],
                     intent=r.get('intent','revise'),
                     manifest=str(self.cache_dir/'manifest.json'),source=r['source'])
                for r in state['rounds'] if r['status']=='ready']

    @property
    def status(self):
        r=self.snapshot()['rounds'][-1]
        return dict(round=r['number'],state=r['status'],work_id=r['work_id'],
                    pending=[] if r['status'] in ('completed','cancelled') else [fid for fid,doc in r['documents'].items() if doc['approval'] is None],
                    error=r.get('error'))

    def feedback(self, work_id):
        state=self.snapshot()
        r=next((r for r in state['rounds'] if r['work_id']==work_id and r['status']=='ready'),None)
        if r is None:raise ValueError('Stale or unknown review work ID')
        return dict(protocol=1,session_id=state['session_id'],round=copy.deepcopy(r))

    def feedback_summary(self, work_id):
        """Readable object groups linked to every exact snapshot-diff operation."""
        from ._review_summary import summary
        return summary(self.feedback(work_id))

    def feedback_details(self, work_id, figure_id, *, target=None, change_id=None):
        """Inspect exact changes and object snapshots without another render."""
        from ._review_summary import details
        return details(self.feedback(work_id),figure_id,target=target,change_id=change_id)

    def claim(self, work_id, *, worker_id=None, seconds=1800):
        """Lease one staging writer before an agent edits source for this work."""
        from .figure import _timeout
        seconds=_timeout(seconds);worker_id=worker_id or self._worker_id
        if not isinstance(worker_id,str) or not worker_id:raise ValueError('worker_id must be non-empty text')
        with self._store.locked():
            state=self._store.read();r=state['rounds'][-1]
            if r['status']!='ready' or r['work_id']!=work_id:raise ValueError('Stale or unknown review work ID')
            claim=r.get('claim');now=time.time()
            if claim and claim['expires']>now and claim['worker_id']!=worker_id:
                raise RuntimeError('Review work is already claimed by another source writer')
            if not claim or claim['worker_id']!=worker_id or claim['expires']<=now:
                claim=dict(token=_id(),worker_id=worker_id)
            claim['expires']=now+seconds;r['claim']=claim;self._store.write(state)
            return copy.deepcopy(claim)

    def restore(self, figure_id, *, backend=None):
        from .figure import Figure
        with self._store.locked():
            state=self._store.read();doc=state['rounds'][-1]['documents'][figure_id]
            settings=doc['draft'];rect=settings['config']['chart_area'];dpi=doc['dpi']
            fig=Figure(figsize=(rect['width']/dpi,rect['height']/dpi),dpi=dpi,
                       backend=backend or doc['backend'],id=figure_id,
                       pool_bytes=max(8*1024**2,sum(ref['shape'][0]*8 for ref in doc['columns'].values())*2))
            try:
                for name,ref in doc['columns'].items():fig._native.upload_column(name,self._store.get(ref))
                family=next((k for k in ('radial','categorical','boxplot','radar') if k in settings),None)
                if family=='radial':fig._native.set_radial(json.dumps(settings[family]))
                elif family:fig._native.set_bounded(family,json.dumps(settings[family]))
                else:
                    # Establish panel/overlay identities before registering the
                    # complete series batch; no positional owner is guessed.
                    bootstrap=copy.deepcopy(settings);bootstrap['series']=[]
                    def empty_membership(config):
                        for overlay in config.get('overlays',[]):overlay['series']=[]
                        for panel in config.get('subplots',[]):
                            panel['series']=[];empty_membership(panel['config'])
                    empty_membership(bootstrap['config'])
                    fig.apply_settings(bootstrap)
                if not family and settings['series']:
                    if fig.backend=='webgpu':
                        for spec in settings['series']:fig._native.cache_series_extents(json.dumps(spec))
                    fig._native.add_series_batch(json.dumps(settings['series']),json.dumps(settings['config']))
                fig.apply_settings(settings)
                if persistent(fig.get_settings())!=persistent(settings):
                    raise ValueError('Restored settings differ from the complete checkpoint')
                fig._next_series=len(settings['series'])
                doc['instance_id']=_id()
                self._store.write(state)
            except Exception:
                fig.close();raise
        self._bind(fig,figure_id)
        return fig

    def reopen(self, figure_id):
        with self._store.locked():
            state=self._store.read();r=state['rounds'][-1]
            if r['status'] not in ('reviewing','ready'):raise RuntimeError('Round cannot be reopened')
            r['documents'][figure_id]['approval']=None
            r.pop('claim',None)
            r.update(status='reviewing',work_id=None)
            self._store.write(state)
        return self._figures.get(figure_id) or self.restore(figure_id)

    def cancel(self):
        with self._store.locked():
            state=self._store.read();state['rounds'][-1]['status']='cancelled'
            self._store.write(state)
        self.close()

    def finish(self, work_id, *, claim_token=None, timeout=180):
        """Save the accepted review and finish without opening another review.

        Recorded builders are executed and rendered once to verify the source
        still reproduces the exact accepted settings and arrays. Manual sessions
        without source retain their complete approved binary checkpoint.
        """
        state=self.snapshot()
        if work_id in state['completed_work']:
            if work_id not in state.get('finished_work',{}):
                raise ValueError('Work already regenerated; finish the current review round instead')
            return state['finished_work'][work_id]
        feedback=self.feedback(work_id)
        if feedback['round']['source'].get('entrypoint'):
            number=self.regenerate(work_id,claim_token=claim_token,timeout=timeout,_finish=True)
        else:
            if claim_token is None:claim_token=self.claim(work_id)['token']
            with self._store.locked():
                state=self._store.read();r=state['rounds'][-1]
                if work_id in state['completed_work']:
                    if work_id not in state.get('finished_work',{}):raise ValueError('Work already regenerated')
                    return state['finished_work'][work_id]
                if r['status']!='ready' or r['work_id']!=work_id:raise ValueError('Stale or unknown review work ID')
                if r.get('claim',{}).get('token')!=claim_token or r['claim']['expires']<=time.time():
                    raise ValueError('Source writer lease is invalid or expired')
                for doc in r['documents'].values():
                    for ref in self._store.references(doc):self._store.get(ref)
                r.update(status='completed',intent='finish')
                number=r['number'];state['completed_work'][work_id]=number
                state.setdefault('finished_work',{})[work_id]=number
                self._store.write(state);self._store.collect(state)
        self.close()
        return number

    def poll(self):
        """Pump native input and durable submissions; call only on the main thread."""
        from .desktop import poll_events
        poll_events()
        state=self.snapshot();r=state['rounds'][-1]
        if self._live_round is not None and r['number']!=self._live_round:
            self.close();self.present();return
        failed=False
        for fid,handle in list(self._handles.items()):
            request=json.loads(handle.review_request_json())
            if request is None:continue
            try:
                self._set_target_comments(fid,request.get('target_comments',[]))
                self.submit(fid,request['disposition'],comments=request['comments'],expected_revision=request['revision'],intent=request.get('intent','revise'))
            except Exception as exc:
                handle.review_result(str(exc))
                failed=True
        if failed:return
        # Native editor changes bypass Python callbacks. Capture accepted drafts
        # here for disconnect recovery, without waiting for a GPU readback.
        with self._figure_transaction():
            state=self._store.read();r=state['rounds'][-1];changed=False
            for fid,fig in self._figures.items():
                doc=r['documents'].get(fid)
                if doc and fig._native is not None and doc['instance_id']!=fig._native.instance_id:continue
                if doc and doc['approval'] is None and fig._native is not None and doc['draft_revision']!=fig.revision:
                    doc.update(draft=fig.get_settings(),draft_revision=fig.revision);changed=True
                handle=self._handles.get(fid)
                if doc and doc['approval'] is None and handle is not None:
                    draft=json.loads(handle.review_draft_json())
                    text=draft.get('comments') or ''
                    targeted=draft.get('target_comments') or []
                    previous=[v for v in doc['comments'] if v.get('channel')=='ui_target']
                    if targeted!=previous:
                        doc['comments']=[v for v in doc['comments'] if v.get('channel')!='ui_target']+[dict(v,channel='ui_target') for v in targeted];changed=True
                    if text!=_ui_comment(doc):
                        _replace_ui_comment(doc,text);changed=True
            if changed:self._store.write(state)

    def run_events(self, *, on_status=None):
        """Wait through review and disconnected-agent periods until accept/cancel."""
        previous=None
        while True:
            self.poll()
            status=self.status
            if status!=previous and on_status is not None:on_status(status)
            previous=status
            if status['state'] in ('completed','cancelled'):break
            time.sleep(.02)

    async def watch(self):
        """Notebook controller: publish the next complete set after agent work."""
        if self._live_round is None:self.present()
        while True:
            r=self.snapshot()['rounds'][-1]
            if r['status'] in ('completed','cancelled'):return
            if r['number']!=self._live_round:
                self.close();self.present()
            await asyncio.sleep(.1)

    def regenerate(self, work_id, *, superseded=None, claim_token=None, present=False, timeout=180, _finish=False):
        """Run updated source, render every result, reconcile edits, publish once."""
        superseded=dict(superseded or {})
        if any(not isinstance(reason,str) or not reason.strip() for reason in superseded.values()):
            raise ValueError('Superseded edits/Figures require non-empty reasons')
        state=self.snapshot()
        if work_id in state['completed_work']:
            if _finish and work_id not in state.get('finished_work',{}):raise ValueError('Work already regenerated')
            return state['completed_work'][work_id]
        if claim_token is None:claim_token=self.claim(work_id)['token']
        feedback=self.feedback(work_id);old=feedback['round'];source=_source(old['source'])
        if old.get('intent')=='finish' and not _finish:
            raise ValueError('This is a finish request; use finish() rather than creating another review round')
        if old.get('claim',{}).get('token')!=claim_token or old['claim']['expires']<=time.time():
            raise ValueError('Source writer lease is invalid or expired')
        known={c['id'] for doc in old['documents'].values() for c in doc['approval']['changes']}|{'figure:'+fid for fid in old['documents']}
        if set(superseded)-known:raise ValueError('Unknown superseded edit or Figure ID')
        if not source.get('entrypoint'):raise ValueError('Record a source entrypoint before regeneration')
        from .figure import _timeout
        timeout=_timeout(timeout)
        with tempfile.TemporaryDirectory(prefix='candidate-'+claim_token+'-',dir=str(self.cache_dir)) as candidate_path:
            candidate=Session(candidate_path,source=source,backend=old['backend']);candidate._validation=True
            try:
                result=subprocess.run([sys.executable,'-m','figgyplot._review_runner',candidate_path],
                                      capture_output=True,text=True,timeout=timeout)
                if result.returncode:
                    raise RuntimeError('Candidate execution/render failed:\n'+result.stderr[-4000:])
                current=candidate.snapshot()['rounds'][-1]
                if not all(doc.get('validated_png_sha256') for doc in current['documents'].values()):
                    raise ValueError('Candidate set lacks complete render validation')
                for fid,doc in old['documents'].items():
                    if fid not in current['documents']:
                        if 'figure:'+fid not in superseded:raise ValueError('Candidate omitted Figure '+fid)
                        continue
                    for change in doc['approval']['changes']:
                        if change['id'] not in superseded and not preserved(change,current['documents'][fid]['baseline']):
                            raise ValueError('Source did not reproduce approved edit: '+fid+' '+change['path'])
                    successor=current['documents'][fid]
                    same=_same_approved_content(doc,successor)
                    if _finish and not same:
                        raise ValueError('Finish must preserve the exact approved settings and data: '+fid)
                    if same and (doc['approval']['disposition']=='accept' or _finish):
                        _carry_approval(doc,successor,old['id'])
                        if _finish:successor['approval'].update(disposition='accept',intent='finish')
                if _finish and set(current['documents'])!=set(old['documents']):
                    raise ValueError('Finish cannot add or remove Figures')
                if _finish or all(doc['approval'] is not None for doc in current['documents'].values()):
                    current['status']='completed'
                if _source(source)['digest']!=source['digest']:raise ValueError('Source changed during candidate validation')
                with self._store.locked():
                    state=self._store.read()
                    if work_id in state['completed_work']:
                        if _finish and work_id not in state.get('finished_work',{}):raise ValueError('Work already regenerated')
                        return state['completed_work'][work_id]
                    active=state['rounds'][-1]
                    if active['status']!='ready' or active['work_id']!=work_id:
                        raise ValueError('Stale round; candidate was not published')
                    if active.get('claim',{}).get('token')!=claim_token or active['claim']['expires']<=time.time():
                        raise ValueError('Source writer lease expired during validation')
                    for doc in current['documents'].values():
                        for key in ('columns','baseline_columns','bounded_data','baseline_bounded_data'):
                            for name,ref in list(doc.get(key,{}).items()):
                                doc[key][name]=self._store.put(candidate._store.get(ref))
                    current.update(number=active['number']+1,source=source,superseded=superseded)
                    active['status']='completed';state['rounds'].append(current)
                    state['completed_work'][work_id]=current['number']
                    if _finish:state.setdefault('finished_work',{})[work_id]=current['number']
                    self._store.write(state);self._store.collect(state)
                    number=current['number']
            except Exception as exc:
                try:
                    with self._store.locked():
                        state=self._store.read();active=state['rounds'][-1]
                        if active['status']=='ready' and active['work_id']==work_id:
                            active['error']=dict(type=type(exc).__name__,message=str(exc))
                            self._store.write(state)
                except OSError:pass
                raise
            finally:
                candidate.close()
        if present:
            self.close();self.present()
        return number

    def close(self):
        for fig in list(self._figures.values()):fig.close()
        self._figures.clear();self._handles.clear();self._widgets.clear()

    def __enter__(self):return self
    def __exit__(self,*args):self.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['protocol','skill','status','events','subscribe','connect','feedback','claim','regenerate','finish','show','cancel'])
    parser.add_argument('cache',nargs='?')
    parser.add_argument('work',nargs='?')
    parser.add_argument('--superseded',help='JSON file mapping edit IDs or figure:ID to reasons')
    parser.add_argument('--after',help='Last delivered work ID for feedback subscription')
    parser.add_argument('--worker',help='Stable agent/staging-workspace identifier for a writer lease')
    parser.add_argument('--claim-token',help='Writer lease token returned by claim')
    parser.add_argument('--timeout',type=float,help='Maximum wait or candidate execution/render seconds; connect waits indefinitely by default')
    parser.add_argument('--summary',action='store_true',help='Object-grouped feedback summary with links to exact change IDs')
    parser.add_argument('--figure',help='Figure ID for exact feedback details')
    parser.add_argument('--target',help='Stable editor/comment object ID within --figure')
    parser.add_argument('--change',help='Exact change ID within --figure')
    args=parser.parse_args()
    if (args.summary or args.figure is not None or args.target is not None or args.change is not None) and args.action!='feedback':
        parser.error('summary/figure/target/change options apply only to feedback')
    if args.summary and (args.figure is not None or args.target is not None or args.change is not None):
        parser.error('--summary cannot be combined with detail filters')
    if (args.target is not None or args.change is not None) and args.figure is None:
        parser.error('--target and --change require --figure')
    package=Path(__file__).parent
    if args.action=='protocol':
        schema=str(package/'review-feedback-v1.schema.json')
        print(json.dumps(dict(protocol=1,skill=str(package/'skills/figgyplot-review/SKILL.md'),schema=schema,event_schema=schema+'#/$defs/events',summary_schema=schema+'#/$defs/summary',details_schema=schema+'#/$defs/details')));return
    if args.action=='skill':
        print((package/'skills/figgyplot-review/SKILL.md').read_text(encoding='utf-8'));return
    if not args.cache:parser.error('cache is required for this action')
    with Session.open(args.cache) as session:
        if args.action=='status':result=session.status
        elif args.action=='events':result=session.events()
        elif args.action=='subscribe':result=session.subscribe(after=args.after,timeout=args.timeout if args.timeout is not None else 60)
        elif args.action=='connect':result=session.connect(after=args.after,timeout=args.timeout)
        elif args.action=='feedback':
            if args.summary:result=session.feedback_summary(args.work)
            elif args.figure is not None:result=session.feedback_details(args.work,args.figure,target=args.target,change_id=args.change)
            else:result=session.feedback(args.work)
        elif args.action=='claim':result=session.claim(args.work,worker_id=args.worker)
        elif args.action=='regenerate':
            if not args.claim_token:parser.error('regenerate requires --claim-token from claim')
            superseded=json.loads(Path(args.superseded).read_text()) if args.superseded else None
            result=dict(round=session.regenerate(args.work,superseded=superseded,claim_token=args.claim_token,timeout=args.timeout if args.timeout is not None else 180))
        elif args.action=='finish':
            if not args.claim_token:parser.error('finish requires --claim-token from claim')
            result=dict(round=session.finish(args.work,claim_token=args.claim_token,timeout=args.timeout if args.timeout is not None else 180),finished=True)
        elif args.action=='show':session.present();session.run_events();result=session.events()
        else:session.cancel();result={'cancelled':True}
        print(json.dumps(result,ensure_ascii=False,allow_nan=False))


if __name__=='__main__':main()

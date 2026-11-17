"""Derived review views; exact snapshot diffs remain the validation authority."""
import copy
import json

from ._review_diff import locate


def _bindings(state):
    from ._native import review_object_bindings_json
    return json.loads(review_object_bindings_json(json.dumps(state, allow_nan=False)))


def _lookup(state, path, selectors):
    try:
        return True, locate(state, path, selectors)[1]
    except (KeyError, IndexError, StopIteration, ValueError, TypeError):
        return False, None


def _preview(value, *, text=False):
    if text and isinstance(value, list):
        value = ''.join(v.get('text', '') for v in value)
    if value is None or isinstance(value, (bool, int, float)):
        return dict(value=value, truncated=False)
    encoded = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, separators=(',', ':'))
    return dict(value=encoded[:160], truncated=len(encoded)>160)


def _rich_signature(segments):
    text, styles = '', []
    for segment in segments if isinstance(segments,list) else []:
        value = segment.get('text','')
        flags = tuple(sorted((k,v) for k,v in segment.items() if k!='text' and v))
        if flags:
            styles.extend((index, flags) for index in range(len(text),len(text)+len(value)))
        text += value
    return text, styles


def _document(doc):
    before, after = doc['baseline'], doc['approval']['settings']
    states = dict(before=before, after=after)
    bindings = {side:_bindings(state) for side,state in states.items()}
    objects = {v['id']:v for side in ('before','after') for v in bindings[side]}
    groups = {}

    def group(target, label=None):
        if target not in groups:
            binding = objects.get(target, {})
            label_preview = _preview(label or binding.get('label', target))
            groups[target] = dict(target=target, label=label_preview['value'], label_truncated=label_preview['truncated'],
                                  scope=binding.get('kind', 'unresolved'), change_count=0,
                                  properties=[], comments=[], _changes=[], _properties={})
        return groups[target]

    for change in doc['approval']['changes']:
        side = 'before' if change['op']=='remove' else 'after'
        try:
            actual, _ = locate(states[side], change['path'], change['selectors'])
        except (KeyError, IndexError, StopIteration, ValueError, TypeError):
            side = 'after' if side=='before' else 'before'
            actual, _ = locate(states[side], change['path'], change['selectors'])
        matches = [(len(path), binding, path) for binding in bindings[side] for path in binding['paths']
                   if actual==path or actual.startswith(path+'/')]
        _, binding, root = max(matches, key=lambda item:item[0])
        item = group(binding['id'])
        item['_changes'].append(change)
        item['change_count'] += 1
        # A rich text document is one readable property even when its exact
        # diff contains separate character/style operations. IDs are retained.
        parts = change['path'].split('/')
        text = 'segments' in parts
        raw_property = '/'.join(parts[:parts.index('segments')+1]) if text else change['path']
        actual_parts = actual.split('/')
        property_path = '/'.join(actual_parts[:actual_parts.index('segments')+1]) if text else actual
        relative = property_path[len(root):] or '/'
        key = (relative, change['op']) if change['op']=='move' else (relative, '')
        if key not in item['_properties']:
            old_exists, old = _lookup(before, raw_property, change['selectors'])
            new_exists, new = _lookup(after, raw_property, change['selectors'])
            field = dict(path=relative, kind='rich_text' if text else change['op'],
                         before_exists=old_exists, after_exists=new_exists,
                         before=_preview(old, text=text), after=_preview(new, text=text),
                         operation_ids=[])
            if text:
                old_text, old_styles = _rich_signature(old)
                new_text, new_styles = _rich_signature(new)
                field['text_changed'] = old_text != new_text
                field['formatting_changed'] = old_styles != new_styles
            item['_properties'][key] = field
            item['properties'].append(field)
        field = item['_properties'][key]
        field['operation_ids'].append(change['id'])
    figure_comments = []
    for comment in doc['comments']:
        if comment.get('target'):
            group(comment['target'], comment.get('label'))['comments'].append(comment)
        else:
            figure_comments.append(comment)
    return states, bindings, groups, figure_comments


def _public(item, figure_id):
    return dict({k:v for k,v in item.items() if not k.startswith('_')},
                details=dict(figure_id=figure_id, target=item['target']))


def summary(feedback):
    round_ = feedback['round']
    figures = []
    for fid,doc in round_['documents'].items():
        _, _, groups, comments = _document(doc)
        approval = doc['approval']
        figures.append(dict(id=fid, disposition=approval['disposition'], intent=approval.get('intent','revise'),
                            change_count=len(approval['changes']), comment_count=len(doc['comments']),
                            data_changed=doc.get('baseline_columns',{})!=doc.get('columns',{}) or doc.get('baseline_bounded_data',{})!=doc.get('bounded_data',{}),
                            comments=comments, objects=[_public(v,fid) for v in groups.values()],
                            details=dict(figure_id=fid)))
    return dict(protocol=1, view='summary', session_id=feedback['session_id'],
                round_id=round_['id'], work_id=round_['work_id'], intent=round_.get('intent','revise'),
                source=round_['source'], figures=figures,
                counts=dict(figures=len(figures), objects=sum(len(f['objects']) for f in figures),
                            changes=sum(f['change_count'] for f in figures), comments=sum(f['comment_count'] for f in figures)))


def details(feedback, figure_id, *, target=None, change_id=None):
    round_ = feedback['round']
    if figure_id not in round_['documents']:
        raise ValueError('Unknown Figure ID: '+figure_id)
    states, bindings, groups, comments = _document(round_['documents'][figure_id])
    selected = list(groups.values())
    if target is not None:
        if target not in groups:
            raise ValueError('No feedback for this object: '+target)
        selected = [groups[target]]
        comments = []
    if change_id is not None:
        selected = [g for g in selected if any(c['id']==change_id for c in g['_changes'])]
        if not selected:
            raise ValueError('Unknown change ID for this Figure/target: '+change_id)
    objects = []
    for item in selected:
        snapshot = {}
        for side,state in states.items():
            paths = next((b['paths'] for b in bindings[side] if b['id']==item['target']), [])
            snapshot[side] = {p:_lookup(state,p,{})[1] for p in paths if _lookup(state,p,{})[0]}
        objects.append(dict(_public(item,figure_id), snapshots=snapshot))
    selected_ids = {c['id'] for item in selected for c in item['_changes'] if change_id is None or c['id']==change_id}
    changes = [c for c in round_['documents'][figure_id]['approval']['changes'] if c['id'] in selected_ids]
    return dict(protocol=1, view='details', session_id=feedback['session_id'], round_id=round_['id'],
                work_id=round_['work_id'], figure_id=figure_id, comments=comments, objects=objects,
                selection=dict(target=target,change_id=change_id), changes=copy.deepcopy(changes))

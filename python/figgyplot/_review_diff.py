"""Exact persistent changes with identity selectors for source reconciliation."""
import copy
import json

from ._review_store import digest


def persistent(state):
    from ._native import persistent_settings_json
    return json.loads(persistent_settings_json(json.dumps(state, allow_nan=False)))


def escape(value):
    return str(value).replace('~', '~0').replace('/', '~1')


def _selector(path, item, index, document):
    if not isinstance(item, dict):
        return None
    for key in ('series_id', 'id'):
        if isinstance(item.get(key), str):
            return {'key': key, 'value': item[key]}
    if path == '/config/subplots':
        return {'panel': document['identity']['panels'][index+1]['id']}
    if path.endswith('/overlays') and path.startswith('/config'):
        pieces = path.split('/')
        owner = int(pieces[3])+1 if len(pieces)>3 and pieces[2]=='subplots' else 0
        return {'overlay': document['identity']['panels'][owner]['overlays'][index]}
    return None


def resolve(document, path, selectors):
    parts = path.split('/')[1:]
    value = document
    actual = []
    for encoded in parts:
        key = encoded.replace('~1', '/').replace('~0', '~')
        if isinstance(value, list):
            selection = selectors.get('/'+'/'.join(actual))
            if selection:
                if 'key' in selection:
                    key = next(i for i,v in enumerate(value) if v.get(selection['key']) == selection['value'])
                elif 'panel' in selection:
                    key = next(i-1 for i,v in enumerate(document['identity']['panels']) if v['id']==selection['panel'])
                else:
                    owner = int(actual[2])+1 if len(actual)>2 and actual[1]=='subplots' else 0
                    key = document['identity']['panels'][owner]['overlays'].index(selection['overlay'])
            else:
                key = int(key)
        value = value[key]
        actual.append(escape(key))
    return value


def changes(before, after):
    before, after = persistent(before), persistent(after)
    result = []

    def emit(op, path, a, b, selectors, **extra):
        change = dict(op=op, path=path, before_exists=op!='add', after_exists=op!='remove',
                      before=copy.deepcopy(a), after=copy.deepcopy(b), selectors=copy.deepcopy(selectors), **extra)
        change['id'] = digest(change)
        change['object_id'] = 'figure/'+after['identity']['figure']
        for selector in selectors.values():
            change['object_id'] += '/'+str(selector.get('value', selector.get('panel', selector.get('overlay'))))
        result.append(change)

    def walk(a, b, path, selectors):
        if a == b:
            return
        if isinstance(a, dict) and isinstance(b, dict):
            for key in sorted(set(a)|set(b)):
                child = path+'/'+escape(key)
                if key not in a: emit('add',child,None,b[key],selectors)
                elif key not in b: emit('remove',child,a[key],None,selectors)
                else: walk(a[key],b[key],child,selectors)
        elif isinstance(a, list) and isinstance(b, list):
            ka = [_selector(path,v,i,before) for i,v in enumerate(a)]
            kb = [_selector(path,v,i,after) for i,v in enumerate(b)]
            if (a or b) and all(v is not None for v in ka+kb) and len({json.dumps(v,sort_keys=True) for v in ka})==len(ka) and len({json.dumps(v,sort_keys=True) for v in kb})==len(kb):
                current, keys = copy.deepcopy(a), ka[:]
                for i in range(len(keys)-1,-1,-1):
                    if keys[i] not in kb:
                        emit('remove',path+'/'+str(i),current[i],None,dict(selectors, **{path:keys[i]}))
                        keys.pop(i);current.pop(i)
                for i,key in enumerate(kb):
                    selected = dict(selectors, **{path:key})
                    if key not in keys:
                        emit('add',path+'/'+str(i),None,b[i],selected)
                        keys.insert(i,key);current.insert(i,copy.deepcopy(b[i]))
                    else:
                        old = keys.index(key)
                        if old != i:
                            emit('move',path+'/'+str(i),current[old],current[old],selected, from_path=path+'/'+str(old))
                            keys.insert(i,keys.pop(old));current.insert(i,current.pop(old))
                        walk(current[i],b[i],path+'/'+str(i),selected)
            elif len(a)==len(b):
                for i,(old,new) in enumerate(zip(a,b)):walk(old,new,path+'/'+str(i),selectors)
            else:
                emit('replace',path,a,b,selectors)
        else:
            emit('replace',path,a,b,selectors)
    walk(before,after,'',{})
    return result


def preserved(change, document):
    try:
        value = resolve(persistent(document), change['path'], change['selectors'])
    except (KeyError, IndexError, StopIteration, ValueError, TypeError):
        return not change['after_exists']
    if not change['after_exists']:
        return False
    if change['op'] == 'move':
        # Selection resolves the item; order is checked against the new index.
        parent, index = change['path'].rsplit('/',1)
        try:
            return resolve(persistent(document),parent,change['selectors'])[int(index)] == value
        except (KeyError, IndexError, ValueError, TypeError):
            return False
    return value == change['after']

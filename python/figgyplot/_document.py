"""Stable document addresses and grid placement, independent of GPU storage."""
from collections.abc import Mapping
import copy
import math
import uuid


def identifier(value):
    if not isinstance(value, str) or not value:
        raise ValueError('IDs must be nonempty strings')
    return value


def initial_identity(figure_id=None):
    return dict(figure=identifier(figure_id or str(uuid.uuid4())),
                panels=[dict(id='main', overlays=[])], layout=None, groups={}, retired=[])


def panel_config(state, panel_id):
    panels = state['identity']['panels']
    for index, panel in enumerate(panels):
        if panel['id'] == panel_id:
            return state['config'] if index == 0 else state['config']['subplots'][index-1]['config']
    raise ValueError(f'subplot {panel_id!r} no longer exists')


def panel_index(state, panel_id):
    for index, panel in enumerate(state['identity']['panels']):
        if panel['id'] == panel_id:
            return index
    raise ValueError(f'subplot {panel_id!r} no longer exists')


def overlay_config(state, panel_id, overlay_id):
    index = panel_index(state, panel_id)
    try:
        overlay = state['identity']['panels'][index]['overlays'].index(overlay_id)
    except ValueError:
        raise ValueError(f'overlay {overlay_id!r} no longer exists') from None
    return panel_config(state, panel_id)['overlays'][overlay]


def target_layer(state, panel_id, overlay_id=None):
    index = panel_index(state, panel_id)
    if overlay_id is None:
        return 'Base' if index == 0 else {'Subplot': index-1}
    overlay = state['identity']['panels'][index]['overlays'].index(overlay_id)
    return {'Overlay': overlay} if index == 0 else {'SubplotOverlay': [index-1, overlay]}


def validate(state):
    """Reject invalid host metadata before native or notebook state changes."""
    meta = state.get('identity')
    if meta is None:
        return
    if set(meta)-{'tick_modes'} != {'figure', 'panels', 'layout', 'groups', 'retired'}:
        raise ValueError('unknown or missing identity metadata fields')
    panels = meta['panels']
    if len(panels) != len(state['config'].get('subplots', [])) + 1:
        raise ValueError('panel identities must match the document')
    seen = {identifier(meta['figure'])}
    if len(set(meta['retired'])) != len(meta['retired']):
        raise ValueError('duplicate retired object identity')
    for i, panel in enumerate(panels):
        if set(panel) != {'id', 'overlays'}:
            raise ValueError('unknown panel identity fields')
        cfg = state['config'] if i == 0 else state['config']['subplots'][i-1]['config']
        if len(panel['overlays']) != len(cfg.get('overlays', [])):
            raise ValueError('overlay identities must match the document')
        for value in [panel['id'], *panel['overlays']]:
            if identifier(value) in seen:
                raise ValueError(f'duplicate object ID: {value}')
            seen.add(value)
    owners={p['id']:{'bottom_x','top_x','left_y','right_y'} for p in panels}
    owners.update({o:{'y_axis'} for p in panels for o in p['overlays']})
    modes=meta.get('tick_modes',{})
    if not isinstance(modes,dict) or any(owner not in owners or not isinstance(axes,dict)
        or set(axes)-owners[owner] or any(mode not in ('Auto','Fixed') for mode in axes.values())
        for owner,axes in modes.items()):
        raise ValueError('invalid tick mode or axes owner')
    if meta['layout'] is not None:
        layout = meta['layout']
        if set(layout) != {'grid', 'placement', 'row_weights', 'column_weights', 'gap', 'size'}:
            raise ValueError('unknown layout fields')
        slots = grid_slots(layout['grid'])
        placement = layout['placement']
        if set(placement) - set(slots):
            raise ValueError('placement references an unknown grid slot')
        if len(set(placement.values())) != len(placement):
            raise ValueError('a subplot cannot occupy multiple slots')
        if set(placement.values()) != {p['id'] for p in panels}:
            raise ValueError('each subplot needs exactly one slot')
        dimensions = (len(layout['grid']), len(layout['grid'][0]))
        for key, count in zip(('row_weights', 'column_weights'), dimensions):
            weights = layout[key]
            if len(weights) != count or any(not math.isfinite(float(w)) or w <= 0 for w in weights):
                raise ValueError('grid weights must be positive and match the grid')
        if not math.isfinite(float(layout['gap'])) or layout['gap'] < 0:
            raise ValueError('grid gap must be nonnegative and finite')
    # Group membership is identity-only; axis values stay in the renderer SSOT.
    for group, definition in meta['groups'].items():
        identifier(group)
        if set(definition) != {'axis', 'members'} or definition['axis'] not in ('x', 'y'):
            raise ValueError('shared axis groups need an axis and member IDs')
        members = definition['members']
        if set(members) - {p['id'] for p in panels} or len(set(members)) != len(members):
            raise ValueError('invalid shared-axis group membership')
    validate_features(state)


def object_ids(state):
    result = set()
    for panel in state.get('identity', {}).get('panels', []):
        result.add('panel/'+panel['id'])
        result.update('overlay/'+value for value in panel['overlays'])
    family = next((k for k in ('radial', 'categorical', 'boxplot', 'radar') if state.get(k)), None)
    owner = state[family] if family else state['config']
    result.update('annotation/'+item['id'] for item in owner.get('annotations', {}).get('items', []))
    return result


def tick_owners(meta, owner, key):
    owners={owner};dimension={'bottom_x':'x','left_y':'y'}.get(key)
    if dimension is None:return owners
    while True:
        before=len(owners)
        for group in meta['groups'].values():
            if group['axis']==dimension and owners.intersection(group['members']):owners.update(group['members'])
        if len(owners)==before:return owners


def set_tick_mode(state, panel_id, overlay_id, side, automatic, *, paired=True, spacing=None):
    meta=state.get('identity')
    if meta is None:return
    owner=overlay_id if overlay_id and side in ('right_y','y_axis') else panel_id
    key='y_axis' if owner==overlay_id else side
    def assign(member, key):
        if automatic is not None:
            meta.setdefault('tick_modes',{}).setdefault(member,{})[key]='Auto' if automatic else 'Fixed'
        else:
            modes=meta.get('tick_modes',{})
            if member in modes:
                modes[member].pop(key,None)
                if not modes[member]:modes.pop(member)
            if not modes:meta.pop('tick_modes',None)
    for member in tick_owners(meta,owner,key):
        assign(member,key)
        if spacing is not None and key in ('bottom_x','left_y'):panel_config(state,member)[key]['major_spacing']=spacing
    peer={'bottom_x':'top_x','top_x':'bottom_x','left_y':'right_y','right_y':'left_y'}.get(key)
    cfg=panel_config(state,panel_id)
    if paired and peer and all(cfg[key].get(k)==cfg[peer].get(k) for k in ('min','max','scale','inverted')):
        for member in tick_owners(meta,owner,peer):assign(member,peer)


def manual_tick_patch(state, patch, panel_id=None, overlay_id=None, _claimed=None):
    """Configuration of a numeric major spacing explicitly selects fixed ticks."""
    panel_id=panel_id or state['identity']['panels'][0]['id']
    if _claimed is None:_claimed=set()
    for key in ('bottom_x','top_x','left_y','right_y','y_axis'):
        if isinstance(patch.get(key),dict) and 'major_spacing' in patch[key]:
            owner=overlay_id if overlay_id and key in ('right_y','y_axis') else panel_id
            claim=(tuple(sorted(tick_owners(state['identity'],owner,key))),key)
            if claim in _claimed:continue
            _claimed.add(claim)
            set_tick_mode(state,panel_id,overlay_id,key,False,paired=False,spacing=patch[key]['major_spacing'])
    for i,overlay in enumerate(patch.get('overlays',[])):
        ids=next(p['overlays'] for p in state['identity']['panels'] if p['id']==panel_id)
        if i<len(ids):manual_tick_patch(state,overlay,panel_id,ids[i],_claimed)
    for i,panel in enumerate(patch.get('subplots',[])):
        if i+1<len(state['identity']['panels']):
            manual_tick_patch(state,panel.get('config',{}),state['identity']['panels'][i+1]['id'],_claimed=_claimed)


def track_identities(before, after):
    """Retired IDs cannot silently acquire a different object in the same document."""
    meta = after.get('identity')
    if meta is None:
        return
    retired = set(meta['retired'])
    current = before.get('identity')
    if current and current['figure'] == meta['figure']:
        retired.update(current['retired'])
        retired.update(object_ids(before)-object_ids(after))
    if retired & object_ids(after):
        raise ValueError('retired object IDs cannot be reused; assign a new ID')
    meta['retired'] = sorted(retired)


def prune_tick_modes(before, after):
    old,new=before.get('identity'),after.get('identity')
    if not old or not new or old['figure']!=new['figure']:return
    def owners(meta):return {v for p in meta['panels'] for v in [p['id'],*p['overlays']]}
    for removed in owners(old)-owners(new):
        if isinstance(new.get('tick_modes'),dict):new['tick_modes'].pop(removed,None)


def validate_features(state):
    """Host-independent guards for combinations the renderer cannot represent."""
    config = state['config']
    series = {s['series_id']: s for s in state['series']}
    if len(series) != len(state['series']):
        raise ValueError('duplicate series ID')
    bounded = [k for k in ('radial', 'categorical', 'boxplot', 'radar') if state.get(k) is not None]
    if bounded and (config.get('subplots') or config.get('overlays') or config.get('polar') or series):
        raise ValueError('bounded chart families require a separate single-panel document')
    owners = {}
    if config.get('polar') is not None and any(not set(spec['render_type']) <= {'Line', 'Scatter', 'ScatterLine'} for spec in series.values()):
        raise ValueError('renderer 0.18 requires a Cartesian root panel when other subplots use fields, vectors, histograms or errors')
    for index, panel in enumerate([None, *config.get('subplots', [])]):
        cfg = config if panel is None else panel['config']
        selected = set(series) - {sid for p in config.get('subplots', []) for sid in p.get('series', [])} if panel is None else set(panel.get('series', []))
        if panel is not None and (cfg.get('subplots') or cfg.get('annotations')):
            raise ValueError('nested subplots and subplot-local annotations are unsupported')
        overlay_owners = {}
        for o, overlay in enumerate(cfg.get('overlays', [])):
            for sid in overlay.get('series', []):
                if sid in overlay_owners or (sid in series and sid not in selected):
                    raise ValueError('series must belong to exactly one coordinate layer')
                overlay_owners[sid] = o
        if cfg.get('polar') is not None and cfg.get('overlays'):
            raise ValueError('polar does not support secondary Y axes')
        for sid in selected:
            if sid not in series:
                continue  # Renderer permits ownership references before upload.
            if sid in owners:
                raise ValueError('series cannot belong to more than one subplot')
            owners[sid] = index, overlay_owners.get(sid)
            if cfg.get('polar') is not None and not set(series[sid]['render_type']) <= {'Line', 'Scatter', 'ScatterLine'}:
                raise ValueError('polar supports line, scatter and scatter-line series only')
        items = cfg.get('annotations', {}).get('items', [])
        if len({identifier(item['id']) for item in items}) != len(items):
            raise ValueError('duplicate annotation ID')
    for sid, spec in series.items():
        style = next(iter(spec['render_type'].values()))
        fill = style.get('line', {}).get('fill', {})
        if isinstance(fill, dict) and 'ToSeries' in fill:
            target = series.get(fill['ToSeries'])
            if target is None or target['x_column'] != spec['x_column'] or owners.get(sid) != owners.get(target['series_id']):
                raise ValueError('series-reference fills need a valid line in the same layer and shared X column')


def grid_slots(grid):
    if not isinstance(grid, (list, tuple)) or not grid or not grid[0]:
        raise ValueError('grid must be a nonempty rectangular sequence')
    width = len(grid[0])
    if any(len(row) != width for row in grid):
        raise ValueError('grid rows must have equal lengths')
    slots = {}
    for r, row in enumerate(grid):
        for c, slot in enumerate(row):
            if slot is not None:
                identifier(slot)
                slots.setdefault(slot, []).append((r, c))
    for slot, cells in list(slots.items()):
        r0, c0 = map(min, zip(*cells))
        r1, c1 = map(max, zip(*cells))
        if len(cells) != (r1-r0+1)*(c1-c0+1):
            raise ValueError(f'grid slot {slot!r} must be rectangular')
        slots[slot] = (r0, c0, r1+1, c1+1)
    if not slots:
        raise ValueError('grid requires at least one occupied slot')
    if any(all(cell is None for cell in row) for row in (grid[0], grid[-1])) or any(
        all(row[c] is None for row in grid) for c in (0, width-1)):
        raise ValueError('renderer document bounds do not support completely empty outer grid rows or columns')
    return slots


def place_grid(state):
    layout = state['identity']['layout']
    if layout is None:
        return
    slots = grid_slots(layout['grid'])
    width, height = layout['size']
    gap = float(layout['gap'])
    def positions(weights, size):
        available = size-gap*(len(weights)-1)
        if available <= 0:
            raise ValueError('grid gaps exceed the document size')
        edges = [0.]
        for weight in weights:
            edges.append(edges[-1]+available*weight/sum(weights)+gap)
        return edges
    xs = positions(layout['column_weights'], width)
    ys = positions(layout['row_weights'], height)
    for slot, panel in layout['placement'].items():
        r0, c0, r1, c1 = slots[slot]
        rect = dict(x=round(xs[c0]), y=round(ys[r0]),
                    width=round(xs[c1]-gap)-round(xs[c0]),
                    height=round(ys[r1]-gap)-round(ys[r0]))
        if min(rect['width'], rect['height']) < 100:
            raise ValueError('grid panels must be at least 100 logical pixels per dimension')
        panel_config(state, panel)['chart_area'] = rect


class Subplot:
    """One stable panel, with locally owned coordinate axes."""
    def __init__(self, figure, id):
        self.figure, self.id = figure, id

    @property
    def axes(self):
        return self.figure._axes_for(self.id)

    def __getattr__(self, key):
        return getattr(self.axes, key)

    def set_rect(self, x, y, width, height):
        state = self.figure.get_settings()
        panel_config(state, self.id)['chart_area'] = dict(x=x, y=y, width=width, height=height)
        state['identity']['layout'] = None
        self.figure.apply_settings(state)
        return self


class Subplots(Mapping):
    def __init__(self, figure):
        self.figure = figure

    def __iter__(self):
        return iter(p['id'] for p in self.figure.get_settings()['identity']['panels'])

    def __len__(self):
        return len(self.figure.get_settings()['identity']['panels'])

    def __getitem__(self, key):
        state = self.figure.get_settings()
        panel_index(state, key)
        return Subplot(self.figure, key)

    @property
    def placement(self):
        layout = self.figure.get_settings()['identity']['layout']
        return {} if layout is None else copy.deepcopy(layout['placement'])

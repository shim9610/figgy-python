"""Public API combinations preserve explicit edits and consistent document geometry."""
import copy
import threading
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pytest
import figgyplot as fg


def chart(fig,kind):
    return fig.get_settings()[kind]


@pytest.mark.parametrize('backend',['native','webgpu'])
@pytest.mark.parametrize('family',['categorical','boxplot','radar','radial'])
def test_partial_nested_style_override_changes_only_requested_leaves(backend,family):
    token=fg.styles.preset('dashboard.operations')
    token.appearance['bounded']['radial']['style']={'outline':{'color':'#e6edf5','width':2}}
    def build(fig,override):
        a=fig.axes[0]
        if family=='categorical':a.bar(['A','B'],[1,2],**({'style':{'corner_radius':0}} if override else {}))
        elif family=='boxplot':a.boxplot([1,2,3,5],**({'style':{'median_width':3}} if override else {}))
        elif family=='radar':a.radar(['A','B','C'],[1,2,3],**({'style':{'line_width_px':3}} if override else {}))
        else:a.pie([1,2],**({'outline':{'width':3}} if override else {}))
    with fg.Figure(backend=backend,style=token) as baseline,fg.Figure(backend=backend,style=token) as changed:
        build(baseline,False);build(changed,True)
        expected=copy.deepcopy(chart(baseline,family))
        key={'categorical':'corner_radius','boxplot':'median_width','radar':'line_width_px'}.get(family)
        if family=='radial':expected['style']['outline']['width']=3
        else:expected['style'][key]=0 if family=='categorical' else 3
        assert chart(changed,family)==expected


def add_mapped(ax,method,explicit=False):
    kw={'cmap':'magma'} if explicit else {}
    if method=='imshow':ax.imshow([[1,2],[3,4]],**kw)
    elif method=='contour':ax.contour(np.arange(9).reshape(3,3)+1,**kw)
    elif method=='contourf':ax.contourf(np.arange(9).reshape(3,3)+1,**kw)
    elif method=='scatter':ax.scatter([0,1],[2,3],c=[2,7],**kw)
    else:ax.quiver([0,1],[2,3],[.2,.3],[.3,.2],values=[2,7],**kw)


def appearance(bar):
    bar=copy.deepcopy(bar)
    for key in ('min','max','major_spacing'):bar['axis'].pop(key)
    bar.pop('colormap')
    return bar


@pytest.mark.parametrize('backend',['native','webgpu'])
@pytest.mark.parametrize('style',[None,'dashboard.operations'])
@pytest.mark.parametrize('method',['imshow','contour','contourf','scatter','quiver'])
def test_new_mapped_layer_preserves_existing_colorbar_edits(backend,style,method):
    with fg.Figure(backend=backend,style=style,grid=[['left','right']]) as fig:
        fig.subplots['left'].plot([0,1],[1,2],id='left-line')
        ax=fig.subplots['right'].axes
        ax.scatter([0,1],[1,2],c=[0,1],id='right-points')
        state=fig.get_settings();bar=state['config']['subplots'][0]['config']['colorbar']
        bar['axis']['label_style']['font_size']=31;bar['gap_px']=37;bar['thickness_px']=29
        fig.apply_settings(state);before=fig.get_settings();old=before['config']['subplots'][0]['config']['colorbar']
        add_mapped(ax,method,explicit=True)
        after=fig.get_settings();new=after['config']['subplots'][0]['config']['colorbar']
        assert appearance(new)==appearance(old)
        assert new['colormap']=='Magma'
        assert after['series'][:2]==before['series']
        # The other panel keeps its complete accepted appearance and domain.
        for key in ('bottom_x','top_x','left_y','right_y','chart_title','grid','legend'):
            assert after['config'][key]==before['config'][key]


def grid_rects(fig):
    state=fig.get_settings()
    return state['identity']['layout'],[state['config']['chart_area']]+[p['config']['chart_area'] for p in state['config'].get('subplots',[])]


def assert_two_columns(fig,gap,weights):
    layout,rects=grid_rects(fig);width,height=layout['size']
    first=(width-gap)*weights[0]/sum(weights);second_x=round(first+gap)
    assert layout['gap']==pytest.approx(gap)
    assert layout['column_weights']==weights
    assert rects==[{'x':0,'y':0,'width':round(first),'height':height},
                   {'x':second_x,'y':0,'width':width-second_x,'height':height}]


@pytest.mark.parametrize('backend',['native','webgpu'])
@pytest.mark.parametrize('dpi',[120,144])
def test_inherited_grid_defaults_and_explicit_layout_match_accepted_geometry(backend,dpi):
    with fg.Figure(backend=backend,dpi=120) as source:
        source.set_layout([['left','right']],gap=44,column_weights=[2,1]);token=source.extract_style()
    with fg.Figure(backend=backend,dpi=dpi,style=token,grid=[['left','right']]) as fig:
        assert_two_columns(fig,44*dpi/120,[2,1])
        fig.set_layout([['left','right']],gap=22,column_weights=[1,2])
        assert_two_columns(fig,22,[1,2])
        # Omitted options retain the accepted manual layout, not old defaults.
        fig.set_layout([['left','right']])
        assert_two_columns(fig,22,[1,2])
        fig.place('left',slot='right')
        layout,rects=grid_rects(fig)
        assert rects[0]['x']>rects[1]['x'] and layout['gap']==22


def test_disabling_style_while_a_constructor_waits_is_one_serialized_operation():
    with fg.Figure(backend='webgpu',style='dashboard.operations') as fig:
        waiting=threading.Event();original=fig._lock
        class ObservedLock:
            def __enter__(self):
                if threading.current_thread() is not threading.main_thread():waiting.set()
                original.acquire()
                return self
            def __exit__(self,*args):original.release()
        fig._lock=ObservedLock()
        with ThreadPoolExecutor(1) as pool:
            with original:
                future=pool.submit(fig.axes[0].plot,[0,1],[1,2],color='black')
                assert waiting.wait(5)
                fig.set_style(None)
            future.result(timeout=10)
        assert fig.style_defaults is None
        spec=fig.get_settings()['series'][0]['render_type']['Line']['line']
        assert spec['line_color']=={'r':0.,'g':0.,'b':0.,'a':1.}

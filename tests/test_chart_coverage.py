"""Public constructors cover the renderer families and preserve SSOT/replay data."""
import copy
import numpy as np
import pytest
import figgyplot as figgy


CASES = [
    ('bar', (['A', 'B'], [[2, -1], [3, 4]]), {}, 'categorical'),
    ('barh', (['A', 'B'], [2, 4]), {}, 'categorical'),
    ('boxplot', ([[1, 2, 3], [2, 4, 6, 50]],), {}, 'boxplot'),
    ('bxp', ([dict(q1=1, med=2, q3=3, whislo=0, whishi=4)],), {}, 'boxplot'),
    ('errorbar', ([1, 2, 3], [2, 4, 3]), dict(yerr=[[.1, .2, .3], [.2, .1, .2]], xerr=.1), 'LineScatterErrorbarXY'),
    ('hist', ([1, 2, 2, 3, 4],), dict(bins=[0, 2, 4, 6]), 'Histogram'),
    ('stairs', ([1, 3], [0, 1, 3]), dict(orientation='horizontal'), 'Histogram'),
    ('contour', (np.array([[0., 1.], [2., 3.]]),), dict(levels=[.5, 1.5, 2.5]), 'Contour'),
    ('contourf', (np.array([[0., 1.], [2., 3.]]),), dict(levels=[.5, 1.5, 2.5]), 'HeatmapContour'),
]


@pytest.mark.parametrize('family,method,args', [
    ('radial', 'donut', ([1, 2, 3],)),
    ('categorical', 'bar', (['A', 'B'], [2, 4])),
    ('boxplot', 'boxplot', ([[1, 2, 3], [2, 4, 6]],)),
])
def test_native_bounded_preparation_reports_the_actual_chart_family(family, method, args):
    with figgy.figure(backend='native') as figure:
        getattr(figure.axes[0], method)(*args)
        before, revision = figure.get_settings(), figure.revision
        report = figure.prepare()
        assert report['ready'] and report['backend'] == 'native'
        assert report['stages'] == [{'scope': family, 'stage': 'first-frame', 'phase': 'Ready'}]
        assert figure.info['preparation'] == report
        assert figure.get_settings() == before and figure.revision == revision


@pytest.mark.parametrize('method,args,kwargs,kind', CASES, ids=[c[0] for c in CASES])
def test_all_constructors_share_native_browser_model_and_render(method, args, kwargs, kind):
    with figgy.figure(backend='native', id='parity') as native, figgy.figure(backend='webgpu', id='parity') as browser:
        for fig in (native, browser):
            getattr(fig.axes[0], method)(*args, **kwargs)
            fig.axes[0].set_title('Shared chart')
        ns, bs = native.get_settings(), browser.get_settings()
        def compare(a,b):
            if isinstance(a,dict):
                assert a.keys()==b.keys()
                for k in a: compare(a[k],b[k])
            elif isinstance(a,list):
                assert len(a)==len(b)
                for x,y in zip(a,b): compare(x,y)
            elif isinstance(a,float): assert a == pytest.approx(b, rel=1e-6, abs=1e-6)
            else: assert a==b
        compare(ns,bs)
        if kind in ('categorical', 'boxplot'):
            assert ns[kind]['title'] == 'Shared chart'
            for fig in (native, browser):
                fig.configure_bounded(style={'outline': True})
            assert native.get_settings() == browser.get_settings()
        else:
            assert kind in ns['series'][0]['render_type']
        pixels = np.asarray(native.render_rgba())
        assert pixels.shape == (600, 960, 4)
        assert np.count_nonzero(np.any(pixels[:, :, :3] < 220, axis=2)) > 500
        assert native.info['column_uploads'] == (0 if kind in ('categorical', 'boxplot') else browser.info['columns'])

@pytest.mark.parametrize('kind', ['categorical', 'boxplot'])
def test_bounded_replay_preserves_data_and_rejects_other_category_layout(kind):
    with figgy.figure(backend='native') as a, figgy.figure(backend='webgpu') as b:
        for fig, offset in [(a, 0), (b, 10)]:
            if kind == 'categorical': fig.axes[0].bar(['A', 'B'], [1+offset, 2+offset])
            else: fig.axes[0].boxplot([[1+offset, 2+offset], [3+offset, 4+offset]])
        original = copy.deepcopy(b.get_settings()[kind]['series'][0]['values'])
        a.configure_bounded(style={'outline': True})
        exec(a.to_code(), {'fig': b})
        assert b.get_settings()[kind]['series'][0]['values'] == original
        before, revision = b.get_settings(), b.revision
        bad = copy.deepcopy(before)
        bad[kind]['series'][0]['values'] = []
        with pytest.raises(ValueError): b.apply_settings(bad)
        assert b.get_settings() == before and b.revision == revision

@pytest.mark.parametrize('backend', ['native', 'webgpu'])
def test_radial_decorations_and_data_edits_remain_ssot(backend):
    with figgy.figure(backend=backend) as fig:
        fig.axes[0].donut([4, 3, 2], labels=['A', 'B', 'C'])
        fig.axes[0].set_title('Move me')
        if backend == 'native':
            fig.select_object('chart_title')
            before = fig.selection_bounds()['rect']
            assert fig.drag('chart_title', 12, 5)
            after = fig.selection_bounds()['rect']
            assert after[:2] == pytest.approx([before[0]+12, before[1]+5])
        before = fig.get_settings()
        fig.configure_radial(style={'hover_lift': .12})
        assert fig.get_settings()['radial']['slices'] == before['radial']['slices']

@pytest.mark.parametrize('backend', ['native', 'webgpu'])
def test_horizontal_bounded_axis_titles_follow_orientation(backend):
    with figgy.figure(backend=backend) as fig:
        ax=fig.axes[0]
        ax.barh(['A','B'],[2,3]);ax.set_xlabel('Value');ax.set_ylabel('Category')
        chart=fig.get_settings()['categorical']
        assert chart['value_title']=='Value' and chart['category_title']=='Category'


@pytest.mark.parametrize('backend', ['native', 'webgpu'])
@pytest.mark.parametrize('interpolation', ['nearest', 'bilinear'])
def test_heatmap_fit_padding_and_mixed_series(backend, interpolation):
    with figgy.figure(backend=backend) as fig:
        ax=fig.axes[0]
        ax.imshow(np.arange(24,dtype=float).reshape(4,6),extent=(-3,3,-2,2),origin='lower',interpolation=interpolation)
        expected=(-3,3,-2,2) if interpolation=='nearest' else (-2.5,2.5,-1.5,1.5)
        def limits():
            c=fig.get_settings()['config'];return tuple(c[k][b] for k in ['bottom_x','left_y'] for b in ['min','max'])
        fig.fit();assert limits()==pytest.approx(expected)
        fig.fit(padding=.1)
        x0,x1,y0,y1=expected
        assert limits()==pytest.approx((x0-(x1-x0)*.1,x1+(x1-x0)*.1,y0-(y1-y0)*.1,y1+(y1-y0)*.1))
        state=fig.get_settings()
        state['series'][0]['render_type']['Heatmap']['fill']['shading']='Flat'
        fig.apply_settings(state);fig.fit()
        assert limits()==pytest.approx((-3,3,-2,2))
        state=fig.get_settings()
        state['series'][0]['render_type']['Heatmap']['fill']['shading']='Interpolated'
        fig.apply_settings(state);fig.fit()
        assert limits()==pytest.approx((-2.5,2.5,-1.5,1.5))
        ax.plot([-5,5],[-4,4]);fig.fit()
        assert limits()==pytest.approx((-5.5,5.5,-4.4,4.4))


@pytest.mark.parametrize('backend', ['native', 'webgpu'])
@pytest.mark.parametrize('family', ['contour', 'contourf', 'matrix_overlay'])
def test_contour_fit_defaults_and_mixed_series(backend, family):
    with figgy.figure(backend=backend) as fig:
        ax=fig.axes[0]
        x=np.array([-3., -2.5, 0., 3.])
        y=np.array([-2., -.5, 2.])
        z=np.arange(12,dtype=float).reshape(3,4)
        getattr(ax, 'contourf' if family=='matrix_overlay' else family)(x,y,z)
        if family=='matrix_overlay':
            ax.contour(x,y,z)
            ax.imshow(z,extent=(-3,3,-2,2),origin='lower')
        colorbar=fig.get_settings()['config']['colorbar']
        def limits():
            c=fig.get_settings()['config'];return tuple(c[k][b] for k in ['bottom_x','left_y'] for b in ['min','max'])
        fig.fit();assert limits()==pytest.approx((-3,3,-2,2))
        fig.fit(padding=.1);assert limits()==pytest.approx((-3.6,3.6,-2.4,2.4))
        if backend=='webgpu':
            widget=fig.widget()
            widget._command(widget, {'action':'ready','info':{'column_uploads':fig.info['columns']}}, [])
            assert widget.columns == [] and fig._native.columns == {}
        fig.fit();assert limits()==pytest.approx((-3,3,-2,2))
        assert fig.get_settings()['config']['colorbar']==colorbar
    with figgy.figure(backend=backend) as fig:
        ax=fig.axes[0]
        getattr(ax, 'contourf' if family=='matrix_overlay' else family)(x,y,z)
        if family=='matrix_overlay':ax.imshow(z,extent=(-3,3,-2,2),origin='lower')
        ax.plot([-5,5],[-4,4]);fig.fit()
        c=fig.get_settings()['config']
        assert tuple(c[k][b] for k in ['bottom_x','left_y'] for b in ['min','max'])==pytest.approx((-5.5,5.5,-4.4,4.4))


@pytest.mark.parametrize('backend', ['native', 'webgpu'])
@pytest.mark.parametrize('family', ['Heatmap', 'Contour', 'HeatmapContour'])
def test_matrix_fit_uses_rendered_grid_after_ssot_style_change(backend, family):
    with figgy.figure(backend=backend) as fig:
        ax=fig.axes[0]
        ax.imshow(np.arange(12,dtype=float).reshape(3,4),extent=(-3,5,-2,4),origin='lower')
        state=fig.get_settings()
        field=state['series'][0]['render_type']['Heatmap']
        contour={'levels':[3.,6.,9.], 'line':{'line_style':'Solid','line_color':{'r':0.,'g':0.,'b':0.,'a':1.},'line_width':1.}}
        style={'matrix':field['matrix']}
        if family!='Contour':style['fill']=field['fill']
        if family!='Heatmap':style['contour']=contour
        state['series'][0]['render_type']={family:style}
        if family!='Contour':style['fill']['shading']='Interpolated'
        fig.apply_settings(state)
        if backend=='webgpu':
            widget=fig.widget()
            widget._command(widget, {'action':'ready','info':{'column_uploads':fig.info['columns']}}, [])
        def limits():
            c=fig.get_settings()['config'];return tuple(c[k][b] for k in ['bottom_x','left_y'] for b in ['min','max'])
        fig.fit();assert limits()==pytest.approx((-2,4,-1,3))
        if family!='Contour':
            state=fig.get_settings()
            state['series'][0]['render_type'][family]['fill']['shading']='Flat'
            fig.apply_settings(state);fig.fit()
            assert limits()==pytest.approx((-3,5,-2,4))
    if family=='Contour':return
    # Center samples with flat shading cover extrapolated half-cells, unlike
    # interpolated contourf. No source arrays are needed after browser upload.
    with figgy.figure(backend=backend) as fig:
        fig.axes[0].contourf([-3,-1,5],[-2,0,4],np.arange(9,dtype=float).reshape(3,3))
        state=fig.get_settings()
        field=state['series'][0]['render_type']['HeatmapContour']
        field['fill']['shading']='Flat'
        if family=='Heatmap':
            field.pop('contour');state['series'][0]['render_type']={'Heatmap':field}
        fig.apply_settings(state)
        if backend=='webgpu':
            widget=fig.widget()
            widget._command(widget, {'action':'ready','info':{'column_uploads':fig.info['columns']}}, [])
        fig.fit()
        c=fig.get_settings()['config']
        assert tuple(c[k][b] for k in ['bottom_x','left_y'] for b in ['min','max'])==pytest.approx((-4,8,-3,6))

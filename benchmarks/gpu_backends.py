"""GPU comparison adapters: actual draw followed by completed RGBA readback."""
import io
import time
import numpy as np
from PIL import Image


def timed(callback):
    start = time.perf_counter()
    result = callback()
    return time.perf_counter() - start, result


def png(draw):
    out = io.BytesIO()
    Image.fromarray(draw()).save(out, format='PNG')
    return out.getvalue()


def fastplotlib(args, x, y, row):
    import fastplotlib as fpl
    from rendercanvas.offscreen import RenderCanvas

    def initialize():
        canvas = RenderCanvas(size=(960, 600), pixel_ratio=1)
        fig = fpl.Figure(canvas=canvas, size=(960, 600), names=[None])
        ax = fig[0, 0]
        ax.background_color = ('white',)
        return fig, ax, canvas
    row['initialize_s'], (fig, ax, canvas) = timed(initialize)
    def register():
        points = np.column_stack((x, y))
        if args.kind == 'line':
            artist = ax.add_line(points, colors='#1f77b4', thickness=2.5)
        else:
            artist = ax.add_scatter(points, colors='#1f77b4', sizes=5, edge_width=0)
        ax.auto_scale(maintain_aspect=False)
        fig.show(autoscale=False)
        def render_frame():
            # The initial canvas resize can reset the layout. Apply the matched
            # data rectangle after resize events, immediately before rendering.
            if args.plot_area:
                ax.viewport.rect = tuple(args.plot_area)
            fig._render(draw=False)
        canvas.request_draw(render_frame)
        return artist
    row['register_and_fit_s'], artist = timed(register)
    row['adapter'] = dict(fig.renderer.device.adapter.info)
    row['renderer_pixel_scale'] = fig.renderer.pixel_scale
    row['postprocess_antialias'] = fig.renderer.ppaa
    if args.kind == 'line':
        row['line_material_antialias'] = artist.world_object.material.aa
    row['gpu_coordinate_dtype'] = 'float32 (fastplotlib conversion from supplied float64)'
    row['auto_downsample'] = False
    row['render_path'] = 'offscreen canvas force_draw + completed GPU readback'
    row['plot_area_px'] = list(ax.viewport.rect)
    def draw():
        # canvas.draw() forces the registered Figure render callback every call;
        # export_numpy() alone would only snapshot the previous frame.
        pixels = np.asarray(canvas.draw()).copy()
        row['plot_area_px'] = list(ax.viewport.rect)
        return pixels
    def view(i):
        ax.camera.width = 100
        ax.camera.local.x = 50 + i * .2
    def style(i):
        artist.colors = '#d62728' if i % 2 else '#1f77b4'
    return draw, view, style, lambda: png(draw), canvas.close


def vispy(args, x, y, row):
    from vispy import app, scene, gloo
    app.use_app('pyside6')
    def initialize():
        canvas = scene.SceneCanvas(size=(960, 600), bgcolor='white', show=False)
        left, top, width, height = args.plot_area or (70, 62, 860, 478)
        view = scene.widgets.ViewBox(parent=canvas.scene, pos=(left, top),
                                    size=(width, height), camera='panzoom', bgcolor='white')
        view.camera.aspect = None
        bottom = scene.AxisWidget(orientation='bottom', axis_color='black',
                                  tick_color='black', text_color='black', font_size=10)
        bottom.parent, bottom.pos, bottom.size = canvas.scene, (left, top + height), (width, 38)
        side = scene.AxisWidget(orientation='left', axis_color='black', tick_color='black',
                                text_color='black', font_size=10)
        side.parent, side.pos, side.size = canvas.scene, (0, top), (left, height)
        bottom.link_view(view)
        side.link_view(view)
        scene.visuals.GridLines(color=(.85, .85, .85, 1), parent=view.scene)
        return canvas, view
    row['initialize_s'], (canvas, ax) = timed(initialize)
    row['canvas_logical_size'] = list(canvas.size)
    row['canvas_physical_size'] = list(canvas.physical_size)
    row['canvas_pixel_scale'] = canvas.pixel_scale
    # A hidden Qt Wayland canvas can start at the monitor's native 2x scale.
    # VisPy's fixed-size FBO then clips the scene while still returning a
    # 960x600 array, so output shape alone does not validate the comparison.
    if canvas.pixel_scale != 1:
        canvas.close()
        raise RuntimeError(
            'VisPy benchmark requires canvas pixel_scale=1 for the matched '
            '960x600 viewport; adjust QT_SCALE_FACTOR for the display scale'
        )
    points = None
    antialias = args.worker == 'vispy-aa'
    def register():
        nonlocal points
        points = np.column_stack((x, y)).astype(np.float32)
        if args.kind == 'line':
            artist = scene.visuals.Line(pos=points, color='#1f77b4', width=2.5,
                                        method='gl', antialias=antialias, parent=ax.scene)
        else:
            artist = scene.visuals.Markers(parent=ax.scene)
            artist.set_data(pos=points, face_color='#1f77b4', size=5, edge_width=0)
        ax.camera.set_range(x=(float(x.min()), float(x.max())),
                            y=(float(y.min()), float(y.max())), margin=.05)
        return artist
    row['register_and_fit_s'], artist = timed(register)
    canvas.set_current()
    row['adapter'] = {k: str(gloo.gl.glGetParameter(v)) for k, v in
                      [('vendor', gloo.gl.GL_VENDOR), ('renderer', gloo.gl.GL_RENDERER),
                       ('version', gloo.gl.GL_VERSION)]}
    row['gpu_coordinate_dtype'] = 'float32 (timed conversion from supplied float64)'
    row['auto_downsample'] = False
    row['render_path'] = 'SceneCanvas.render: draw to framebuffer + RGBA readback'
    row['line_method'] = 'gl'
    row['antialias'] = antialias if args.kind == 'line' else artist.antialias
    row['plot_area_px'] = list(args.plot_area or (70, 62, 860, 478))
    def draw():
        return canvas.render(size=(960, 600), alpha=True)
    def view(i):
        rect = ax.camera.rect
        ax.camera.rect = (i * .2, rect.bottom, 100, rect.height)
    def style(i):
        if args.kind == 'line':
            artist.set_data(color='#d62728' if i % 2 else '#1f77b4')
        else:
            artist.set_data(pos=points, face_color='#d62728' if i % 2 else '#1f77b4', size=5, edge_width=0)
    return draw, view, style, lambda: png(draw), canvas.close


def pyqtgraph_opengl(args, x, y, row):
    import pyqtgraph as pg
    from OpenGL import GL
    from PySide6.QtWidgets import QFrame
    pg.setConfigOptions(useOpenGL=True, antialias=False)
    app = pg.mkQApp()
    def initialize():
        plot = pg.PlotWidget(background='w')
        plot.setFrameShape(QFrame.Shape.NoFrame)
        plot.resize(960, 600)
        if args.plot_area:
            left, top, width, height = args.plot_area
            item = plot.getPlotItem()
            item.layout.setContentsMargins(0, 0, 0, 0)
            item.layout.setSpacing(0)
            item.showAxis('top'); item.showAxis('right')
            item.getAxis('top').setStyle(showValues=False)
            item.getAxis('right').setStyle(showValues=False)
            item.getAxis('left').setWidth(left)
            item.getAxis('top').setHeight(top)
            item.getAxis('right').setWidth(960 - left - width)
            item.getAxis('bottom').setHeight(600 - top - height)
        plot.show()
        app.processEvents()
        viewport = plot.viewport()
        if not hasattr(viewport, 'grabFramebuffer') or not viewport.isValid():
            raise RuntimeError('pyqtgraph OpenGL viewport was not created')
        return plot, viewport
    row['initialize_s'], (plot, viewport) = timed(initialize)
    def register():
        artist = plot.plot(x, y, pen=pg.mkPen('#1f77b4', width=2.5),
                           autoDownsample=False, clipToView=False)
        plot.autoRange()
        return artist
    row['register_and_fit_s'], artist = timed(register)
    row.update(use_opengl=True, antialias=False, auto_downsample=False,
               render_path='QGraphicsView OpenGL paint + glReadPixels RGBA readback',
               gpu_coordinate_dtype='pyqtgraph centered float32 OpenGL VBO')
    viewport.makeCurrent()
    gl = viewport.context().functions()
    row['adapter'] = {k: str(gl.glGetString(v)) for k, v in
                      [('vendor', 0x1F00), ('renderer', 0x1F01), ('version', 0x1F02)]}
    viewport.doneCurrent()
    rect = plot.getViewBox().sceneBoundingRect()
    row['plot_area_px'] = [rect.x(), rect.y(), rect.width(), rect.height()]
    def draw():
        viewport.repaint()
        app.processEvents()
        if round(viewport.width() * viewport.devicePixelRatioF()) != 960 or round(viewport.height() * viewport.devicePixelRatioF()) != 600:
            raise RuntimeError('OpenGL physical framebuffer size differs from 960x600')
        if artist.curve.glstate is None:
            raise RuntimeError('PlotCurveItem did not execute its native OpenGL paintGL path')
        row['native_opengl_curve'] = True
        row['device_pixel_ratio'] = viewport.devicePixelRatioF()
        # grabFramebuffer() invokes QOpenGLWidget.paintGL(), which is empty in
        # this QGraphicsView viewport and clears its frame. Read the framebuffer
        # just painted by QGraphicsView directly instead.
        viewport.makeCurrent()
        try:
            GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, viewport.defaultFramebufferObject())
            pixels = GL.glReadPixels(0, 0, 960, 600, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE)
        finally:
            viewport.doneCurrent()
        return np.frombuffer(pixels, np.uint8).reshape(600, 960, 4)[::-1].copy()
    def view(i):
        plot.setXRange(i * .2, 100 + i * .2, padding=0)
    def style(i):
        artist.setPen(pg.mkPen('#d62728' if i % 2 else '#1f77b4', width=2.5))
    return draw, view, style, lambda: png(draw), plot.close


SETUPS = {'fastplotlib': fastplotlib, 'vispy': vispy, 'vispy-aa': vispy, 'pyqtgraph-opengl': pyqtgraph_opengl}

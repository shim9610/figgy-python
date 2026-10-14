//! winit + egui surface host. It shares the existing resident FigureCore.
use super::*;
use std::{
    cell::RefCell,
    sync::{
        Weak,
        atomic::{AtomicBool, Ordering},
    },
    time::{Duration, Instant},
};
use winit::{
    application::ApplicationHandler,
    dpi::{LogicalSize, PhysicalSize},
    event::{ElementState, MouseButton, MouseScrollDelta, WindowEvent},
    event_loop::{ActiveEventLoop, ControlFlow, EventLoop},
    keyboard::{Key, ModifiersState, NamedKey},
    platform::pump_events::EventLoopExtPumpEvents,
    window::{Window, WindowId},
};

#[derive(Default)]
struct Control {
    close: AtomicBool,
    dirty: AtomicBool,
    stats: Mutex<Value>,
    settings: Mutex<Option<Arc<Control>>>,
}
#[pyclass(module = "figgyplot._native")]
pub struct WindowHandle {
    control: Arc<Control>,
}
#[pymethods]
impl WindowHandle {
    fn close(&self) {
        self.control.close.store(true, Ordering::Release);
    }
    fn refresh(&self) {
        self.control.dirty.store(true, Ordering::Release);
    }
    fn info_json(&self) -> String {
        let mut stats = self.control.stats.lock().unwrap().clone();
        if let Some(settings) = self.control.settings.lock().unwrap().as_ref() {
            stats["settings_window"] = if settings.close.load(Ordering::Acquire) {
                Value::Null
            } else {
                settings.stats.lock().unwrap().clone()
            };
        }
        stats.to_string()
    }
    #[getter]
    fn closed(&self) -> bool {
        self.control.close.load(Ordering::Acquire)
    }
}

struct SurfaceWindow {
    window: Arc<Window>,
    surface: wgpu::Surface<'static>,
    config: wgpu::SurfaceConfiguration,
    core: Weak<Mutex<FigureCore>>,
    control: Arc<Control>,
    ctx: egui::Context,
    input: egui_winit::State,
    ui_renderer: egui_wgpu::Renderer,
    view: Option<renderer::ChartView>,
    styles: Vec<renderer::ChartStyle>,
    last_revision: u64,
    last_scale: f32,
    last_pool_generation: u32,
    selected: Option<String>,
    handle: Option<String>,
    dragging: bool,
    panning: bool,
    pan_moved: bool,
    drag_origin: (f32, f32),
    chart_pressed: bool,
    edit_area: bool,
    cursor: (f32, f32),
    panel: Rect,
    scale: f32,
    editor: editor::Editor,
    last_panel: Option<Rect>,
    frames: u64,
    last_input: Option<Instant>,
    latency_ms: f64,
    repaint_at: Option<Instant>,
    settings_only: bool,
    parent: Option<Weak<Control>>,
    inspector_docked: bool,
    resize_target: Option<u32>,
    pending_chart_width: Option<u32>,
    last_pick: Option<renderer::config::PickedDataRef>,
    modifiers: ModifiersState,
    radial_surface: Option<radial_host::RadialSurface>,
}
#[path = "radial_host.rs"]
mod radial_host;

impl SurfaceWindow {
    fn new(
        event_loop: &ActiveEventLoop,
        core: &Arc<Mutex<FigureCore>>,
        control: Arc<Control>,
        settings_only: bool,
        parent: Option<Weak<Control>>,
    ) -> PyResult<Self> {
        let mut data = core.lock().map_err(runtime)?;
        let gpu = Arc::clone(&data.gpu);
        let mut renderer = gpu::lock(&gpu)?;
        let c = FigureAccess::new(&gpu, &mut data, &mut renderer);
        let rect = c.data.chart.config().chart_area.0;
        let window = Arc::new(
            event_loop
                .create_window(
                    Window::default_attributes()
                        .with_title(if settings_only {
                            "Figgy — Advanced chart settings"
                        } else {
                            "Figgy"
                        })
                        .with_min_inner_size(if settings_only {
                            LogicalSize::new(500., 400.)
                        } else {
                            LogicalSize::new(900., 520.)
                        })
                        .with_inner_size(if settings_only {
                            LogicalSize::new(680., 680.)
                        } else {
                            LogicalSize::new(
                                (rect.width as f64 + 32.).max(900.),
                                (rect.height as f64 + 144.).max(700.),
                            )
                        }),
                )
                .map_err(runtime)?,
        );
        let size = window.inner_size();
        let surface = c
            .context
            .instance
            .create_surface(window.clone())
            .map_err(runtime)?;
        let caps = surface.get_capabilities(&c.context.adapter);
        let format = caps.formats.iter().copied().find(|f| !f.is_srgb()).or(caps.formats.first().copied()).ok_or_else(|| runtime("the Figure GPU cannot present to this window; create it on a compatible adapter"))?;
        let config = wgpu::SurfaceConfiguration {
            usage: wgpu::TextureUsages::RENDER_ATTACHMENT,
            format,
            width: size.width.max(1),
            height: size.height.max(1),
            present_mode: wgpu::PresentMode::Fifo,
            desired_maximum_frame_latency: 2,
            alpha_mode: caps.alpha_modes[0],
            view_formats: vec![],
            color_space: Default::default(),
        };
        surface.configure(c.renderer.device(), &config);
        let ctx = egui::Context::default();
        editor::theme(&ctx);
        let input = egui_winit::State::new(
            ctx.clone(),
            egui::ViewportId::ROOT,
            window.as_ref(),
            Some(window.scale_factor() as f32),
            window.theme(),
            None,
        );
        let ui_renderer = egui_wgpu::Renderer::new(c.renderer.device(), format, Default::default());
        let mut editor = editor::Editor::default();
        if settings_only {
            editor.begin_settings(&c);
        }
        Ok(Self {
            window,
            surface,
            config,
            core: Arc::downgrade(core),
            control,
            ctx,
            input,
            ui_renderer,
            view: None,
            styles: vec![],
            last_revision: u64::MAX,
            last_scale: 0.,
            last_pool_generation: 0,
            selected: None,
            handle: None,
            dragging: false,
            panning: false,
            pan_moved: false,
            drag_origin: (0., 0.),
            chart_pressed: false,
            edit_area: false,
            cursor: (0., 0.),
            panel: rect,
            scale: 1.,
            editor,
            last_panel: None,
            frames: 0,
            last_input: None,
            latency_ms: 0.,
            repaint_at: None,
            settings_only,
            parent,
            inspector_docked: false,
            resize_target: None,
            pending_chart_width: None,
            last_pick: None,
            modifiers: ModifiersState::empty(),
            radial_surface: None,
        })
    }
    fn resize(&mut self, w: u32, h: u32) {
        if w == 0 || h == 0 {
            return;
        }
        if self.resize_target == Some(w) {
            self.resize_target = None;
            self.pending_chart_width = None;
        }
        self.config.width = w;
        self.config.height = h;
        if let Some(core) = self.core.upgrade() {
            let mut data = core.lock().unwrap();
            let gpu = Arc::clone(&data.gpu);
            let Ok(mut renderer) = gpu::lock(&gpu) else {
                return;
            };
            let c = FigureAccess::new(&gpu, &mut data, &mut renderer);
            self.surface.configure(c.renderer.device(), &self.config);
        }
        self.last_scale = 0.;
        self.window.request_redraw();
    }
    fn display(&self, c: &FigureAccess<'_>) -> (Config, Rect, f32) {
        let stage = self.editor.stage;
        let dpr = self.ctx.pixels_per_point();
        let width = (stage.width() * dpr).round().max(1.) as u32;
        let height = (stage.height() * dpr).round().max(1.) as u32;
        let (mut display, mut panel, scale) =
            renderer::display_config_for_surface(c.data.chart.config(), (width, height));
        // Keep the document aspect ratio, including the fitted letterbox.
        panel.x += (stage.min.x * dpr).round().max(0.) as u32;
        panel.y += (stage.min.y * dpr).round().max(0.) as u32;
        display.chart_area = renderer::layout::ChartArea(panel);
        (display, panel, scale)
    }
    fn inspector_overlay(&self) -> bool {
        self.window.is_maximized()
            || self.window.fullscreen().is_some()
            || self.window.current_monitor().is_some_and(|m| {
                !self.inspector_docked && self.config.width + self.sidebar_pixels() > m.size().width
            })
    }
    fn sidebar_pixels(&self) -> u32 {
        (editor::INSPECTOR_WIDTH * self.ctx.pixels_per_point()).round() as u32
    }
    fn sync_inspector_size(&mut self) {
        if self.settings_only || self.inspector_overlay() {
            return;
        }
        if self.editor.inspector_open != self.inspector_docked {
            let sidebar = self.sidebar_pixels();
            let base = self.pending_chart_width.unwrap_or_else(|| {
                self.config
                    .width
                    .saturating_sub(if self.inspector_docked { sidebar } else { 0 })
            });
            let target = base
                + if self.editor.inspector_open {
                    sidebar
                } else {
                    0
                };
            self.pending_chart_width = Some(base);
            self.resize_target = Some(target);
            self.inspector_docked = self.editor.inspector_open;
            if let Some(size) = self
                .window
                .request_inner_size(PhysicalSize::new(target, self.config.height))
            {
                self.config.width = size.width;
                self.config.height = size.height;
                self.resize_target = None;
                self.pending_chart_width = None;
                self.last_scale = 0.;
            }
            self.window.request_redraw();
        }
    }
    fn keyboard(&mut self, key: &NamedKey) -> PyResult<()> {
        if *key == NamedKey::F11 {
            self.window
                .set_fullscreen(if self.window.fullscreen().is_some() {
                    None
                } else {
                    Some(winit::window::Fullscreen::Borderless(None))
                });
            self.window.request_redraw();
            return Ok(());
        }
        let Some(core) = self.core.upgrade() else {
            return Ok(());
        };
        let mut data = core.lock().map_err(runtime)?;
        let gpu = Arc::clone(&data.gpu);
        let mut renderer = gpu::lock(&gpu)?;
        let mut c = FigureAccess::new(&gpu, &mut data, &mut renderer);
        if c.data.radial.is_some() {
            if *key == NamedKey::Escape {
                c.clear_data_selection()?;
            } else if matches!(key, NamedKey::ArrowLeft | NamedKey::ArrowRight) {
                let mut chart = c.data.radial.as_ref().unwrap().chart.clone();
                let indices = chart
                    .slices
                    .iter()
                    .enumerate()
                    .filter(|(_, s)| s.value > 0.)
                    .map(|(i, _)| i)
                    .collect::<Vec<_>>();
                let n = indices.len() as i64;
                let index = chart
                    .interaction
                    .selected
                    .and_then(|t| indices.iter().position(|i| *i == t.index))
                    .unwrap_or(0) as i64;
                let delta = if *key == NamedKey::ArrowLeft { -1 } else { 1 };
                chart.interaction.selected = Some(renderer::radial::RadialTarget::main(
                    indices[(index + delta).rem_euclid(n) as usize],
                ));
                c.set_radial(&serde_json::to_string(&chart).map_err(runtime)?)?;
            }
            self.window.request_redraw();
            return Ok(());
        }
        if *key == NamedKey::Escape {
            self.selected = None;
            self.handle = None;
            self.dragging = false;
            self.panning = false;
            c.clear_data_selection()?;
        } else {
            let step = if self.modifiers.shift_key() { 10 } else { 1 };
            let (mut dx, mut dy) = match key {
                NamedKey::ArrowLeft => (-step, 0),
                NamedKey::ArrowRight => (step, 0),
                NamedKey::ArrowUp => (0, 1),
                NamedKey::ArrowDown => (0, -1),
                _ => return Ok(()),
            };
            if c.data.chart.config().picked_data.is_some() {
                if c.data
                    .chart
                    .config()
                    .picked_data
                    .as_ref()
                    .and_then(|p| p.refs.first())
                    .is_some_and(|p| {
                        matches!(p, renderer::config::PickedDataRef::MatrixCell { .. })
                    })
                {
                    if c.data.chart.config().bottom_x.inverted {
                        dx = -dx;
                    }
                    if c.data.chart.config().left_y.inverted {
                        dy = -dy;
                    }
                }
                c.step_selection(dx, dy)?;
                self.selected = c
                    .data
                    .chart
                    .config()
                    .picked_data
                    .as_ref()
                    .and_then(|p| p.refs.first())
                    .map(|p| p.series_id().to_owned());
            } else if let Some(target) = &self.selected {
                if c.element(target)
                    .ok()
                    .and_then(|id| c.data.hitmap.get(id))
                    .is_some_and(|e| e.as_draggable().is_some())
                {
                    // Screen up is negative y; data up is positive y.
                    c.drag(
                        target,
                        dx as f32 / self.scale,
                        -(dy * step) as f32 / self.scale,
                        None,
                    )?;
                }
            }
        }
        self.last_revision = u64::MAX;
        self.window.request_redraw();
        Ok(())
    }
    fn chart_contains_cursor(&self) -> bool {
        let p = self.panel;
        self.cursor.0 >= p.x as f32
            && self.cursor.0 < (p.x + p.width) as f32
            && self.cursor.1 >= p.y as f32
            && self.cursor.1 < (p.y + p.height) as f32
    }
    fn pointer(&mut self, event: &WindowEvent) -> PyResult<()> {
        let input_received = Instant::now();
        let Some(core) = self.core.upgrade() else {
            return Ok(());
        };
        let mut data = core.lock().map_err(runtime)?;
        let gpu = Arc::clone(&data.gpu);
        let mut renderer = gpu::lock(&gpu)?;
        let mut c = FigureAccess::new(&gpu, &mut data, &mut renderer);
        if c.data.radial.is_some() {
            self.window.request_redraw();
            return Ok(());
        }
        let (display, panel, scale) = self.display(&c);
        self.panel = panel;
        self.scale = scale;
        match event {
            WindowEvent::CursorMoved { position, .. } => {
                let old = self.cursor;
                self.cursor = (position.x as f32, position.y as f32);
                if self.panning {
                    let distance = (self.cursor.0 - self.drag_origin.0)
                        .hypot(self.cursor.1 - self.drag_origin.1);
                    if self.pan_moved || distance >= 3. {
                        if !self.pan_moved {
                            c.clear_data_selection()?;
                            self.selected = None;
                            self.pan_moved = true;
                        }
                        let bounds = c
                            .data
                            .hitmap
                            .selection_box(
                                c.element("data_area")?,
                                &display,
                                &CpuTextMeasure::for_style(&display.draw_style),
                            )
                            .unwrap()
                            .rect;
                        let mut cfg = c.data.chart.config().clone();
                        let dx = -(self.cursor.0 - old.0) as f64 / bounds.width.max(1.) as f64;
                        let dy = (self.cursor.1 - old.1) as f64 / bounds.height.max(1.) as f64;
                        for axis in [&mut cfg.bottom_x, &mut cfg.top_x] {
                            navigate_axis(axis, 1., 0.5, dx);
                        }
                        for axis in [&mut cfg.left_y, &mut cfg.right_y] {
                            navigate_axis(axis, 1., 0.5, dy);
                        }
                        c.commit_config(cfg)?;
                        self.last_input = Some(input_received);
                        self.window.request_redraw();
                    }
                } else if self.dragging
                    && let Some(target) = &self.selected
                {
                    c.drag(
                        target,
                        (self.cursor.0 - old.0) / scale,
                        (self.cursor.1 - old.1) / scale,
                        self.handle.as_deref(),
                    )?;
                    self.last_input = Some(input_received);
                    self.window.request_redraw();
                }
            }

            WindowEvent::MouseInput {
                state: ElementState::Pressed,
                button: MouseButton::Left,
                ..
            } => {
                self.chart_pressed = true;
                self.panning = false;
                self.pan_moved = false;
                self.drag_origin = self.cursor;
                let (x, y) = self.cursor;
                let measure = CpuTextMeasure::for_style(&display.draw_style);
                self.handle = self
                    .selected
                    .as_deref()
                    .and_then(|t| c.element(t).ok())
                    .and_then(|id| c.data.hitmap.get(id))
                    .and_then(|e| e.as_resizable())
                    .and_then(|e| e.hit_resize_handle(&display, &measure, x, y))
                    .map(|h| format!("{h:?}"));
                if self.handle.is_none() {
                    self.selected = c
                        .data
                        .hitmap
                        .hit_test(&display, &measure, x, y)
                        .and_then(|id| c.data.hitmap.get(id))
                        .map(|e| e.element_id());
                    if self.selected.as_deref() == Some("data_area") && !self.edit_area {
                        self.panning = true;
                        c.renderer.enable_gpu_picking().map_err(runtime)?;
                        let id = c.data.chart_id;
                        let ticket = c
                            .renderer
                            .pick_chart_data(
                                id,
                                GpuPickRequest {
                                    canvas_position_px: [x, y],
                                    display_panel_px: panel,
                                    display_scale: scale,
                                    max_distance_px: 6.,
                                },
                            )
                            .map_err(runtime)?;
                        c.renderer.wait_idle();
                        let picked = pollster::block_on(ticket.resolve()).map_err(runtime)?;
                        let picked = picked.map(|p| {
                            let mut reference = p.to_ref();
                            gpu::local_selection(c.data.figure_id, &mut reference);
                            reference
                        });
                        self.selected = picked.as_ref().map(|p| p.series_id().to_string());
                        let mut cfg = c.data.chart.config().clone();
                        let same = picked.as_ref().is_some_and(|p| {
                            cfg.picked_data
                                .as_ref()
                                .is_some_and(|s| s.refs.first() == Some(p))
                        });
                        cfg.picked_data = if same {
                            None
                        } else {
                            picked.map(|p| renderer::config::DataSelectionsConfig {
                                refs: vec![p],
                                ..Default::default()
                            })
                        };
                        cfg.picked_points = None;
                        if same {
                            self.selected = None;
                        }
                        c.commit_config(cfg)?;
                    } else {
                        c.clear_data_selection()?;
                    }
                }
                self.dragging = self.panning
                    || self
                        .selected
                        .as_deref()
                        .and_then(|t| c.element(t).ok())
                        .and_then(|id| c.data.hitmap.get(id))
                        .is_some_and(|e| e.as_draggable().is_some());
                self.last_revision = u64::MAX;
                self.last_input = Some(input_received);
                self.window.request_redraw();
            }
            WindowEvent::MouseInput {
                state: ElementState::Released,
                button: MouseButton::Left,
                ..
            } => {
                let chart_pressed = std::mem::take(&mut self.chart_pressed);
                self.dragging = false;
                self.panning = false;
                self.handle = None;
                if !self.pan_moved
                    && chart_pressed
                    && self.selected.is_some()
                    && self.chart_contains_cursor()
                {
                    self.editor.inspector_open = true;
                    self.window.request_redraw();
                }
            }
            WindowEvent::MouseWheel { delta, .. } => {
                let (dx, dy) = match delta {
                    MouseScrollDelta::LineDelta(x, y) => (*x as f64, *y as f64),
                    MouseScrollDelta::PixelDelta(p) => (p.x / 40., p.y / 40.),
                };
                let bounds = c
                    .data
                    .hitmap
                    .selection_box(
                        c.element("data_area")?,
                        &display,
                        &CpuTextMeasure::for_style(&display.draw_style),
                    )
                    .unwrap()
                    .rect;
                let x = ((self.cursor.0 - bounds.x) / bounds.width.max(1.)).clamp(0., 1.) as f64;
                let y =
                    1. - ((self.cursor.1 - bounds.y) / bounds.height.max(1.)).clamp(0., 1.) as f64;
                let mut cfg = c.data.chart.config().clone();
                let delta = if dy != 0. { dy } else { dx };
                let factor = (-delta.clamp(-12., 12.) * 0.1).exp();
                let ctrl = self.modifiers.control_key();
                let shift = self.modifiers.shift_key();
                // Ctrl isolates X, Shift isolates Y; plain wheel zooms both.
                if !shift || ctrl {
                    for axis in [&mut cfg.bottom_x, &mut cfg.top_x] {
                        navigate_axis(axis, factor, x, 0.);
                    }
                }
                if !ctrl || shift {
                    for axis in [&mut cfg.left_y, &mut cfg.right_y] {
                        navigate_axis(axis, factor, y, 0.);
                    }
                }
                c.commit_config(cfg)?;
                self.last_input = Some(input_received);
                self.window.request_redraw();
            }
            _ => {}
        }
        Ok(())
    }
    fn frame(&mut self) -> PyResult<()> {
        let Some(core) = self.core.upgrade() else {
            self.control.close.store(true, Ordering::Release);
            return Ok(());
        };
        let mut data = core.lock().map_err(runtime)?;
        let gpu = Arc::clone(&data.gpu);
        let mut renderer = gpu::lock(&gpu)?;
        let mut c = FigureAccess::new(&gpu, &mut data, &mut renderer);
        if c.data.radial.is_some() && !self.settings_only {
            return self.frame_radial(&mut c);
        }
        c.renderer
            .ensure_target_format(self.config.format)
            .map_err(runtime)?;
        let input = self.input.take_egui_input(&self.window);
        let ctx = self.ctx.clone();
        let current_pick = c
            .data
            .chart
            .config()
            .picked_data
            .as_ref()
            .and_then(|p| p.refs.first())
            .cloned();
        if current_pick != self.last_pick {
            self.editor.picked = match current_pick
                .as_ref()
                .map(|p| c.selection_details(p))
                .transpose()
            {
                Ok(value) => value,
                Err(error) => {
                    self.editor.error = error.to_string();
                    None
                }
            };
            self.last_pick = current_pick;
        }
        let previous_selection = self.selected.clone();
        let output = ctx.run_ui(input, |root| {
            if self.settings_only {
                self.editor.show_settings(root, &mut c);
            } else {
                self.editor
                    .show(root, &mut c, &mut self.selected, &mut self.edit_area);
            }
        });
        // Explicit export may temporarily select its RGBA target pipelines.
        c.renderer
            .ensure_target_format(self.config.format)
            .map_err(runtime)?;
        if previous_selection != self.selected {
            if c.data
                .chart
                .config()
                .picked_data
                .as_ref()
                .and_then(|p| p.refs.first())
                .is_some_and(|p| Some(p.series_id()) != self.selected.as_deref())
            {
                c.clear_data_selection()?;
            }
            self.last_revision = u64::MAX;
            self.window.request_redraw();
        }
        self.input
            .handle_platform_output(&self.window, output.platform_output);
        let previous_size = (self.config.width, self.config.height);
        self.sync_inspector_size();
        if previous_size != (self.config.width, self.config.height) {
            self.surface.configure(c.renderer.device(), &self.config);
        }
        if !self.settings_only && !self.inspector_overlay() {
            let available = self.pending_chart_width.unwrap_or_else(|| {
                self.config.width.saturating_sub(if self.inspector_docked {
                    self.sidebar_pixels()
                } else {
                    0
                })
            });
            self.editor.stage.max.x =
                self.editor.stage.min.x + (available as f32 / ctx.pixels_per_point() - 32.).max(1.);
        }
        let (display, panel, scale) = if self.settings_only {
            (
                c.data.chart.config().clone(),
                c.data.chart.config().chart_area.0,
                1.,
            )
        } else {
            self.display(&c)
        };
        self.panel = panel;
        self.scale = scale;
        if !self.settings_only && self.view.is_none() {
            self.view = Some(
                c.renderer
                    .create_chart_view(&Chart::new(display.clone()), panel)
                    .map_err(runtime)?,
            );
        }
        if !self.settings_only
            && (c.data.revision != self.last_revision
                || scale != self.last_scale
                || self.last_pool_generation != c.renderer.pool().generation()
                || self.last_panel != Some(panel))
        {
            let boxes = self
                .selected
                .as_deref()
                .and_then(|t| c.element(t).ok())
                .and_then(|id| {
                    c.data.hitmap.selection_box(
                        id,
                        &display,
                        &CpuTextMeasure::for_style(&display.draw_style),
                    )
                })
                .into_iter()
                .collect::<Vec<_>>();
            c.renderer
                .refresh_axis_with_selection(
                    self.view.as_mut().unwrap(),
                    &Chart::new(display.clone()),
                    panel,
                    &boxes,
                )
                .map_err(runtime)?;
            let specs = c.gpu_series(&c.data.series);
            self.styles = specs
                .iter()
                .zip(&c.data.series)
                .map(|(s, local)| {
                    let mut style_spec = s.clone();
                    style_spec.series_id = local.series_id.clone();
                    c.renderer
                        .create_style_for_series_scaled(&style_spec, scale)
                        .map_err(runtime)
                })
                .collect::<PyResult<Vec<_>>>()?;
            self.last_revision = c.data.revision;
            self.last_scale = scale;
            self.last_pool_generation = c.renderer.pool().generation();
            self.last_panel = Some(panel);
        }
        let specs = c.gpu_series(&c.data.series);
        let series = specs
            .iter()
            .zip(&self.styles)
            .map(|(config, style)| renderer::Series { config, style })
            .collect::<Vec<_>>();
        let prepared = if self.settings_only {
            None
        } else {
            Some(
                c.renderer
                    .prepare(&[renderer::ChartDrawItem {
                        view: self.view.as_ref().unwrap(),
                        chart_config: &gpu::config(c.data.figure_id, &display),
                        series: &series,
                    }])
                    .map_err(runtime)?,
            )
        };
        let frame = match self.surface.get_current_texture() {
            wgpu::CurrentSurfaceTexture::Success(f)
            | wgpu::CurrentSurfaceTexture::Suboptimal(f) => f,
            wgpu::CurrentSurfaceTexture::Outdated | wgpu::CurrentSurfaceTexture::Lost => {
                self.surface.configure(c.renderer.device(), &self.config);
                self.window.request_redraw();
                return Ok(());
            }
            other => return Err(runtime(format!("surface acquisition: {other:?}"))),
        };
        let view = frame.texture.create_view(&Default::default());
        let mut encoder = c
            .renderer
            .device()
            .create_command_encoder(&Default::default());
        let jobs = ctx.tessellate(output.shapes, output.pixels_per_point);
        let screen = egui_wgpu::ScreenDescriptor {
            size_in_pixels: [self.config.width, self.config.height],
            pixels_per_point: output.pixels_per_point,
        };
        for (id, deltas) in &output.textures_delta.set {
            for delta in deltas {
                self.ui_renderer.update_texture(
                    c.renderer.device(),
                    c.renderer.queue(),
                    *id,
                    delta,
                );
            }
        }
        let extra = self.ui_renderer.update_buffers(
            c.renderer.device(),
            c.renderer.queue(),
            &mut encoder,
            &jobs,
            &screen,
        );
        {
            let mut pass = encoder.begin_render_pass(&wgpu::RenderPassDescriptor {
                color_attachments: &[Some(wgpu::RenderPassColorAttachment {
                    view: &view,
                    depth_slice: None,
                    resolve_target: None,
                    ops: wgpu::Operations {
                        load: wgpu::LoadOp::Clear(background_wgpu(c.data.background)),
                        store: wgpu::StoreOp::Store,
                    },
                })],
                ..Default::default()
            });
            if let Some(prepared) = &prepared {
                c.renderer
                    .paint_prepared(&mut pass, (self.config.width, self.config.height), prepared)
                    .map_err(runtime)?;
            }
            self.ui_renderer
                .render(&mut pass.forget_lifetime(), &jobs, &screen);
        }
        c.renderer
            .queue()
            .submit(extra.into_iter().chain(std::iter::once(encoder.finish())));
        c.renderer.queue().present(frame);
        c.renderer.end_gpu_frame();
        for id in &output.textures_delta.free {
            self.ui_renderer.free_texture(id);
        }
        // egui popups use a sizing pass before their visible pass; text inputs
        // also request delayed caret redraws without another OS input event.
        self.repaint_at = output
            .viewport_output
            .get(&egui::ViewportId::ROOT)
            .filter(|viewport| viewport.repaint_delay != Duration::MAX)
            .and_then(|viewport| Instant::now().checked_add(viewport.repaint_delay));
        if self.settings_only {
            self.last_revision = c.data.revision;
        }
        self.frames += 1;
        if let Some(start) = self.last_input.take() {
            self.latency_ms = start.elapsed().as_secs_f64() * 1000.;
        }
        let dpr = output.pixels_per_point;
        let controls = self
            .editor
            .controls
            .iter()
            .map(|(name, rect)| {
                (
                    name.clone(),
                    json!([
                        rect.min.x * dpr,
                        rect.min.y * dpr,
                        rect.width() * dpr,
                        rect.height() * dpr
                    ]),
                )
            })
            .collect::<serde_json::Map<_, _>>();
        let measure = CpuTextMeasure::for_style(&display.draw_style);
        let decorations = c
            .data
            .elements
            .iter()
            .filter_map(|(name, id)| {
                c.data
                    .hitmap
                    .selection_box(*id, &display, &measure)
                    .map(|b| {
                        (
                            name.clone(),
                            json!([b.rect.x, b.rect.y, b.rect.width, b.rect.height]),
                        )
                    })
            })
            .collect::<serde_json::Map<_, _>>();
        *self.control.stats.lock().unwrap() = json!({"host":"winit-wgpu","window_role":if self.settings_only { "settings" } else { "chart" },"inspector_overlay":self.inspector_overlay(),"picked_values":self.editor.picked,"selection_value_readbacks":c.data.selection_value_readbacks,"error":self.editor.error,"controls":controls,"decorations":decorations,"selected":self.selected,"properties_open":self.editor.inspector_open,"chart_panel":[panel.x,panel.y,panel.width,panel.height],"gpu_context_id":c.context.id,"figure_id":c.data.figure_id,"pool_used_bytes":c.renderer.pool().used_bytes(),"surface_frames":self.frames,"last_input_to_submit_ms":self.latency_ms,"scale_factor":self.window.scale_factor(),"surface_size":[self.config.width,self.config.height],"column_uploads":c.data.uploads,"rgba_readbacks":c.data.readbacks,"png_encodes":c.data.png_encodes,"revision":c.data.revision});
        Ok(())
    }
}
/// Transform bounds in axis space so logarithmic and inverted axes behave like
/// linear axes. Shift is measured as a fraction of the visible span.
fn navigate_axis(axis: &mut renderer::config::AxisOptions, factor: f64, anchor: f64, shift: f64) {
    let log = axis.scale == renderer::config::AxisScale::Logarithmic;
    let (min, max) = if log {
        (axis.min.log10(), axis.max.log10())
    } else {
        (axis.min, axis.max)
    };
    let span = max - min;
    let anchor = if axis.inverted { 1. - anchor } else { anchor };
    let shift = if axis.inverted { -shift } else { shift };
    let pivot = min + span * anchor;
    let low = pivot + (min - pivot) * factor + shift * span;
    let high = pivot + (max - pivot) * factor + shift * span;
    let (low, high) = if log {
        (10_f64.powf(low), 10_f64.powf(high))
    } else {
        (low, high)
    };
    if low.is_finite()
        && high.is_finite()
        && low < high
        && (!log || low > 0.)
        && (high - low) <= f32::MAX as f64
        && low.abs() <= f32::MAX as f64
        && high.abs() <= f32::MAX as f64
    {
        axis.min = low;
        axis.max = high;
    }
}

struct App {
    pending: Vec<(Arc<Mutex<FigureCore>>, Arc<Control>)>,
    windows: HashMap<WindowId, SurfaceWindow>,
    error: Option<PyErr>,
}
impl ApplicationHandler for App {
    fn resumed(&mut self, events: &ActiveEventLoop) {
        self.open_pending(events);
    }
    fn about_to_wait(&mut self, events: &ActiveEventLoop) {
        self.open_pending(events);
        self.windows.retain(|_, w| {
            !w.control.close.load(Ordering::Acquire)
                && w.core.strong_count() > 0
                && w.parent.as_ref().is_none_or(|p| {
                    p.upgrade()
                        .is_some_and(|p| !p.close.load(Ordering::Acquire))
                })
        });
        let settings = self
            .windows
            .values_mut()
            .filter_map(|w| {
                if !std::mem::take(&mut w.editor.advanced_requested) {
                    return None;
                }
                if let Some(existing) = w.control.settings.lock().unwrap().as_ref() {
                    if !existing.close.load(Ordering::Acquire) {
                        return None;
                    }
                }
                Some((w.core.upgrade()?, Arc::clone(&w.control)))
            })
            .collect::<Vec<_>>();
        for (core, parent) in settings {
            let control = Arc::new(Control::default());
            match SurfaceWindow::new(
                events,
                &core,
                control.clone(),
                true,
                Some(Arc::downgrade(&parent)),
            ) {
                Ok(w) => {
                    *parent.settings.lock().unwrap() = Some(control);
                    w.window.request_redraw();
                    self.windows.insert(w.window.id(), w);
                }
                Err(e) => self.error = Some(e),
            }
        }
        for w in self.windows.values_mut() {
            let due = w
                .repaint_at
                .is_some_and(|deadline| Instant::now() >= deadline);
            if due {
                w.repaint_at = None;
            }
            if due
                || w.control.dirty.swap(false, Ordering::AcqRel)
                || w.core
                    .upgrade()
                    .is_some_and(|c| c.lock().unwrap().revision != w.last_revision)
            {
                w.window.request_redraw();
            }
        }
    }
    fn window_event(&mut self, _: &ActiveEventLoop, id: WindowId, event: WindowEvent) {
        let Some(w) = self.windows.get_mut(&id) else {
            return;
        };
        if matches!(event, WindowEvent::CloseRequested) {
            w.control.close.store(true, Ordering::Release);
            return;
        }
        let response = w.input.on_window_event(&w.window, &event);
        let result = match event {
            WindowEvent::Focused(false) => {
                w.modifiers = ModifiersState::empty();
                w.dragging = false;
                w.panning = false;
                w.chart_pressed = false;
                Ok(())
            }
            WindowEvent::ModifiersChanged(modifiers) => {
                w.modifiers = modifiers.state();
                Ok(())
            }
            WindowEvent::KeyboardInput { ref event, .. }
                if !w.settings_only
                    && event.state == ElementState::Pressed
                    && !w.ctx.egui_wants_keyboard_input()
                    && !response.consumed =>
            {
                if let Key::Named(key) = &event.logical_key {
                    w.keyboard(key)
                } else {
                    Ok(())
                }
            }
            WindowEvent::Resized(s) => {
                w.resize(s.width, s.height);
                Ok(())
            }
            WindowEvent::ScaleFactorChanged { .. } => {
                let s = w.window.inner_size();
                w.resize(s.width, s.height);
                Ok(())
            }
            WindowEvent::RedrawRequested => w.frame(),
            WindowEvent::CursorMoved { position, .. } if !w.dragging => {
                w.cursor = (position.x as f32, position.y as f32);
                Ok(())
            }
            WindowEvent::CursorMoved { .. } => w.pointer(&event),
            WindowEvent::MouseInput {
                state: ElementState::Released,
                ..
            } if !w.settings_only => w.pointer(&event),
            _ if !w.settings_only
                && (w.chart_contains_cursor()
                    || (matches!(
                        event,
                        WindowEvent::MouseInput {
                            state: ElementState::Pressed,
                            button: MouseButton::Left,
                            ..
                        }
                    ) && w.editor.stage.contains(egui::pos2(
                        w.cursor.0 / w.ctx.pixels_per_point(),
                        w.cursor.1 / w.ctx.pixels_per_point(),
                    ))))
                && (!response.consumed
                    || w.ctx
                        .layer_id_at(egui::pos2(
                            w.cursor.0 / w.ctx.pixels_per_point(),
                            w.cursor.1 / w.ctx.pixels_per_point(),
                        ))
                        .is_none_or(|layer| layer.order == egui::Order::Background)) =>
            {
                w.pointer(&event)
            }
            _ => Ok(()),
        };
        if let Err(e) = result {
            w.editor.error = e.to_string();
            self.error = Some(e);
            w.control.close.store(true, Ordering::Release);
        }
        if response.repaint && !matches!(event, WindowEvent::RedrawRequested) {
            w.window.request_redraw();
        }
    }
}
impl App {
    fn open_pending(&mut self, events: &ActiveEventLoop) {
        for (core, control) in self.pending.drain(..) {
            match SurfaceWindow::new(events, &core, control, false, None) {
                Ok(w) => {
                    w.window.request_redraw();
                    self.windows.insert(w.window.id(), w);
                }
                Err(e) => self.error = Some(e),
            }
        }
    }
}
struct Host {
    events: EventLoop<()>,
    app: App,
}
thread_local! {static HOST:RefCell<Option<Host>>=const{RefCell::new(None)};}
fn pump(block: bool) -> PyResult<usize> {
    HOST.with(|h| {
        let mut h = h.borrow_mut();
        let Some(host) = h.as_mut() else { return Ok(0) };
        host.events.pump_app_events(
            Some(if block {
                Duration::from_millis(16)
            } else {
                Duration::ZERO
            }),
            &mut host.app,
        );
        if let Some(e) = host.app.error.take() {
            return Err(e);
        }
        Ok(host.app.windows.len())
    })
}
pub fn show(core: Arc<Mutex<FigureCore>>, block: bool) -> PyResult<WindowHandle> {
    let control = Arc::new(Control::default());
    HOST.with(|h| -> PyResult<()> {
        let mut h = h.borrow_mut();
        if h.is_none() {
            let events = EventLoop::new().map_err(runtime)?;
            events.set_control_flow(ControlFlow::Wait);
            *h = Some(Host {
                events,
                app: App {
                    pending: vec![],
                    windows: HashMap::new(),
                    error: None,
                },
            });
        }
        h.as_mut()
            .unwrap()
            .app
            .pending
            .push((core, control.clone()));
        Ok(())
    })?;
    pump(false)?;
    if block {
        while pump(true)? > 0 {}
    }
    Ok(WindowHandle { control })
}
#[pyfunction]
pub fn poll_events(py: Python<'_>) -> PyResult<usize> {
    py.detach(|| pump(false))
}
#[pyfunction]
pub fn run_events(py: Python<'_>) -> PyResult<()> {
    while py.detach(|| pump(true))? > 0 {
        py.check_signals()?;
    }
    Ok(())
}
